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
            "due": "2026-04-23",          // 可選，未給則依 --start-date + subtask 工時自動推算
            "description": "...",          // 可選，純文字；< 1.5h 的實作細節塞這裡
            "subtasks": [
                // hours 必須 ∈ {1.5, 2, 2.5, 3}（Lv2 半小時錨點）
                {"summary": "Laravel + Inertia + Vite 腳手架", "hours": 3},
                {"summary": "資料庫核心 migration", "hours": 2}
            ]
        }
    ]
}

Lv2 顆粒度規則（pre-flight 自動驗證）：
- subtask.hours 只能是 1.5 / 2 / 2.5 / 3
- module 總工時 ≤ 22h（超過要拆模組）
- 軟區間 2.0–3.0h（1.5h 會警告）
- 完整規則：references/granularity-rules.md

工時 → due 推算規則：
- 每天有效工時 8h（依 references/granularity-rules.md）
- 模組總工時 = sum(subtask hours)；ceil(總工時 / 8) = 工作天數
- 跳過非工作日（預設週末，可用 JIRA_WORKING_DAYS env var 自訂）
- 前一個 module 的 due 為下一個 module 的起算日 + 1 工作日

工作日設定（JIRA_WORKING_DAYS）：
- 逗號分隔的星期數（0=週一, 1=週二, ..., 5=週六, 6=週日）
- 預設 "0,1,2,3,4"（週一到週五）
- 範例：Tue-Sat 設 "1,2,3,4,5"

結果寫入 ~/.cache/jira-skill/build_result.json（chmod 0600）
"""
import os, json, sys, time, argparse, math
from datetime import date, datetime, timedelta
from pathlib import Path

import sys as _sys
if hasattr(_sys.stdout, "reconfigure"): _sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))
from jira_client import JiraClient, output_path


HOURS_PER_DAY = 8.0
DEFAULT_WORKING_DAYS = {0, 1, 2, 3, 4}  # 週一到週五

# Lv2 顆粒度規則（references/granularity-rules.md）
ALLOWED_SUBTASK_HOURS = {1.5, 2.0, 2.5, 3.0}  # 半小時錨點
SOFT_TARGET_LOWER = 2.0                        # 軟區間下限（1.5h 雖允許但會警告）
MAX_MODULE_HOURS = 22.0                        # 模組總工時上限


def expected_subtask_count(total: float) -> int | None:
    """模組總工時 → 推薦 subtask 數。回傳 None 表示超出範圍（必須拆模組）。"""
    if total < 1.5:
        return 0
    if total <= 3.0:  return 1
    if total <= 6.0:  return 2
    if total <= 9.0:  return 3
    if total <= 12.0: return 4
    if total <= 15.0: return 5
    if total <= 18.0: return 6
    if total <= 21.0: return 7
    if total <= 22.0: return 8
    return None


def validate_plan_granularity(plan: dict) -> tuple[list[str], list[str]]:
    """
    依 Lv2 規則驗證 plan.json。回傳 (hard_errors, soft_warnings)。
    硬閘門：
      - subtask.hours ∉ {1.5, 2, 2.5, 3}
      - 模組總工時 > 22h
    軟警告（--force 可略過）：
      - subtask.hours = 1.5（< 軟下限 2.0h）
      - subtask 數量與模組總工時不對齊速查表
    """
    errors: list[str] = []
    warnings: list[str] = []

    for m_idx, m in enumerate(plan.get('middles', [])):
        m_label = f'middles[{m_idx}] "{m.get("summary", "<未命名>")}"'
        subtasks = m.get('subtasks', [])
        total = sum(s.get('hours', 0) for s in subtasks)

        if total > MAX_MODULE_HOURS:
            errors.append(
                f'{m_label}: 總工時 {total}h > {MAX_MODULE_HOURS}h → 拆成兩個 module'
            )

        for s_idx, s in enumerate(subtasks):
            s_label = f'{m_label} / subtasks[{s_idx}] "{s.get("summary", "<未命名>")}"'
            h = s.get('hours')
            if h is None:
                errors.append(f'{s_label}: 缺 hours 欄位')
                continue
            if h not in ALLOWED_SUBTASK_HOURS:
                if h < 1.5:
                    errors.append(
                        f'{s_label}: hours={h} < 1.5h → 併入 module description，不開 subtask'
                    )
                elif h > 3.0:
                    errors.append(
                        f'{s_label}: hours={h} > 3h → 拆成 2 個 subtask（每個 ≥ 1.5h）'
                    )
                else:
                    errors.append(
                        f'{s_label}: hours={h} 不是半小時錨點，'
                        f'允許值 {sorted(ALLOWED_SUBTASK_HOURS)}'
                    )
                continue
            if h < SOFT_TARGET_LOWER:
                warnings.append(
                    f'{s_label}: hours={h} < 軟下限 2.0h（偏細，確認不該併入 description）'
                )

        if subtasks and 1.5 <= total <= MAX_MODULE_HOURS:
            expected = expected_subtask_count(total)
            count = len(subtasks)
            if expected is not None and count != expected:
                warnings.append(
                    f'{m_label}: 總工時 {total}h 建議 {expected} 個 subtask，實際 {count} 個'
                )

    return errors, warnings


def parse_hours_from_jira(timetracking: dict | None) -> float | None:
    """
    從 Jira timetracking 欄位讀 hours。
    Jira 同時提供 originalEstimateSeconds（秒）與 originalEstimate（字串 "3h" / "2h 30m"）。
    優先用秒數，回傳 float hours；無資料回 None。
    """
    if not timetracking:
        return None
    secs = timetracking.get('originalEstimateSeconds')
    if secs is not None:
        try:
            return round(float(secs) / 3600.0, 2)
        except (TypeError, ValueError):
            pass
    raw = timetracking.get('originalEstimate')
    if not raw:
        return None
    # 解析 "Xh Ym" 字串
    total = 0.0
    cur = ''
    for ch in str(raw):
        if ch.isdigit() or ch == '.':
            cur += ch
        elif ch in 'hH':
            if cur:
                total += float(cur); cur = ''
        elif ch in 'mM':
            if cur:
                total += float(cur) / 60.0; cur = ''
        elif ch in 'dD':
            if cur:
                total += float(cur) * 8.0; cur = ''  # 1d = 8h
    return round(total, 2) if total > 0 else None


def text_to_adf(text: str) -> dict | None:
    """純文字 → Atlassian Document Format（每行一段 paragraph）。空字串回 None。"""
    if not text or not text.strip():
        return None
    content = []
    for line in text.split('\n'):
        line = line.rstrip()
        if line:
            content.append({
                'type': 'paragraph',
                'content': [{'type': 'text', 'text': line}],
            })
        else:
            content.append({'type': 'paragraph', 'content': []})
    return {'type': 'doc', 'version': 1, 'content': content}


DAY_NAME_TO_INT = {
    'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6,
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
    '一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6,
}


def _parse_day(token: str) -> int:
    """允許 '0'-'6' 數字或 'Mon/Tue/...' 名字（大小寫不限），中文「一」「二」等。"""
    t = token.strip().lower().lstrip('週周星期')
    if t.isdigit():
        n = int(t)
        if 0 <= n <= 6:
            return n
        raise ValueError(f'數字超出 0-6: {token}')
    if t in DAY_NAME_TO_INT:
        return DAY_NAME_TO_INT[t]
    raise ValueError(f'無法解析: {token}')


def get_working_days() -> set[int]:
    """
    從 JIRA_WORKING_DAYS env 讀工作日。
    可接受格式：
      - 數字：'0,1,2,3,4'（0=週一...6=週日）
      - 英文名：'Mon,Tue,Wed,Thu,Fri'（大小寫不限）
      - 中文名：'週一,週二,...' 或 '一,二,三,四,五'
      - 混合：'Mon,2,Wed,4'
    """
    raw = os.environ.get('JIRA_WORKING_DAYS', '').strip()
    if not raw:
        return DEFAULT_WORKING_DAYS
    try:
        days = {_parse_day(t) for t in raw.split(',') if t.strip()}
        if not days:
            raise ValueError('未解析出任何工作日')
        return days
    except ValueError as e:
        print(f'⚠ JIRA_WORKING_DAYS 解析失敗（{e}），fallback 用預設週一到週五')
        return DEFAULT_WORKING_DAYS


def is_workday(d: date, working_days: set[int] | None = None) -> bool:
    return d.weekday() in (working_days or get_working_days())


def next_workday(d: date, working_days: set[int] | None = None) -> date:
    """回傳下一個工作日（跳過非工作日）。"""
    wd = working_days or get_working_days()
    nxt = d + timedelta(days=1)
    while nxt.weekday() not in wd:
        nxt += timedelta(days=1)
    return nxt


def add_workdays(start: date, days: int, working_days: set[int] | None = None) -> date:
    """從 start 起算第 N 個工作日（含 start 當天若為工作日）。N=1 代表 start 當天。"""
    wd = working_days or get_working_days()
    if days <= 0:
        return start
    current = start
    # 若 start 不是工作日，先推到下個工作日再從那天算第 1 天
    while current.weekday() not in wd:
        current += timedelta(days=1)
    counted = 1
    while counted < days:
        current = next_workday(current, wd)
        counted += 1
    return current


def compute_module_due(start: date, hours: float,
                        working_days: set[int] | None = None) -> tuple[date, date]:
    """
    根據工時推算模組 due date。
    回傳 (該模組 due, 下個模組起算日)
    """
    wd = working_days or get_working_days()
    days = max(1, math.ceil(hours / HOURS_PER_DAY))
    due = add_workdays(start, days, wd)
    next_start = next_workday(due, wd)
    return due, next_start


def _project_issuetypes(jc: JiraClient, project_key: str) -> list[dict] | None:
    """
    用 createmeta API 列出該 project 允許的 issue types（project-aware）。
    失敗回 None，呼叫端用全域 issuetypes() fallback。
    """
    try:
        code, body = jc.api('GET',
            f'/rest/api/3/issue/createmeta/{project_key}/issuetypes')
        if code != 200:
            return None
        return [{
            'id': t['id'], 'name': t['name'],
            'level': t.get('hierarchyLevel'),
            'subtask': t.get('subtask', False),
        } for t in body.get('issueTypes', [])]
    except Exception:
        return None


def auto_resolve_types(jc: JiraClient, project_key: str | None = None) -> tuple[str, str]:
    """
    自動挑選 Middle (level=0) 和 Subtask (level=-1 / subtask=true) type id。
    優先用 project createmeta（避免多 project 同名 type 衝突，例如 IT 專案的
    「任務」是 10101，全域 issuetypes 第一個「任務」卻是 10004 — workflow scheme 不允許）。
    createmeta 失敗時 fallback 到全域。
    """
    types = _project_issuetypes(jc, project_key) if project_key else None
    if not types:
        types = jc.issuetypes()

    middle = next((t for t in types if t['level'] == 0 and not t['subtask']
                   and t['name'] in ('任務', 'Task')), None) or \
             next((t for t in types if t['level'] == 0 and not t['subtask']), None)
    subtask = next((t for t in types if t['subtask']
                    and t['name'] in ('Subtask', '子任務')), None) or \
              next((t for t in types if t['subtask']), None)
    if not middle or not subtask:
        raise RuntimeError(
            f'找不到合適的 middle/subtask type（project={project_key}）'
        )
    return middle['id'], subtask['id']


def build(plan_path: str, dry_run: bool = False, delay: float = 0.06,
          include_others: bool = False, start_date: str | None = None,
          check_only: bool = False, strict: bool = False, force: bool = False) -> dict:
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))

    # Lv2 顆粒度 pre-flight（在 connect Jira 之前先擋）
    errors, warnings = validate_plan_granularity(plan)
    if errors:
        print('✗ Pre-flight 硬閘門擋下，請修正：')
        for e in errors:
            print(f'  - {e}')
        raise SystemExit(1)
    if warnings:
        print('⚠ Pre-flight 軟警告：')
        for w in warnings:
            print(f'  - {w}')
        if strict:
            print('--strict：軟警告視為錯誤，停止')
            raise SystemExit(1)
        if not force and not check_only:
            print('要繼續請加 --force（dry-run 也適用）；或修正後重跑')
            raise SystemExit(1)
    else:
        print('✓ Pre-flight 全部通過')

    if check_only:
        print('--check-only：僅驗證，不連 Jira、不上傳')
        return {'check_only': True, 'errors': errors, 'warnings': warnings}

    jc = JiraClient.from_env()

    epic_key = plan['epic_key']
    project_key = epic_key.split('-')[0]

    # 驗證 Epic 確實屬於當前使用者，避免在他人 Epic 底下亂建
    jc.assert_mine(epic_key, '建立子項於 Epic')

    middle_type = plan.get('middle_type_id') or None
    subtask_type = plan.get('subtask_type_id') or None
    if not middle_type or not subtask_type:
        mt, st = auto_resolve_types(jc, project_key)
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

    # 工作日設定（先讓 from_env 把 .env 注入 os.environ）
    wd_set = get_working_days()
    weekday_names = ['週一','週二','週三','週四','週五','週六','週日']
    print(f'⚙ 工作日: {", ".join(weekday_names[i] for i in sorted(wd_set))}')

    # 起算日：CLI > plan 內 start_date > 今天
    if start_date:
        cur_start = datetime.strptime(start_date, '%Y-%m-%d').date()
    elif plan.get('start_date'):
        cur_start = datetime.strptime(plan['start_date'], '%Y-%m-%d').date()
    else:
        cur_start = date.today()
    # 若起算日不是工作日，推到下個工作日
    while cur_start.weekday() not in wd_set:
        cur_start += timedelta(days=1)

    result = {'epic': epic_key, 'middles': [], 'subtasks': [], 'failed': []}

    for m in plan['middles']:
        # due 來源：m['due'] > 依 subtask hours 自動推算
        if m.get('due'):
            module_due = m['due']
            # plan 指定 due 後，下個 module 起算日推到 due+1 工作日
            cur_start = next_workday(datetime.strptime(module_due, '%Y-%m-%d').date(), wd_set)
        else:
            total_hours = sum(s.get('hours', 0) for s in m.get('subtasks', []))
            if total_hours <= 0:
                total_hours = HOURS_PER_DAY  # 至少一天
            due_date_obj, cur_start = compute_module_due(cur_start, total_hours, wd_set)
            module_due = due_date_obj.isoformat()

        if dry_run:
            total_h = sum(s.get('hours', 0) for s in m.get('subtasks', []))
            print(f'[dry-run] 會建立 middle: {m["summary"]} (due {module_due}, ~{total_h}h)')
            for s in m.get('subtasks', []):
                print(f'    └── {s["summary"]}')
            continue

        fields = {
            'project': {'key': project_key},
            'issuetype': {'id': middle_type},
            'summary': m['summary'],
            'duedate': module_due,
            'assignee': {'accountId': account},
            'parent': {'key': epic_key},
        }
        adf_desc = text_to_adf(m.get('description', ''))
        if adf_desc:
            fields['description'] = adf_desc
        payload = {'fields': fields}
        code, body = jc.api('POST', '/rest/api/3/issue', payload)
        if code not in (200, 201):
            result['failed'].append({'middle': m['summary'], 'code': code, 'body': body})
            continue
        mid_key = body['key']
        result['middles'].append({'key': mid_key, 'summary': m['summary'], 'due': module_due})
        time.sleep(delay)

        for s in m.get('subtasks', []):
            sfields = {
                'project': {'key': project_key},
                'issuetype': {'id': subtask_type},
                'summary': s['summary'],
                'duedate': module_due,
                'assignee': {'accountId': account},
                'parent': {'key': mid_key},
            }
            # 把 hours 寫進 timetracking.originalEstimate，供 audit_tree.py / add_subtask.py 後續審計
            s_hours = s.get('hours')
            if s_hours:
                sfields['timetracking'] = {'originalEstimate': f'{s_hours}h'}
            spayload = {'fields': sfields}
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
    ap.add_argument('--start-date', help='起算日（YYYY-MM-DD），未給則用今天；'
                                          'plan.json 內如有 module 級 due 仍優先使用')
    ap.add_argument('--include-others', action='store_true',
                    help='⚠ 危險：允許把任務 assign 給非當前使用者（預設只 assign 給自己）')
    ap.add_argument('--check-only', action='store_true',
                    help='只跑 Lv2 顆粒度 pre-flight 驗證，不連 Jira、不上傳')
    ap.add_argument('--strict', action='store_true',
                    help='軟警告也視為錯誤')
    ap.add_argument('--force', action='store_true',
                    help='略過軟警告（硬閘門仍擋）')
    args = ap.parse_args()
    build(args.plan, args.dry_run, args.delay, args.include_others, args.start_date,
          args.check_only, args.strict, args.force)


if __name__ == '__main__':
    _cli()
