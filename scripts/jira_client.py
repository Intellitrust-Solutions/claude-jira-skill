#!/usr/bin/env python3
"""
Jira API 共用 client：
- 從 .env / 環境變數 / CLAUDE.md 讀取憑證
- 封裝 api(method, path, body)
- 提供 whoami / issuetypes / transitions 查詢
- 中文 payload 自動用 ensure_ascii=True

用法：
    from jira_client import JiraClient
    jc = JiraClient.from_env()
    jc.whoami()
    jc.issuetypes()
    jc.api('GET', '/rest/api/3/issue/PROJECT-XXX')

CLI:
    python3 jira_client.py whoami
    python3 jira_client.py issuetypes
    python3 jira_client.py transitions PROJECT-XXX
"""
import os, json, base64, sys, time, subprocess, urllib.request, urllib.error
from pathlib import Path

# 強制 stdout UTF-8，避免中文在某些環境壞掉
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def output_path(filename: str) -> Path:
    """所有腳本輸出統一寫到 ~/.cache/jira-skill/，避免 /tmp 被同機其他使用者讀取。"""
    cache = Path.home() / '.cache' / 'jira-skill'
    cache.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(cache, 0o700)
    except Exception:
        pass
    p = cache / filename
    return p


def resolve_epic_key(cli_value: str | None) -> str:
    """Epic Key 解析優先序：CLI 參數 > JIRA_EPIC_KEY env var。都沒有 raise。"""
    val = cli_value or os.environ.get('JIRA_EPIC_KEY')
    if not val:
        raise SystemExit(
            '缺少 Epic Key：請以 CLI 參數提供，或在專案 .env 設 JIRA_EPIC_KEY=...'
        )
    return val


def check_update(force: bool = False, verbose: bool = False) -> tuple[bool, str]:
    """
    檢查 skill 是否有新版（被動通知，不自動拉）。
    - 24h 快取（~/.cache/jira-skill/.update_check），避免每次呼叫都打 GitHub
    - JIRA_SKILL_NO_UPDATE_CHECK=1 可關閉
    - 任何錯誤都 silent skip（離線 / 非 git repo / git 沒裝）
    回傳 (有新版, 訊息)。
    """
    if not force and os.environ.get('JIRA_SKILL_NO_UPDATE_CHECK'):
        return False, ''

    skill_dir = Path(__file__).resolve().parent.parent
    if not (skill_dir / '.git').exists():
        return False, ''

    cache_file = Path.home() / '.cache' / 'jira-skill' / '.update_check'
    now = int(time.time())
    if not force and cache_file.exists():
        try:
            if now - int(cache_file.read_text().strip()) < 86400:
                return False, ''
        except Exception:
            pass

    try:
        local = subprocess.run(
            ['git', '-C', str(skill_dir), 'rev-parse', 'HEAD'],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        remote_out = subprocess.run(
            ['git', '-C', str(skill_dir), 'ls-remote', 'origin', 'HEAD'],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
        if not local or not remote_out:
            return False, ''
        remote = remote_out.split()[0]

        # 寫快取（無論結果都更新時間）
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(str(now))
        try:
            cache_file.chmod(0o600)
        except Exception:
            pass

        if local != remote:
            return True, (
                f'⚠ skill 有新版可更新（local: {local[:7]} → remote: {remote[:7]}）\n'
                f'  更新指令：curl -sL https://raw.githubusercontent.com/Intellitrust-Solutions/claude-jira-skill/main/install.sh | bash\n'
                f'  或：git -C {skill_dir} pull'
            )
        if verbose:
            return False, f'✓ skill 已是最新版（{local[:7]}）'
        return False, ''
    except Exception:
        return False, ''


class JiraClient:
    def __init__(self, base_url: str, email: str, token: str):
        if not base_url.startswith('https://'):
            raise RuntimeError(
                f'JIRA_BASE_URL 必須以 https:// 開頭（避免 token 以明文傳輸），'
                f'目前為: {base_url}'
            )
        self.base = base_url.rstrip('/')
        self.headers = {
            'Authorization': 'Basic ' + base64.b64encode(f'{email}:{token}'.encode()).decode(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        self._me = None

    @classmethod
    def from_env(cls, env_file: str | None = None) -> 'JiraClient':
        # 優先序：參數指定 .env > JIRA_ENV_FILE > 當前目錄 .env > 全域 ~/.claude/skills/jira/.env > 環境變數
        # JIRA_EPIC_KEY 也會一併讀入 os.environ，供 resolve_epic_key() 使用
        vars_needed = ['JIRA_BASE_URL', 'JIRA_EMAIL', 'JIRA_API_TOKEN']
        optional_vars = ['JIRA_EPIC_KEY', 'JIRA_WORKING_DAYS']
        all_vars = vars_needed + optional_vars
        values = {k: os.environ.get(k) for k in all_vars}

        global_env = Path.home() / '.claude' / 'skills' / 'jira' / '.env'
        candidates = [env_file, os.environ.get('JIRA_ENV_FILE'), '.env', str(global_env)]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                for line in Path(candidate).read_text(encoding='utf-8').splitlines():
                    if '=' in line and not line.strip().startswith('#'):
                        k, v = line.split('=', 1)
                        k = k.strip()
                        if k in all_vars and not values.get(k):
                            values[k] = v.strip().strip('"').strip("'")
                # 讀完一個檔就停（依優先序）
                break

        # JIRA_EPIC_KEY / JIRA_WORKING_DAYS 注入 os.environ，讓其他模組讀得到
        for k in optional_vars:
            if values.get(k) and not os.environ.get(k):
                os.environ[k] = values[k]

        missing = [k for k in vars_needed if not values.get(k)]
        if missing:
            raise RuntimeError(f'缺少 Jira 憑證: {", ".join(missing)}')
        return cls(values['JIRA_BASE_URL'], values['JIRA_EMAIL'], values['JIRA_API_TOKEN'])

    def api(self, method: str, path: str, body=None):
        url = f'{self.base}{path}'
        data = json.dumps(body, ensure_ascii=True).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode()
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors='replace')
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {'error': raw}

    def whoami(self) -> dict:
        if self._me:
            return self._me
        code, body = self.api('GET', '/rest/api/3/myself')
        if code == 401:
            raise RuntimeError(
                'Jira 401：憑證無效（JIRA_EMAIL 或 JIRA_API_TOKEN 錯誤 / token 過期）。'
                '到 https://id.atlassian.com/manage-profile/security/api-tokens 重新申請'
            )
        if code == 403:
            raise RuntimeError(f'Jira 403：權限不足。回應：{body}')
        if code != 200 or 'accountId' not in body:
            raise RuntimeError(f'Jira 連線異常（status={code}）：{body}')
        self._me = {'accountId': body['accountId'], 'name': body.get('displayName')}
        return self._me

    def issuetypes(self) -> list[dict]:
        _, body = self.api('GET', '/rest/api/3/issuetype')
        return [{
            'id': t['id'], 'name': t['name'],
            'level': t.get('hierarchyLevel'), 'subtask': t.get('subtask', False),
        } for t in body]

    def transitions(self, key: str) -> list[dict]:
        _, body = self.api('GET', f'/rest/api/3/issue/{key}/transitions')
        return [{
            'id': t['id'], 'name': t['name'], 'to': t['to']['name'],
        } for t in body.get('transitions', [])]

    def get_status(self, key: str) -> str:
        _, body = self.api('GET', f'/rest/api/3/issue/{key}?fields=status')
        return body.get('fields', {}).get('status', {}).get('name', '')

    def is_mine(self, key: str) -> bool:
        _, body = self.api('GET', f'/rest/api/3/issue/{key}?fields=assignee,reporter')
        me = self.whoami()['accountId']
        f = body.get('fields', {})
        a = (f.get('assignee') or {}).get('accountId')
        r = (f.get('reporter') or {}).get('accountId')
        return a == me or r == me

    def assert_mine(self, key: str, action: str = '操作') -> None:
        """非自己的 issue 直接 raise，避免誤改他人項目。"""
        if not self.is_mine(key):
            _, body = self.api('GET', f'/rest/api/3/issue/{key}?fields=assignee,reporter,summary')
            f = body.get('fields', {})
            a = (f.get('assignee') or {}).get('displayName', '無')
            r = (f.get('reporter') or {}).get('displayName', '無')
            summary = f.get('summary', '')
            raise PermissionError(
                f'拒絕{action} {key}「{summary}」— assignee={a} / reporter={r}，皆非當前使用者。'
                f'若要強制執行請手動修改 issue 的 assignee 為自己。'
            )

    def selftest(self) -> dict:
        """連線自檢：驗證憑證 + accountId + Jira 站台可達。順便檢查 skill 是否有新版。"""
        me = self.whoami()
        result = {
            'base_url': self.base,
            'account_id': me['accountId'],
            'display_name': me['name'],
            'status': 'OK',
        }
        # 被動更新通知（24h cache，silent on error）
        has_update, msg = check_update()
        if has_update:
            print(msg, file=sys.stderr)
        return result


def _cli():
    if len(sys.argv) < 2:
        print('用法: python3 jira_client.py <whoami|issuetypes|transitions KEY|check-update>')
        sys.exit(1)
    cmd = sys.argv[1]
    # check-update 不需要 Jira 連線，先處理
    if cmd == 'check-update':
        has, msg = check_update(force=True, verbose=True)
        print(msg or '✓ 已是最新版')
        sys.exit(0 if not has else 1)
    jc = JiraClient.from_env()
    if cmd == 'whoami':
        print(json.dumps(jc.whoami(), ensure_ascii=False, indent=2))
    elif cmd == 'selftest':
        print(json.dumps(jc.selftest(), ensure_ascii=False, indent=2))
    elif cmd == 'check-mine':
        if len(sys.argv) < 3:
            print('需要 issue key'); sys.exit(1)
        key = sys.argv[2]
        try:
            jc.assert_mine(key, '檢查')
            print(f'✓ {key} 屬於你（assignee 或 reporter 是當前帳號）')
        except PermissionError as e:
            print(f'✗ {e}'); sys.exit(1)
    elif cmd == 'issuetypes':
        for t in jc.issuetypes():
            tag = 'subtask' if t['subtask'] else f'level={t["level"]}'
            print(f"{t['id']:6} | {t['name']:10} | {tag}")
    elif cmd == 'transitions':
        if len(sys.argv) < 3:
            print('需要 issue key'); sys.exit(1)
        for t in jc.transitions(sys.argv[2]):
            print(f"{t['id']:4} | {t['name']:16} -> {t['to']}")
    else:
        print(f'未知指令: {cmd}'); sys.exit(1)


if __name__ == '__main__':
    _cli()
