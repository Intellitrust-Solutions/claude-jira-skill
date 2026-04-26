#!/usr/bin/env python3
"""
批次建立 Epic → Module → Subtask 結構。

plan.json 格式：
{
    "epic_key": "PROJECT-491",
    "middle_type_id": "10004",     // 可選，未給則自動從 Epic 的 issuetype 推導
    "subtask_type_id": "10002",    // 可選
    "assignee_account_id": "712020:...",  // 可選，未給則使用目前使用者
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

結果寫入 /tmp/jira_build_result.json
"""
import json, sys, time, argparse
from pathlib import Path

import sys as _sys
if hasattr(_sys.stdout, "reconfigure"): _sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))
from jira_client import JiraClient


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


def build(plan_path: str, dry_run: bool = False, delay: float = 0.06) -> dict:
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

    # assignee 預設為當前使用者；若 plan 指定他人，警告
    me = jc.whoami()['accountId']
    account = plan.get('assignee_account_id') or me
    if account != me:
        print(f'⚠ plan 指定 assignee 為 {account}（非當前使用者 {me}）')

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

    out = '/tmp/jira_build_result.json'
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'middles: {len(result["middles"])}, subtasks: {len(result["subtasks"])}, failed: {len(result["failed"])}')
    print(f'寫入: {out}')
    return result


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True, help='plan.json 檔案路徑')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--delay', type=float, default=0.06)
    args = ap.parse_args()
    build(args.plan, args.dry_run, args.delay)


if __name__ == '__main__':
    _cli()
