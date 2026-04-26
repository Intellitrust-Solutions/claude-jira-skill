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
    jc.api('GET', '/rest/api/3/issue/PROJECT-491')

CLI:
    python3 jira_client.py whoami
    python3 jira_client.py issuetypes
    python3 jira_client.py transitions PROJECT-491
"""
import os, json, base64, sys, urllib.request, urllib.error
from pathlib import Path

# 強制 stdout UTF-8，避免中文在某些環境壞掉
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


class JiraClient:
    def __init__(self, base_url: str, email: str, token: str):
        self.base = base_url.rstrip('/')
        self.headers = {
            'Authorization': 'Basic ' + base64.b64encode(f'{email}:{token}'.encode()).decode(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        self._me = None

    @classmethod
    def from_env(cls, env_file: str | None = None) -> 'JiraClient':
        # 優先序：參數指定 .env > 當前目錄 .env > 環境變數
        # 也可用 JIRA_ENV_FILE 環境變數指定額外路徑
        vars_needed = ['JIRA_BASE_URL', 'JIRA_EMAIL', 'JIRA_API_TOKEN']
        values = {k: os.environ.get(k) for k in vars_needed}

        candidates = [env_file, os.environ.get('JIRA_ENV_FILE'), '.env']
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                for line in Path(candidate).read_text(encoding='utf-8').splitlines():
                    if '=' in line and not line.strip().startswith('#'):
                        k, v = line.split('=', 1)
                        k = k.strip()
                        if k in vars_needed and not values.get(k):
                            values[k] = v.strip().strip('"').strip("'")
                break

        missing = [k for k, v in values.items() if not v]
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
        _, body = self.api('GET', '/rest/api/3/myself')
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
        """連線自檢：驗證憑證 + accountId + Jira 站台可達。"""
        me = self.whoami()
        return {
            'base_url': self.base,
            'account_id': me['accountId'],
            'display_name': me['name'],
            'status': 'OK',
        }


def _cli():
    if len(sys.argv) < 2:
        print('用法: python3 jira_client.py <whoami|issuetypes|transitions KEY>')
        sys.exit(1)
    jc = JiraClient.from_env()
    cmd = sys.argv[1]
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
