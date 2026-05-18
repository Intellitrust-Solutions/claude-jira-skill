#!/usr/bin/env python3
"""
Git hook 整合器 — 在 pre-push 時整理本次 push 含的 Jira ticket，
互動提示是否推進狀態或補建 subtask。

被 .git/hooks/pre-push wrapper 呼叫：
    python3 .../git_hook.py pre-push

行為（pre-push）：
1. 從 stdin parse pre-push refs（git 傳給 hook 的格式）
2. 收集本次 push 範圍的 commits 與 messages
3. 用 regex 抽 Jira key（如 PROJ-123）
4. 連 Jira 查每個 key 的當前狀態
5. 互動詢問：要推進狀態 / 中止 push / 跳過繼續

關閉 hook：
    export JIRA_SKILL_SKIP_HOOK=1

設計理由：
- pre-push 是「發出去」的最後閘門，整理 Jira 最有意義
- 沒抓到 key 也不擋 push（純提示）
- Jira 連線失敗時靜默跳過（避免離線時擋 push）
"""
import os, re, sys, subprocess
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

ZERO_SHA = '0' * 40
JIRA_KEY_RE = re.compile(r'\b([A-Z][A-Z0-9]+-\d+)\b')


def log(msg: str = '') -> None:
    print(msg, file=sys.stderr)


def parse_push_refs() -> list[dict]:
    """從 stdin 讀 git pre-push 訊息（每行: local_ref local_sha remote_ref remote_sha）。"""
    refs = []
    for line in sys.stdin:
        parts = line.strip().split()
        if len(parts) >= 4:
            refs.append({
                'local_ref': parts[0], 'local_sha': parts[1],
                'remote_ref': parts[2], 'remote_sha': parts[3],
            })
    return refs


def collect_commits(refs: list[dict]) -> list[dict]:
    """收集要 push 的 commits（subject + body）。"""
    commits = []
    sep = '\x1f'   # ASCII unit separator，commit 內容不太可能含
    rec_sep = '\x1e'  # record separator
    for r in refs:
        if r['local_sha'] == ZERO_SHA:
            continue  # delete
        if r['remote_sha'] == ZERO_SHA:
            cmd = ['git', 'log', f'--format=%H{sep}%s{sep}%b{rec_sep}',
                   r['local_sha'], '--not', '--remotes']
        else:
            cmd = ['git', 'log', f'--format=%H{sep}%s{sep}%b{rec_sep}',
                   f'{r["remote_sha"]}..{r["local_sha"]}']
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        for record in out.split(rec_sep):
            record = record.strip().strip('\n')
            if not record:
                continue
            parts = record.split(sep)
            if len(parts) >= 2:
                commits.append({
                    'sha': parts[0].strip(),
                    'subject': parts[1] if len(parts) > 1 else '',
                    'body': parts[2] if len(parts) > 2 else '',
                })
    # 去重（多 ref 推同一 commit）
    seen = set()
    deduped = []
    for c in commits:
        if c['sha'] not in seen:
            seen.add(c['sha'])
            deduped.append(c)
    return deduped


def extract_jira_keys(commits: list[dict]) -> list[str]:
    keys = []
    seen = set()
    for c in commits:
        text = f'{c["subject"]}\n{c["body"]}'
        for m in JIRA_KEY_RE.finditer(text):
            k = m.group(1)
            if k not in seen:
                seen.add(k)
                keys.append(k)
    return keys


def tty_read(prompt: str, default: str = '') -> str:
    """從 /dev/tty 讀使用者輸入（pre-push 的 stdin 被 git 占用）。"""
    try:
        with open('/dev/tty', 'r') as tty:
            sys.stderr.write(prompt)
            sys.stderr.flush()
            return tty.readline().strip() or default
    except OSError:
        return default


def run_state_transition(keys: list[str], target: str) -> None:
    """呼叫 state_transition.py 推進指定 keys 到 target 狀態。"""
    script = Path(__file__).parent / 'state_transition.py'
    # 寫 keys 到暫存檔
    import tempfile
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt', encoding='utf-8') as f:
        for k in keys:
            f.write(k + '\n')
        keys_path = f.name
    try:
        cmd = ['python3', str(script), '--keys', keys_path, '--target', target]
        log(f'  → 執行：{" ".join(cmd)}')
        subprocess.run(cmd)
    finally:
        try:
            os.unlink(keys_path)
        except OSError:
            pass


def pre_push() -> int:
    if os.environ.get('JIRA_SKILL_SKIP_HOOK'):
        return 0

    refs = parse_push_refs()
    if not refs:
        return 0
    commits = collect_commits(refs)
    if not commits:
        return 0

    keys = extract_jira_keys(commits)

    log('')
    log(f'=== claude-jira-skill: pre-push 整理（{len(commits)} commits） ===')
    log('（關閉：export JIRA_SKILL_SKIP_HOOK=1）')

    if not keys:
        log('')
        log('⚠ 沒有 commit 提到 Jira key（建議 commit message 帶 [PROJ-123] 之類）')
        log('  本次 commits：')
        for c in commits[:10]:
            log(f'    {c["sha"][:7]} {c["subject"]}')
        if len(commits) > 10:
            log(f'    ... 還有 {len(commits) - 10} 個')
        log('')
        log('  如果這些是 Jira 上沒有的工作，記得：')
        log('    - 補建 subtask： python3 .../add_subtask.py <MODULE> --summary "..." --hours 2.5')
        log('  push 繼續（純提示）')
        return 0

    # 連 Jira 查狀態（連線失敗就靜默放行）
    try:
        from jira_client import JiraClient
        jc = JiraClient.from_env()
    except Exception as e:
        log(f'⚠ Jira 連線失敗（{e}），跳過互動，push 繼續')
        return 0

    log('')
    log(f'本次 push 提到 {len(keys)} 個 Jira ticket：')
    statuses = {}
    for k in keys:
        try:
            statuses[k] = jc.get_status(k)
        except Exception:
            statuses[k] = '?'
        log(f'  - {k} [{statuses[k]}]')

    log('')
    log('要整理這些 ticket 嗎？')
    log('  [t] 推到「測試中」')
    log('  [d] 推到「完成」（會觸發 cascade）')
    log('  [s] 跳過，繼續 push')
    log('  [a] 中止 push（回去整理 Jira）')
    choice = tty_read('  選擇 [s]: ', 's').lower()

    if choice.startswith('a'):
        log('  → 中止 push')
        return 1
    if choice.startswith('t'):
        run_state_transition(keys, '測試中')
    elif choice.startswith('d'):
        run_state_transition(keys, '完成')
    else:
        log('  → 跳過，繼續 push')

    return 0


def main() -> int:
    if len(sys.argv) < 2:
        log('用法: git_hook.py <pre-push>')
        return 1
    mode = sys.argv[1]
    if mode == 'pre-push':
        return pre_push()
    log(f'未知 hook: {mode}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
