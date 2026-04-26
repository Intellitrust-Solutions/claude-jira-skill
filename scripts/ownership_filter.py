#!/usr/bin/env python3
"""
過濾出「自己的」Jira issue（assignee 或 reporter = currentUser）。

用法：
    # 單一 key 檢查
    python3 ownership_filter.py --check PROJECT-XXX

    # 批次過濾（stdin 一行一 key）
    cat keys.txt | python3 ownership_filter.py --filter
    # 輸出僅自己的 keys

    # Epic 子項用 JQL 過濾
    python3 ownership_filter.py --under PROJECT-XXX
"""
import sys, argparse
from pathlib import Path

import sys as _sys
if hasattr(_sys.stdout, "reconfigure"): _sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))
from jira_client import JiraClient


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', help='檢查單一 key 是否屬自己')
    ap.add_argument('--filter', action='store_true', help='從 stdin 讀 keys 過濾')
    ap.add_argument('--under', help='Epic key，用 JQL 列出自己的子項')
    args = ap.parse_args()

    jc = JiraClient.from_env()

    if args.check:
        mine = jc.is_mine(args.check)
        print('YES' if mine else 'NO')
        sys.exit(0 if mine else 1)

    if args.filter:
        me = jc.whoami()['accountId']
        for line in sys.stdin:
            k = line.strip()
            if not k:
                continue
            if jc.is_mine(k):
                print(k)
        return

    if args.under:
        jql = f'parent={args.under} AND (assignee=currentUser() OR reporter=currentUser())'
        code, body = jc.api('POST', '/rest/api/3/search/jql',
            {'jql': jql, 'fields': ['key', 'summary'], 'maxResults': 200})
        for i in body.get('issues', []):
            print(f"{i['key']:14} | {i['fields']['summary']}")
        return

    print('需要 --check / --filter / --under'); sys.exit(1)


if __name__ == '__main__':
    _cli()
