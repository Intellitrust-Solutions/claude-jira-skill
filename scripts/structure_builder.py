#!/usr/bin/env python3
"""
批次建立 Epic → Module → Subtask 結構。

plan.json 格式：
{
    "epic_key": "PROJECT-XXX",
    "middle_type_id": "10004",     // 可選，未給則自動從 Epic 的 issuetype 推導
    "subtask_type_id": "10002",    // 可選
    "assignee_account_id": "712020:...",  // 可選，須加 --include-others 才會生效
    "middles": [
        {
            "summary": "基礎建設與安全防護",
            "due": "2026-04-23",
            "subtasks": [
                {"summary": "Laravel + Inertia + Vite 腳手架", "hours": 3},
                {"summary": "資料庫核心 migration", "hours": 2}
            ]
        }
    ]
}

結果寫入 ~/.cache/jira-skill/build_result.json（chmod 0600）
"""
import json, sys, time, argparse
from pathlib import Path

import sys as _sys
if hasattr(_sys.stdout, "reconfigure"): _sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))
from jira_client import JiraClient, output_path


def auto_resolve_types(jc: JiraClient) -> tuple[str, str]:
    """自動挑選 Middle (level=0, non-subtask) 和 Subtask (subtask=true) type id。"""
    types = jc.issuetypes()
    middle = next((t for t in types if t['level'] == 0 and not t['subtask']
                   and t['name'] in ('任務', 'Task')), None) or \
             next((t for t in types if t['level'] == 0 and not t['subtask']), None)
    subtask = next((t for t in types if t['subtask']
                    and t['name'] in ('Subtask', '子任務')), None) or \
              next((t for t in types if t['subtask']), None)
    if not middle or not subtask:
        raise RuntimeError('找不到合適的 middle/subtask type')
    return middle['id'], subtask['id']


def build(plan_path: str, dry_run: bool = False, delay: float = 0.06,
          include_others: bool = False) -> dict:
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    jc = JiraClient.from_env()

    epic_key = plan['epic_key']
    project_key = epic_key.split('-')[0]

    # 驗證 Epic 確實屬於當前使用者，避免在他人 Epic 底下亂建
    jc.assert_mine(epic_key, '建立子項於 Epic')

    middle_type = plan.get('middle_type_id') or None
    subtask_type = plan.get('subtask_type_id') or None
    if not middle_type or not subtask_type:
        mt, st = auto_resolve_types(jc)
        middle_type = middle_type or mt
        subtask_type = subtask_type or st

    # assignee 預設為當前使用者；plan 指定他人需 --include-others
    me = jc.whoami()['accountId']
    plan_account = plan.get('assignee_account_id')
    if plan_account and plan_account != me and not include_others:
        raise PermissionError(
            f'plan.json 指定 assignee={plan_account}（非當前使用者 {me}）。'
            f'若確認要把任務 assign 給他人，請加 --include-others 旗標。'
        )
    account = plan_account if (include_others and plan_account) else me
    if account != me:
        print(f'⚠ assignee = {account}（非當前使用者，--include-others 已啟用）')

    result = {'epic': epic_key, 'middles': [], 'subtasks': [], 'failed': []}

    for m in plan['middles']:
        if dry_run:
            print(f'[dry-run] 會建立 middle: {m["summary"]} (due {m["due"]})')
            for s in m.get('subtasks', []):
                print(f'    └── {s["summary"]}')
            continue

        payload = {
            'fields': {
                'project': {'key': project_key},
                'issuetype': {'id': middle_type},
                'summary': m['summary'],
                'duedate': m['due'],
                'assignee': {'accountId': account},
                'parent': {'key': epic_key},
            }
        }
        code, body = jc.api('POST', '/rest/api/3/issue', payload)
        if code not in (200, 201):
            result['failed'].append({'middle': m['summary'], 'code': code, 'body': body})
            continue
        mid_key = body['key']
        result['middles'].append({'key': mid_key, 'summary': m['summary'], 'due': m['due']})
        time.sleep(delay)

        for s in m.get('subtasks', []):
            spayload = {
                'fields': {
                    'project': {'key': project_key},
                    'issuetype': {'id': subtask_type},
                    'summary': s['summary'],
                    'duedate': m['due'],
                    'assignee': {'accountId': account},
                    'parent': {'key': mid_key},
                }
            }
            sc, sb = jc.api('POST', '/rest/api/3/issue', spayload)
            if sc in (200, 201):
                result['subtasks'].append({'key': sb['key'], 'parent': mid_key, 'summary': s['summary']})
            else:
                result['failed'].append({'subtask': s['summary'], 'parent': mid_key, 'code': sc})
            time.sleep(delay)

    out = output_path('build_result.json')
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    out.chmod(0o600)
    print(f'middles: {len(result["middles"])}, subtasks: {len(result["subtasks"])}, failed: {len(result["failed"])}')
    print(f'寫入: {out}')
    return result


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True, help='plan.json 檔案路徑')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--delay', type=float, default=0.06)
    ap.add_argument('--include-others', action='store_true',
                    help='⚠ 危險：允許把任務 assign 給非當前使用者（預設只 assign 給自己）')
    args = ap.parse_args()
    build(args.plan, args.dry_run, args.delay, args.include_others)


if __name__ == '__main__':
    _cli()
