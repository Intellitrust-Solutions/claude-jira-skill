#!/usr/bin/env bash
# claude-jira-skill 安裝腳本
# 使用：./install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> claude-jira-skill 安裝"
echo "    路徑: $SCRIPT_DIR"
echo

# 1. Python 版本檢查
if ! command -v python3 >/dev/null 2>&1; then
    echo "✗ 找不到 python3"
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PY_VER"

# 2. 建立 .env（若不存在）
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✓ 已建立 .env（請編輯填入憑證）"
else
    echo "✓ .env 已存在，略過"
fi

# 3. 提示下一步
echo
echo "==> 下一步"
echo "    1. 編輯 .env 填入 JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN"
echo "       申請 token: https://id.atlassian.com/manage-profile/security/api-tokens"
echo
echo "    2. 執行自檢："
echo "       python3 scripts/jira_client.py selftest"
echo
echo "    3. 若要當作 Claude Code skill 使用，將此目錄連結到 ~/.claude/skills/jira"
echo "       ln -s \"$SCRIPT_DIR\" ~/.claude/skills/jira"
echo
