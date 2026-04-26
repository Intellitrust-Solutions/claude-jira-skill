#!/usr/bin/env python3
"""
查詢並顯示 Epic 底下的樹狀結構（含狀態）。

用法：
    python3 query_tree.py PROJECT-491
    python3 query_tree.py PROJECT-491 --json   # 輸出 JSON
    python3 query_tree.py PROJECT-491 --stats  # 狀態分佈統計
"""
import json, sys, argparse
from pathlib import Path

import sys as _sys
if hasattr(_sys.stdout, "reconfigure"): _sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from jira_client import JiraClient


def fetch_tree(jc: JiraClient, epic_key: str) -> dict:
    # 取中型
    _, body = jc.api('POST', '/rest/api/3/search/jql',
        {'jql': f'parent={epic_key}',
         'fields': ['summary','status','duedate','issuetype'],
         'maxResults': 200})
    middles = body.get('issues', [])

    tree = {'epic': epic_key, 'middles': []}
    for m in middles:
        mk = m['key']
        _, sb = jc.api('POST', '/rest/api/3/search/jql',
            {'jql': f'parent={mk}', 'fields': ['summary','status','duedate'], 'maxResults': 200})
        tree['middles'].append({
            'key': mk,
            'summary': m['fields']['summary'],
            'status': m['fields']['status']['name'],
            'due': m['fields'].get('duedate'),
            'subtasks': [{
                'key': s['key'],
                'summary': s['fields']['summary'],
                'status': s['fields']['status']['name'],
                'due': s['fields'].get('duedate'),
            } for s in sb.get('issues', [])]
        })
    return tree


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('epic_key')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--stats', action='store_true')
    args = ap.parse_args()

    jc = JiraClient.from_env()
    tree = fetch_tree(jc, args.epic_key)

    if args.json:
        print(json.dumps(tree, ensure_ascii=False, indent=2))
        return

    if args.stats:
        all_status = Counter()
        for m in tree['middles']:
            all_status[m['status']] += 1
            for s in m['subtasks']:
                all_status[s['status']] += 1
        total = sum(all_status.values())
        print(f'=== {args.epic_key} 樹狀統計（共 {total} 項）===')
        for status, count in all_status.most_common():
            bar = '█' * int(count / total * 30)
            print(f"  {status:10} {count:4}  {bar}")
        return

    print(f'Epic: {args.epic_key}')
    for m in tree['middles']:
        print(f"├── {m['key']:14} [{m['status']:8}] due={m['due']} | {m['summary']}")
        for i, s in enumerate(m['subtasks']):
            prefix = '│   └──' if i == len(m['subtasks']) - 1 else '│   ├──'
            print(f"{prefix} {s['key']:14} [{s['status']:8}] | {s['summary']}")


if __name__ == '__main__':
    _cli()
