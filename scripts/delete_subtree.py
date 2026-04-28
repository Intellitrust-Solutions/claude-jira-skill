#!/usr/bin/env python3
"""
安全批次刪除 Epic 底下的所有子項（中型 + 小型）。

*** 雙重保護 ***
1. 預設 dry-run（不指定 --yes 不會真刪）
2. 預設只刪屬於自己的（mine-only=ON）；要刪別人的需 --include-others 並再次確認

用法：
    # 預覽（預設只列出自己的）
    python3 delete_subtree.py PROJECT-XXX

    # 真的刪自己的
    python3 delete_subtree.py PROJECT-XXX --yes

    # 強制刪別人的（危險）
    python3 delete_subtree.py PROJECT-XXX --yes --include-others
"""
import json, sys, time, argparse
from pathlib import Path

import sys as _sys
if hasattr(_sys.stdout, "reconfigure"): _sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))
from jira_client import JiraClient, output_path, resolve_epic_key


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('epic_key', nargs='?', help='Epic key（可省略，會讀 JIRA_EPIC_KEY env）')
    ap.add_argument('--yes', action='store_true', help='確認執行（否則只 dry-run）')
    ap.add_argument('--include-others', action='store_true',
                    help='⚠ 危險：包含他人的 issue（預設只刪自己的）')
    ap.add_argument('--delay', type=float, default=0.04)
    args = ap.parse_args()

    jc = JiraClient.from_env()
    epic = resolve_epic_key(args.epic_key)
    jc.assert_mine(epic, '操作 Epic')  # 連 Epic 本身都要是自己的

    jql = f'parent={epic}'
    if not args.include_others:
        jql += ' AND (assignee=currentUser() OR reporter=currentUser())'
    else:
        print('⚠ --include-others 模式：將包含非本人 issue')

    code, body = jc.api('POST', '/rest/api/3/search/jql',
        {'jql': jql, 'fields': ['key', 'summary', 'status'], 'maxResults': 500})

    issues = body.get('issues', [])
    print(f'找到 {len(issues)} 個中型任務（parent={epic}）')
    for i in issues:
        print(f"  {i['key']:14} | {i['fields']['status']['name']:8} | {i['fields']['summary']}")

    if not args.yes:
        print('\n(dry-run) 加 --yes 才真的刪除')
        return

    print('\n開始刪除（含子項）…')
    deleted, failed = 0, []
    for i in issues:
        k = i['key']
        c, _ = jc.api('DELETE', f'/rest/api/3/issue/{k}?deleteSubtasks=true')
        if c in (200, 204, 404):
            deleted += 1
        else:
            failed.append({'key': k, 'code': c})
        time.sleep(args.delay)

    out = output_path('delete_result.json')
    out.write_text(
        json.dumps({'epic': epic, 'deleted': deleted, 'failed': failed},
                   ensure_ascii=False, indent=2),
        encoding='utf-8')
    out.chmod(0o600)
    print(f'刪除: {deleted}/{len(issues)}, 失敗: {len(failed)}')
    print(f'寫入: {out}')


if __name__ == '__main__':
    _cli()
