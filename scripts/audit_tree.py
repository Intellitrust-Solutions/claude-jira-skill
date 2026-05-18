#!/usr/bin/env python3
"""
事後審計 Epic 樹的顆粒度合規（Lv2 規則）。

用法：
    python3 audit_tree.py PROJECT-XXX
    python3 audit_tree.py PROJECT-XXX --json
    python3 audit_tree.py PROJECT-XXX --only-violations  # 只列違規

用途：抓 Jira 上實際的 subtask（含手動在網頁建的、其他工具建的），
比對 references/granularity-rules.md 的 Lv2 規則，列出違規項。

判讀（每個 subtask）：
  ✓ hours ∈ {1.5, 2, 2.5, 3} 且模組總工時 ≤ 22h
  ⚠ hours = 1.5（軟警告：偏細）
  ✗ hours 違規 / 模組總工時 > 22h（硬閘門）
  ? 沒寫 hours（無法審計）

退出碼：0=全部合規或僅軟警告；1=有硬閘門違規；2=有 ? 缺資料
"""
import sys, json, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jira_client import JiraClient, resolve_epic_key
from structure_builder import (
    ALLOWED_SUBTASK_HOURS, MAX_MODULE_HOURS, SOFT_TARGET_LOWER,
    expected_subtask_count, parse_hours_from_jira,
)


def fetch_tree_with_hours(jc: JiraClient, epic_key: str) -> dict:
    """抓 Epic 樹，帶 timetracking。"""
    _, body = jc.api('POST', '/rest/api/3/search/jql', {
        'jql': f'parent={epic_key}',
        'fields': ['summary', 'status', 'duedate', 'timetracking'],
        'maxResults': 200,
    })
    middles = body.get('issues', [])
    tree = {'epic': epic_key, 'middles': []}
    for m in middles:
        mk = m['key']
        _, sb = jc.api('POST', '/rest/api/3/search/jql', {
            'jql': f'parent={mk}',
            'fields': ['summary', 'status', 'duedate', 'timetracking'],
            'maxResults': 200,
        })
        subtasks = []
        for s in sb.get('issues', []):
            subtasks.append({
                'key': s['key'],
                'summary': s['fields']['summary'],
                'status': s['fields']['status']['name'],
                'hours': parse_hours_from_jira(s['fields'].get('timetracking')),
            })
        tree['middles'].append({
            'key': mk,
            'summary': m['fields']['summary'],
            'status': m['fields']['status']['name'],
            'hours': parse_hours_from_jira(m['fields'].get('timetracking')),
            'subtasks': subtasks,
        })
    return tree


def audit_tree(tree: dict) -> dict:
    """
    判讀每個 subtask 與 module。
    回傳 {
      'modules': [{'key', 'summary', 'total_hours', 'issues': [...]}],
      'summary': {'hard': N, 'soft': N, 'missing': N, 'ok': N},
    }
    """
    out = {'modules': [], 'summary': {'hard': 0, 'soft': 0, 'missing': 0, 'ok': 0}}
    s = out['summary']

    for m in tree['middles']:
        issues = []
        # 計算模組總工時（只計算有寫 hours 的）
        known_hours = [st['hours'] for st in m['subtasks'] if st['hours'] is not None]
        total = sum(known_hours)
        has_missing = len(known_hours) != len(m['subtasks'])

        if total > MAX_MODULE_HOURS:
            issues.append({
                'level': 'hard', 'kind': 'module_over_22h',
                'msg': f'模組總工時 {total}h > {MAX_MODULE_HOURS}h → 拆模組',
            })
            s['hard'] += 1

        # 速查表 count 對齊
        if not has_missing and 1.5 <= total <= MAX_MODULE_HOURS:
            exp = expected_subtask_count(total)
            if exp is not None and len(m['subtasks']) != exp:
                issues.append({
                    'level': 'soft', 'kind': 'count_mismatch',
                    'msg': f'總工時 {total}h 建議 {exp} 個 subtask，實際 {len(m["subtasks"])} 個',
                })
                s['soft'] += 1

        # 逐個 subtask
        for st in m['subtasks']:
            h = st['hours']
            if h is None:
                issues.append({
                    'level': 'missing', 'kind': 'no_estimate',
                    'subtask': st['key'], 'summary': st['summary'],
                    'msg': f'{st["key"]} 沒寫 originalEstimate（手動建的？）— 無法審計',
                })
                s['missing'] += 1
                continue
            if h not in ALLOWED_SUBTASK_HOURS:
                if h < 1.5:
                    msg = f'{st["key"]} hours={h} < 1.5h → 併入 module description'
                elif h > 3.0:
                    msg = f'{st["key"]} hours={h} > 3h → 拆成 2 個'
                else:
                    msg = f'{st["key"]} hours={h} 不是半小時錨點（{sorted(ALLOWED_SUBTASK_HOURS)}）'
                issues.append({
                    'level': 'hard', 'kind': 'hours_violation',
                    'subtask': st['key'], 'summary': st['summary'],
                    'hours': h, 'msg': msg,
                })
                s['hard'] += 1
            elif h < SOFT_TARGET_LOWER:
                issues.append({
                    'level': 'soft', 'kind': 'below_soft_lower',
                    'subtask': st['key'], 'summary': st['summary'],
                    'hours': h,
                    'msg': f'{st["key"]} hours={h} < 軟下限 2.0h（偏細）',
                })
                s['soft'] += 1
            else:
                s['ok'] += 1

        out['modules'].append({
            'key': m['key'], 'summary': m['summary'],
            'status': m['status'], 'total_hours': total,
            'subtask_count': len(m['subtasks']),
            'issues': issues,
        })

    return out


def print_report(epic: str, audit: dict, only_violations: bool = False) -> None:
    s = audit['summary']
    total_issues = s['hard'] + s['soft'] + s['missing']
    print(f'=== {epic} Lv2 顆粒度審計 ===')
    print(f"  ✗ 硬閘門違規：{s['hard']}")
    print(f"  ⚠ 軟警告：    {s['soft']}")
    print(f"  ? 缺 hours：  {s['missing']}")
    print(f"  ✓ 合規 subtask：{s['ok']}")
    print()

    for m in audit['modules']:
        if only_violations and not m['issues']:
            continue
        head = f"[{m['status']:8}] {m['key']} {m['summary']} ({m['total_hours']}h, {m['subtask_count']} subtasks)"
        print(head)
        for it in m['issues']:
            mark = {'hard': '✗', 'soft': '⚠', 'missing': '?'}[it['level']]
            print(f'  {mark} {it["msg"]}')
        if not m['issues'] and not only_violations:
            print('  ✓ 模組內全部合規')
        print()

    if total_issues == 0:
        print('🎉 全部合規')


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('epic_key', nargs='?', help='Epic key（省略則讀 JIRA_EPIC_KEY env）')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--only-violations', action='store_true',
                    help='只印有違規的 module')
    args = ap.parse_args()

    jc = JiraClient.from_env()
    epic = resolve_epic_key(args.epic_key)
    tree = fetch_tree_with_hours(jc, epic)
    audit = audit_tree(tree)

    if args.json:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print_report(epic, audit, only_violations=args.only_violations)

    s = audit['summary']
    if s['hard'] > 0:
        sys.exit(1)
    if s['missing'] > 0:
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    _cli()
