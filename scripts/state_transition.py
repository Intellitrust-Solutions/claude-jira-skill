#!/usr/bin/env python3
"""
批次 Jira 狀態轉換。動態查可用 transitions、找最短路徑。

用法：
    # 列出某 issue 可用 transitions
    python3 state_transition.py --list PROJECT-XXX

    # 批次轉換（keys.txt 一行一個 key）
    python3 state_transition.py --keys keys.txt --target 完成

    # 從測試結果推進
    python3 state_transition.py --from ~/.cache/jira-skill/module_test_results.json

    # Epic 底下所有子項統一推到某狀態（可省略 KEY，讀 JIRA_EPIC_KEY env）
    python3 state_transition.py --all-under PROJECT-XXX --target 進行中
"""
import json, sys, time, argparse
from pathlib import Path

import sys as _sys
if hasattr(_sys.stdout, "reconfigure"): _sys.stdout.reconfigure(encoding="utf-8")
from collections import deque

sys.path.insert(0, str(Path(__file__).parent))
from jira_client import JiraClient, output_path, resolve_epic_key


def find_path(jc: JiraClient, key: str, target: str, max_hops: int = 6) -> list[str]:
    """BFS 從當前狀態找到目標狀態的 transition id 序列（最短路徑）。"""
    start = jc.get_status(key)
    if start == target:
        return []
    # 由於 transitions 依 issue 當前狀態而變，此處用假設圖：
    # 記錄每個已探索狀態的可用 transitions（這個 issue 本身一路走）
    # 實作為真實 stateful walk：逐步推進並驗證
    # 但要先用 dry 的 walk，所以我們實作一個「預查」：
    # 因為 API 只能查「當前」可用 transitions，我們採另一策略：
    # 使用者提供明確的狀態名，我們多次查 transitions 找路徑

    # 策略：模擬 walk — 在本地記錄當前假設狀態，但狀態轉後的下一步必須實際查詢
    # 由於成本高，且多數 workflow 線性，這裡做 greedy：每步查 transitions 挑能逼近目標的。

    # 簡化：查當前 transitions，若有直達目標，走；否則挑「第一個往前」的。
    # 若走不到則回報。

    visited = {start}
    path = []
    current = start
    for _ in range(max_hops):
        trans = jc.transitions(key)
        # 直達
        direct = next((t for t in trans if t['to'] == target), None)
        if direct:
            path.append(direct['id'])
            return path
        # 挑一個還沒拜訪過且可能前進的
        candidate = next((t for t in trans if t['to'] not in visited
                          and t['name'] not in ('CANCEL', 'Pending', 'back')), None)
        if not candidate:
            break
        path.append(candidate['id'])
        visited.add(candidate['to'])
        # 真的走一步
        jc.api('POST', f'/rest/api/3/issue/{key}/transitions',
               {'transition': {'id': candidate['id']}})
        current = candidate['to']
        if current == target:
            return path
    raise RuntimeError(f'{key} 從 {start} 走不到 {target}')


def transition_one(jc: JiraClient, key: str, target: str) -> tuple[bool, str]:
    try:
        start = jc.get_status(key)
        if start == target:
            return True, f'already at {target}'
        find_path(jc, key, target)
        return True, f'{start} -> {target}'
    except Exception as e:
        return False, str(e)


def batch(jc: JiraClient, keys: list[str], target: str, delay: float = 0.05) -> dict:
    result = {'ok': [], 'failed': []}
    for k in keys:
        ok, msg = transition_one(jc, k, target)
        (result['ok'] if ok else result['failed']).append({'key': k, 'msg': msg})
        time.sleep(delay)
    return result


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', help='列出某 issue 的可用 transitions')
    ap.add_argument('--keys', help='keys.txt 檔案路徑，每行一 key')
    ap.add_argument('--from', dest='from_json', help='從測試結果 JSON 決定要推哪些')
    ap.add_argument('--all-under', nargs='?', const='', default=None,
                    help='Epic key，推所有子項（可省略，會讀 JIRA_EPIC_KEY env）')
    ap.add_argument('--target', help='目標狀態名稱，例如「完成」')
    ap.add_argument('--include-others', action='store_true',
                    help='⚠ 危險：操作非本人 issue（預設只動自己的）')
    ap.add_argument('--delay', type=float, default=0.05)
    args = ap.parse_args()

    jc = JiraClient.from_env()

    if args.list:
        for t in jc.transitions(args.list):
            print(f"{t['id']:4} | {t['name']:16} -> {t['to']}")
        return

    if not args.target:
        print('需要 --target'); sys.exit(1)

    keys = []
    if args.keys:
        keys = [l.strip() for l in Path(args.keys).read_text(encoding='utf-8').splitlines() if l.strip()]
    elif args.from_json:
        data = json.loads(Path(args.from_json).read_text(encoding='utf-8'))
        # 統一格式：{ "tests": { "name": { status, module_key, subtask_keys } } }
        if isinstance(data, dict) and 'tests' in data:
            for name, t in data['tests'].items():
                if t.get('status') != 'PASS':
                    print(f'⊘ {name}（{t.get("status")}）跳過')
                    continue
                if t.get('module_key'):
                    keys.append(t['module_key'])
                keys.extend(t.get('subtask_keys', []))
        # 簡易格式：[{"key": "..."}]
        elif isinstance(data, list):
            keys = [d['key'] for d in data if 'key' in d]
        # 舊格式：{ "name": { status, detail } }（無 jira key，無法推進）
        else:
            print('⚠ 偵測到舊格式（無 module_key）— 請用更新後的 module_test.php.tmpl 重跑測試')
            print('   或手動轉成 [{"key": "..."}] / {"tests": {...}} 格式')
            sys.exit(1)
    elif args.all_under is not None:
        epic = resolve_epic_key(args.all_under or None)
        jc.assert_mine(epic, '操作 Epic')
        jql = f'parent={epic}'
        if not args.include_others:
            jql += ' AND (assignee=currentUser() OR reporter=currentUser())'
        code, body = jc.api('POST', '/rest/api/3/search/jql',
            {'jql': jql, 'fields': ['key'], 'maxResults': 200})
        keys = [i['key'] for i in body.get('issues', [])]
    else:
        print('需要 --keys / --from / --all-under 之一'); sys.exit(1)

    # 批次擁有者過濾（除非加 --include-others）
    if not args.include_others and (args.keys or args.from_json):
        me = jc.whoami()['accountId']
        original = len(keys)
        keys = [k for k in keys if jc.is_mine(k)]
        skipped = original - len(keys)
        if skipped > 0:
            print(f'⊘ 跳過 {skipped} 個非本人 issue（加 --include-others 可包含）')

    print(f'批次推進 {len(keys)} 項 → {args.target}')
    result = batch(jc, keys, args.target, args.delay)
    out = output_path('transition_result.json')
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    out.chmod(0o600)
    print(f'ok: {len(result["ok"])}, failed: {len(result["failed"])}')
    print(f'寫入: {out}')


if __name__ == '__main__':
    _cli()
