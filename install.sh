#!/usr/bin/env bash
# claude-jira-skill 安裝腳本
#
# 兩種使用方式：
#   1) 遠端一鍵安裝（自動 clone 到 ~/.claude/skills/jira）：
#      curl -sL https://raw.githubusercontent.com/Intellitrust-Solutions/claude-jira-skill/main/install.sh | bash
#
#   2) 本地安裝（已 clone 完，在 repo 目錄裡跑）：
#      ./install.sh

set -euo pipefail

# 可用環境變數覆寫（例如 fork 後自用）：
#   REPO_URL=https://github.com/your-org/your-fork.git curl -sL ... | bash
REPO_URL="${REPO_URL:-https://github.com/Intellitrust-Solutions/claude-jira-skill.git}"
DEFAULT_TARGET="${HOME}/.claude/skills/jira"
TARGET_DIR="${INSTALL_DIR:-$DEFAULT_TARGET}"

echo "==> claude-jira-skill 安裝"
echo

# 偵測模式：腳本本身是否在 git repo 裡 → 本地模式；否則遠端模式
SCRIPT_PATH="${BASH_SOURCE[0]:-}"
if [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
    if [ -d "$SCRIPT_DIR/.git" ] || [ -f "$SCRIPT_DIR/SKILL.md" ]; then
        MODE="local"
        TARGET_DIR="$SCRIPT_DIR"
    fi
fi
MODE="${MODE:-remote}"

# Python 檢查
if ! command -v python3 >/dev/null 2>&1; then
    echo "✗ 找不到 python3，請先安裝 Python 3.7+"
    exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PY_VER"

# 遠端模式：clone 到目標目錄
if [ "$MODE" = "remote" ]; then
    if ! command -v git >/dev/null 2>&1; then
        echo "✗ 找不到 git，請先安裝"
        exit 1
    fi

    if [ -d "$TARGET_DIR" ]; then
        echo "✓ 目錄已存在: $TARGET_DIR"
        if [ -d "$TARGET_DIR/.git" ]; then
            echo "  → 執行 git pull 更新"
            git -C "$TARGET_DIR" pull --ff-only
        else
            echo "✗ 目錄存在但不是 git repo，請手動處理: $TARGET_DIR"
            exit 1
        fi
    else
        mkdir -p "$(dirname "$TARGET_DIR")"
        echo "→ Clone 到: $TARGET_DIR"
        git clone "$REPO_URL" "$TARGET_DIR"
    fi
    cd "$TARGET_DIR"
else
    echo "✓ 本地模式: $TARGET_DIR"
    cd "$TARGET_DIR"
fi

# 建立 .env（若不存在）
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✓ 已建立 .env（請編輯填入憑證）"
else
    echo "✓ .env 已存在，略過"
fi

echo
echo "==> 安裝完成"
echo "    路徑: $TARGET_DIR"
echo
echo "==> 下一步"
echo "    1. 編輯 $TARGET_DIR/.env 填入個人憑證："
echo "       JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN"
echo "       申請 token: https://id.atlassian.com/manage-profile/security/api-tokens"
echo
echo "    2. 自檢："
echo "       python3 $TARGET_DIR/scripts/jira_client.py selftest"
echo
echo "    3. 在每個用 skill 的專案 CLAUDE.md 寫入該專案的 Epic Key："
echo "       本專案 Epic: PROJECT-XXX"
echo
