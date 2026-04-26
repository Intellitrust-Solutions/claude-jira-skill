#!/usr/bin/env bash
# claude-jira-skill 安裝腳本
#
# 兩種使用方式：
#   1) 遠端一鍵安裝（自動 clone + 互動填憑證）：
#      curl -sL https://raw.githubusercontent.com/Intellitrust-Solutions/claude-jira-skill/main/install.sh | bash
#
#   2) 本地安裝（已 clone 完，在 repo 目錄裡跑）：
#      ./install.sh
#
# 環境變數覆寫：
#   REPO_URL       — fork 自用時指定來源 repo
#   INSTALL_DIR    — 改裝到非預設位置
#   NONINTERACTIVE — 設為任何值跳過所有互動 prompt（給 CI / 已有 .env）

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Intellitrust-Solutions/claude-jira-skill.git}"
DEFAULT_TARGET="${HOME}/.claude/skills/jira"
TARGET_DIR="${INSTALL_DIR:-$DEFAULT_TARGET}"
NONINTERACTIVE="${NONINTERACTIVE:-}"

echo "==> claude-jira-skill 安裝"
echo

# ──────── 偵測本地 / 遠端模式 ────────
SCRIPT_PATH="${BASH_SOURCE[0]:-}"
if [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
    if [ -d "$SCRIPT_DIR/.git" ] || [ -f "$SCRIPT_DIR/SKILL.md" ]; then
        MODE="local"
        TARGET_DIR="$SCRIPT_DIR"
    fi
fi
MODE="${MODE:-remote}"

# ──────── 偵測互動環境（curl|bash 也能讀使用者輸入） ────────
INTERACTIVE=1
if [ -n "$NONINTERACTIVE" ]; then
    INTERACTIVE=0
elif ! [ -t 0 ] && ! [ -r /dev/tty ]; then
    INTERACTIVE=0
fi

read_tty() {
    # $1 = prompt, $2 = var name, $3 = (optional) "secret" 隱藏輸入
    local prompt="$1" varname="$2" secret="${3:-}"
    if [ "$secret" = "secret" ]; then
        read -r -s -p "$prompt" "$varname" < /dev/tty
        echo
    else
        read -r -p "$prompt" "$varname" < /dev/tty
    fi
}

# ──────── Python 檢查 ────────
if ! command -v python3 >/dev/null 2>&1; then
    echo "✗ 找不到 python3，請先安裝 Python 3.7+"
    exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PY_VER"

# ──────── 遠端模式：clone 到目標目錄 ────────
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
else
    echo "✓ 本地模式: $TARGET_DIR"
fi

cd "$TARGET_DIR"

# ──────── Phase 1: 個人憑證（全域 .env） ────────
ENV_FILE="$TARGET_DIR/.env"

if [ -f "$ENV_FILE" ] && grep -q "^JIRA_API_TOKEN=." "$ENV_FILE" 2>/dev/null; then
    echo "✓ .env 已存在且看起來已填，略過憑證輸入"
elif [ "$INTERACTIVE" = "1" ]; then
    echo
    echo "==> Phase 1：個人 Jira 憑證（會寫入 ${ENV_FILE}）"
    echo "    申請 token: https://id.atlassian.com/manage-profile/security/api-tokens"
    echo

    while true; do
        read_tty "JIRA_BASE_URL（例如 https://your-workspace.atlassian.net）: " JIRA_BASE_URL
        if [[ "$JIRA_BASE_URL" == https://* ]]; then
            break
        fi
        echo "  ✗ 必須以 https:// 開頭（避免 token 明文傳輸），請重輸入"
    done

    read_tty "JIRA_EMAIL: " JIRA_EMAIL
    read_tty "JIRA_API_TOKEN（輸入時不顯示）: " JIRA_API_TOKEN secret

    cat > "$ENV_FILE" <<EOF
# 由 install.sh 自動產生
JIRA_BASE_URL=$JIRA_BASE_URL
JIRA_EMAIL=$JIRA_EMAIL
JIRA_API_TOKEN=$JIRA_API_TOKEN
EOF
    chmod 600 "$ENV_FILE"
    echo "✓ 已寫入 ${ENV_FILE}（chmod 600）"
else
    if [ ! -f "$ENV_FILE" ]; then
        cp .env.example "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        echo "✓ 非互動模式，已從 .env.example 建立 ${ENV_FILE}，請手動編輯"
    fi
fi

# ──────── 跑 selftest 驗證憑證 ────────
echo
echo "==> 驗證憑證..."
if python3 "$TARGET_DIR/scripts/jira_client.py" selftest; then
    echo "✓ Jira 連線 OK"
    SELFTEST_OK=1
else
    echo "✗ selftest 失敗，請檢查 $ENV_FILE 後再執行："
    echo "    python3 $TARGET_DIR/scripts/jira_client.py selftest"
    SELFTEST_OK=0
fi

# ──────── Phase 2: 專案 Epic Key（寫入專案 CLAUDE.md） ────────
if [ "$INTERACTIVE" = "1" ] && [ "$SELFTEST_OK" = "1" ]; then
    echo
    echo "==> Phase 2：要不要順便為某個專案設定 Epic Key？"
    echo "    （Epic Key 會寫進該專案的 CLAUDE.md，不寫全域）"
    read_tty "設定專案？[y/N]: " SETUP_PROJECT
    if [[ "$SETUP_PROJECT" =~ ^[Yy]$ ]]; then
        # 預設用當前 invoking 目錄（curl|bash 跑的時候 PWD 是使用者所在目錄）
        DEFAULT_PROJECT="$OLDPWD"
        [ -z "$DEFAULT_PROJECT" ] && DEFAULT_PROJECT="$PWD"
        # 但別把 skill 自己當專案
        if [ "$DEFAULT_PROJECT" = "$TARGET_DIR" ]; then
            DEFAULT_PROJECT="$HOME"
        fi

        read_tty "專案目錄路徑 [$DEFAULT_PROJECT]: " PROJECT_DIR
        PROJECT_DIR="${PROJECT_DIR:-$DEFAULT_PROJECT}"
        # 展開 ~
        PROJECT_DIR="${PROJECT_DIR/#\~/$HOME}"

        if [ ! -d "$PROJECT_DIR" ]; then
            echo "✗ 目錄不存在：${PROJECT_DIR}，跳過 Phase 2"
        else
            read_tty "Epic Key（例如 PROJECT-491）: " EPIC_KEY
            if [ -n "$EPIC_KEY" ]; then
                # 先驗證屬主
                echo "→ 驗證 $EPIC_KEY 屬於你..."
                if python3 "$TARGET_DIR/scripts/jira_client.py" check-mine "$EPIC_KEY"; then
                    PROJECT_CLAUDE_MD="$PROJECT_DIR/CLAUDE.md"
                    EPIC_LINE="本專案 Jira Epic: $EPIC_KEY"
                    if [ -f "$PROJECT_CLAUDE_MD" ]; then
                        if grep -q "^本專案 Jira Epic:" "$PROJECT_CLAUDE_MD"; then
                            # 已有，提醒不覆寫
                            echo "⚠ $PROJECT_CLAUDE_MD 已有 Epic 設定，未覆寫。手動編輯確認："
                            grep "^本專案 Jira Epic:" "$PROJECT_CLAUDE_MD"
                        else
                            echo "" >> "$PROJECT_CLAUDE_MD"
                            echo "$EPIC_LINE" >> "$PROJECT_CLAUDE_MD"
                            echo "✓ 已附加到 $PROJECT_CLAUDE_MD"
                        fi
                    else
                        cat > "$PROJECT_CLAUDE_MD" <<EOF
# $(basename "$PROJECT_DIR")

$EPIC_LINE
EOF
                        echo "✓ 已建立 $PROJECT_CLAUDE_MD"
                    fi
                else
                    echo "✗ Epic 屬主驗證失敗，未寫入 CLAUDE.md。"
                    echo "  到 Jira 把該 Epic assignee 改成你，或換一個是你的 Epic 再跑："
                    echo "    python3 $TARGET_DIR/scripts/jira_client.py check-mine <KEY>"
                fi
            fi
        fi
    fi
fi

# ──────── 結束提示 ────────
echo
echo "==> 安裝完成"
echo "    Skill 路徑: $TARGET_DIR"
echo
if [ "$INTERACTIVE" != "1" ] || [ "$SELFTEST_OK" != "1" ]; then
    echo "==> 待辦"
    echo "    1. 編輯 $ENV_FILE 填入 JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN"
    echo "    2. 自檢： python3 $TARGET_DIR/scripts/jira_client.py selftest"
    echo "    3. 在每個用 skill 的專案 CLAUDE.md 寫入 Epic Key："
    echo "       本專案 Jira Epic: PROJECT-XXX"
else
    echo "==> 下一步"
    echo "    在 Claude Code 中對你的專案說：「分析 codebase 並在 Epic 底下建 module」"
fi
echo
