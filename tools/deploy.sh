#!/usr/bin/env bash
# =============================================================================
# deploy.sh — 部署/更新脚本
#
# 目录结构：
#   /opt/src/info   源代码目录（git 仓库，拉取 + 构建）
#   /opt/info       部署运行目录（后端代码 + frontend/dist + .venv + 配置）
#
# 使用方式：
#   bash /opt/src/info/tools/deploy.sh              # 完整部署
#   bash /opt/src/info/tools/deploy.sh --skip-build  # 跳过前端构建
#   bash /opt/src/info/tools/deploy.sh --skip-migrate
#
# 前提条件：
#   1. 服务器上已按 DEPLOY.md 完成首次部署（venv、数据库、systemd 服务）
#   2. /opt/info 中存在 db_config.ini / llm_config.ini / .env 等配置文件
# =============================================================================

set -euo pipefail

# ── 颜色输出 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── 参数解析 ──────────────────────────────────────────────────────────────────
SKIP_BUILD=false
SKIP_MIGRATE=false

for arg in "$@"; do
    case "$arg" in
        --skip-build)   SKIP_BUILD=true ;;
        --skip-migrate) SKIP_MIGRATE=true ;;
        --help|-h)
            echo "Usage: bash tools/deploy.sh [--skip-build] [--skip-migrate]"
            exit 0
            ;;
        *) log_warn "未知参数: $arg，忽略" ;;
    esac
done

# ── 路径配置 ──────────────────────────────────────────────────────────────────
SRC_DIR="/opt/src/info"          # git 仓库，拉取 + 构建
DEPLOY_DIR="/opt/info"           # 运行目录，接收部署产物
VENV_DIR="$DEPLOY_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
LOGS_DIR="$DEPLOY_DIR/logs"

# 部署目录中需要保留的私密配置（不在 git 中）
LOCAL_CONFIGS=(
    "db_config.ini"
    "llm_config.ini"
    ".env"
    "frontend/.env"
)

# systemd 服务名
BACKEND_SERVICE="info-backend"
SCHEDULER_SERVICE="info-scheduler"

# ── 前置检查 ──────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  Info 项目部署脚本"
echo "  源码目录: $SRC_DIR"
echo "  部署目录: $DEPLOY_DIR"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 检查必要工具
for cmd in git rsync python3; do
    if ! command -v "$cmd" &>/dev/null; then
        log_error "缺少必要命令: $cmd（请先安装）"
        exit 1
    fi
done

# 检查源码目录
if [[ ! -d "$SRC_DIR/.git" ]]; then
    log_error "源码目录不存在或不是 git 仓库: $SRC_DIR"
    log_error "请先执行: git clone <repo> $SRC_DIR"
    exit 1
fi

# 检查虚拟环境（在部署目录中）
if [[ ! -f "$PYTHON" ]]; then
    log_error "虚拟环境不存在: $VENV_DIR"
    log_error "请先按 DEPLOY.md 完成首次部署"
    exit 1
fi

mkdir -p "$LOGS_DIR"

# ── Step 1: 拉取最新源码 ──────────────────────────────────────────────────────
log_info "Step 1: 拉取最新源码（$SRC_DIR）..."

cd "$SRC_DIR"
BEFORE_COMMIT=$(git rev-parse HEAD)
git fetch origin main
git reset --hard origin/main
AFTER_COMMIT=$(git rev-parse HEAD)

if [[ "$BEFORE_COMMIT" == "$AFTER_COMMIT" ]]; then
    log_ok "代码已是最新（${AFTER_COMMIT:0:7}）"
else
    log_ok "代码已更新: ${BEFORE_COMMIT:0:7} → ${AFTER_COMMIT:0:7}"
    echo ""
    log_info "本次更新内容:"
    git log --oneline "$BEFORE_COMMIT..$AFTER_COMMIT"
    echo ""
fi

# ── Step 2: 构建前端 ──────────────────────────────────────────────────────────
if [[ "$SKIP_BUILD" == "true" ]]; then
    log_warn "Step 2: 跳过前端构建（--skip-build）"
else
    log_info "Step 2: 构建前端（$SRC_DIR/frontend）..."

    FRONTEND_SRC="$SRC_DIR/frontend"
    if [[ ! -d "$FRONTEND_SRC" ]]; then
        log_warn "frontend 目录不存在，跳过构建"
    else
        cd "$FRONTEND_SRC"

        # 确保使用部署目录的 .env（如果存在），否则用源码目录的 .env.example
        if [[ -f "$DEPLOY_DIR/frontend/.env" ]]; then
            cp "$DEPLOY_DIR/frontend/.env" "$FRONTEND_SRC/frontend/.env" 2>/dev/null || \
            cp "$DEPLOY_DIR/frontend/.env" "$FRONTEND_SRC/.env"
            log_info "  使用部署目录的 frontend/.env"
        fi

        # 优先用 bun，其次 npm
        if command -v bun &>/dev/null; then
            log_info "  安装依赖（bun）..."
            bun install --frozen-lockfile 2>/dev/null || bun install
            log_info "  执行 bun run build..."
            bun run build
        elif command -v npm &>/dev/null; then
            log_info "  安装依赖（npm）..."
            npm ci --silent 2>/dev/null || npm install --silent
            log_info "  执行 npm run build..."
            npm run build
        else
            log_error "未找到 bun 或 npm，无法构建前端"
            exit 1
        fi

        log_ok "前端构建完成（$FRONTEND_SRC/dist/）"
        cd "$SRC_DIR"
    fi
fi

# ── Step 3: 同步后端代码到部署目录 ────────────────────────────────────────────
log_info "Step 3: 同步后端代码到部署目录（$DEPLOY_DIR）..."

# 使用 rsync 同步，排除配置文件、venv、日志、缓存等
rsync -av --delete \
    --exclude=".git" \
    --exclude=".venv" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.pyo" \
    --exclude="logs/" \
    --exclude="db.sqlite3" \
    --exclude="db_config.ini" \
    --exclude="llm_config.ini" \
    --exclude=".env" \
    --exclude="frontend/.env" \
    --exclude="frontend/node_modules" \
    --exclude="frontend/dist" \
    --exclude="tools/" \
    "$SRC_DIR/" "$DEPLOY_DIR/" \
    | grep -v "^sending\|^sent\|^total" || true

log_ok "后端代码同步完成"

# ── Step 4: 部署前端 dist ─────────────────────────────────────────────────────
if [[ "$SKIP_BUILD" != "true" ]]; then
    log_info "Step 4: 部署前端 dist..."

    DIST_SRC="$SRC_DIR/frontend/dist"
    DIST_DST="$DEPLOY_DIR/frontend/dist"

    if [[ -d "$DIST_SRC" ]]; then
        mkdir -p "$DIST_DST"
        rsync -a --delete "$DIST_SRC/" "$DIST_DST/"
        log_ok "前端 dist 部署完成（$DIST_DST）"
    else
        log_warn "前端 dist 不存在，跳过（构建可能未成功）"
    fi
else
    log_warn "Step 4: 跳过前端 dist 部署（--skip-build）"
fi

# ── Step 5: 安装/更新 Python 依赖 ─────────────────────────────────────────────
log_info "Step 5: 更新 Python 依赖..."

cd "$DEPLOY_DIR"
"$PIP" install -r requirements.txt -q --disable-pip-version-check
log_ok "Python 依赖更新完成"

# ── Step 6: 数据库迁移 ────────────────────────────────────────────────────────
if [[ "$SKIP_MIGRATE" == "true" ]]; then
    log_warn "Step 6: 跳过数据库迁移（--skip-migrate）"
else
    log_info "Step 6: 执行数据库迁移..."

    PENDING=$("$PYTHON" manage.py showmigrations --list 2>/dev/null | grep "\[ \]" || true)
    if [[ -n "$PENDING" ]]; then
        log_info "发现待执行的迁移:"
        echo "$PENDING"
        "$PYTHON" manage.py migrate --no-input
        log_ok "数据库迁移完成"
    else
        log_ok "数据库已是最新，无需迁移"
    fi
fi

# ── Step 7: 重启服务 ──────────────────────────────────────────────────────────
log_info "Step 7: 重启 systemd 服务..."

SUDO_CMD=""
[[ $EUID -ne 0 ]] && SUDO_CMD="sudo"

for svc in "$BACKEND_SERVICE" "$SCHEDULER_SERVICE"; do
    if $SUDO_CMD systemctl is-enabled "$svc" &>/dev/null 2>&1; then
        $SUDO_CMD systemctl restart "$svc"
        sleep 2
        if $SUDO_CMD systemctl is-active "$svc" &>/dev/null; then
            log_ok "  $svc 重启成功"
        else
            log_error "  $svc 重启失败！查看: journalctl -u $svc -n 50"
        fi
    else
        log_warn "  $svc 未注册为 systemd 服务，跳过"
    fi
done

# ── Step 8: 健康检查 ──────────────────────────────────────────────────────────
log_info "Step 8: 健康检查..."
sleep 3

CHECK_RESULT=$("$PYTHON" manage.py check 2>&1 | tail -1)
log_info "Django check: $CHECK_RESULT"

if curl -sf "http://127.0.0.1:8000/api/platforms/" -o /dev/null --max-time 5 2>/dev/null; then
    log_ok "后端 API 响应正常（/api/platforms/）"
else
    log_warn "后端 API 无响应（服务可能还在启动中，请稍后检查）"
fi

# ── 完成摘要 ──────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo -e "${GREEN}  部署完成！${NC}"
echo "  提交: ${AFTER_COMMIT:0:7}"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""
echo "常用命令:"
echo "  查看后端日志:   tail -f $LOGS_DIR/app.log"
echo "  手动触发抓取:   $PYTHON manage.py run_all_tasks --parallel"
echo "  手动触发分析:   $PYTHON manage.py extract_keywords_llm --v2 --force"
echo "  服务状态:       sudo systemctl status $BACKEND_SERVICE $SCHEDULER_SERVICE"
echo ""
