#!/usr/bin/env python3
"""
受控追加 subtask 到既有 module。**唯一允許單獨建 subtask 的入口**。

用法：
    python3 add_subtask.py <MODULE_KEY> --summary "..." --hours 2.5
    python3 add_subtask.py <MODULE_KEY> --summary "..." --hours 2 --check-only

行為：
1. 驗證 hours ∈ {1.5, 2, 2.5, 3}（Lv2 半小時錨點）
2. 從 Jira 撈該 module 現有 subtasks 的 hours 加總
3. 檢查「加完後的模組總工時 ≤ 22h」
4. 通過才 POST 新 subtask（繼承 module 的 duedate / project / parent）

設計理由（references/granularity-rules.md）：
- 階段 4-5 測試失敗後追加 bug fix subtask 是常見繞過點
- 走這個 script 強制過 Lv2 pre-flight，禁止用 Jira 網頁手動建

退出碼：0=成功；1=參數錯；2=Lv2 硬閘門擋下；3=Jira API 失敗
"""
import sys, json, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jira_client import JiraClient
from structure_builder import (
    ALLOWED_SUBTASK_HOURS, MAX_MODULE_HOURS, parse_hours_from_jira,
)


def fetch_module_info(jc: JiraClient, module_key: str) -> dict:
    """撈 module 本身的欄位（含 issuetype / duedate / project / parent epic）。"""
    code, body = jc.api(
        'GET',
        f'/rest/api/3/issue/{module_key}'
        f'?fields=summary,duedate,issuetype,project,parent,subtasks'
    )
    if code != 200:
        raise SystemExit(f'✗ 抓不到 module {module_key}（status={code}）：{body}')
    return body


def fetch_existing_subtask_hours(jc: JiraClient, module_key: str) -> tuple[float, list[dict]]:
    """回傳 (現有 subtask 工時加總, [{key, summary, hours}] 列表)。"""
    code, body = jc.api(
        'POST', '/rest/api/3/search/jql',
        {
            'jql': f'parent={module_key}',
            'fields': ['summary', 'timetracking'],
            'maxResults': 200,
        }
    )
    if code != 200:
        raise SystemExit(f'✗ 查不到 module {module_key} 的 subtasks：{body}')
    items = []
    total = 0.0
    for s in body.get('issues', []):
        h = parse_hours_from_jira(s['fields'].get('timetracking'))
        items.append({
            'key': s['key'],
            'summary': s['fields'].get('summary'),
            'hours': h,
        })
        if h:
            total += h
    return total, items


def auto_resolve_subtask_type(jc: JiraClient) -> str:
    """挑 subtask=true 的 issuetype id。"""
    types = jc.issuetypes()
    st = next((t for t in types if t['subtask']
               and t['name'] in ('Subtask', '子任務')), None) or \
         next((t for t in types if t['subtask']), None)
    if not st:
        raise RuntimeError('找不到 subtask issuetype')
    return st['id']


def add_subtask(module_key: str, summary: str, hours: float,
                check_only: bool = False, force_total: bool = False) -> dict:
    # 1. hours 必須是錨點值
    if hours not in ALLOWED_SUBTASK_HOURS:
        print(f'✗ hours={hours} 不是 Lv2 半小時錨點，允許值 {sorted(ALLOWED_SUBTASK_HOURS)}')
        if hours < 1.5:
            print('  → < 1.5h 的工作應併入 module description，不開 subtask')
        elif hours > 3.0:
            print('  → > 3h 的工作要拆成 2 個 subtask')
        raise SystemExit(2)

    jc = JiraClient.from_env()
    jc.assert_mine(module_key, '追加 subtask 到')

    # 2. 抓 module 與現有 subtasks
    module = fetch_module_info(jc, module_key)
    mfields = module['fields']
    existing_total, items = fetch_existing_subtask_hours(jc, module_key)

    print(f'Module {module_key}「{mfields.get("summary")}」')
    print(f'  現有 subtasks：{len(items)} 個，總工時 {existing_total}h')
    for it in items:
        h_str = f'{it["hours"]}h' if it['hours'] else '?h'
        print(f'    - {it["key"]} ({h_str}) {it["summary"]}')

    new_total = existing_total + hours
    print(f'  新增 "{summary}" ({hours}h) → 加完後 {new_total}h')

    # 3. 模組總工時上限
    if new_total > MAX_MODULE_HOURS:
        print(f'✗ 加完後 {new_total}h > {MAX_MODULE_HOURS}h（Lv2 模組上限）')
        if force_total:
            print('  ⚠ --force-total：略過，但建議拆模組')
        else:
            print('  → 拆成兩個 module，或合併現有 subtask 騰出空間')
            print('  → 如確認要硬塞，加 --force-total')
            raise SystemExit(2)

    if check_only:
        print('✓ --check-only 通過，未實際建立')
        return {'check_only': True}

    # 4. POST 新 subtask
    project_key = mfields['project']['key']
    duedate = mfields.get('duedate')
    subtask_type = auto_resolve_subtask_type(jc)
    me = jc.whoami()['accountId']

    payload = {
        'fields': {
            'project': {'key': project_key},
            'issuetype': {'id': subtask_type},
            'summary': summary,
            'assignee': {'accountId': me},
            'parent': {'key': module_key},
            'timetracking': {'originalEstimate': f'{hours}h'},
        }
    }
    if duedate:
        payload['fields']['duedate'] = duedate

    code, body = jc.api('POST', '/rest/api/3/issue', payload)
    if code not in (200, 201):
        print(f'✗ Jira API 失敗（status={code}）：{body}')
        raise SystemExit(3)
    print(f'✓ 建立 {body["key"]}（hours={hours}h, due={duedate}）')
    return {'key': body['key'], 'hours': hours, 'module': module_key}


def _cli():
    ap = argparse.ArgumentParser(description='受控追加 subtask 到既有 module（含 Lv2 pre-flight）')
    ap.add_argument('module_key', help='Module 的 Jira key（例：PROJ-123）')
    ap.add_argument('--summary', required=True, help='Subtask 標題')
    ap.add_argument('--hours', required=True, type=float,
                    help='工時，必須 ∈ {1.5, 2, 2.5, 3}')
    ap.add_argument('--check-only', action='store_true',
                    help='只驗證、不實際建立')
    ap.add_argument('--force-total', action='store_true',
                    help='⚠ 模組總工時超過 22h 時仍強制建立（不建議）')
    args = ap.parse_args()
    add_subtask(args.module_key, args.summary, args.hours,
                check_only=args.check_only, force_total=args.force_total)


if __name__ == '__main__':
    _cli()
