#!/usr/bin/env bash
# =============================================================================
# deploy.sh — 部署/更新脚本
#
# 用途：从 GitHub 拉取最新代码，保留本地配置，构建前端，执行迁移，重启服务
#
# 使用方式：
#   bash tools/deploy.sh           # 完整部署（生产推荐）
#   bash tools/deploy.sh --skip-build   # 跳过前端构建（仅更新后端）
#   bash tools/deploy.sh --skip-migrate # 跳过数据库迁移
#
# 前提条件：
#   1. 服务器上已按 DEPLOY.md 完成首次部署
#   2. systemd 服务 info-backend / info-scheduler 已配置
#   3. 本地存在 db_config.ini / llm_config.ini / .env 等配置文件
# =============================================================================

set -euo pipefail

# ── 颜色输出 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

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

# ── 路径配置（根据实际部署路径调整）─────────────────────────────────────────
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$DEPLOY_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
FRONTEND_DIR="$DEPLOY_DIR/frontend"
LOGS_DIR="$DEPLOY_DIR/logs"

# 需要保留的本地配置文件（不在 git 中的私密配置）
LOCAL_CONFIGS=(
    "db_config.ini"
    "llm_config.ini"
    ".env"
    "frontend/.env"
)

# systemd 服务名（不存在则跳过重启）
BACKEND_SERVICE="info-backend"
SCHEDULER_SERVICE="info-scheduler"

# ── 前置检查 ──────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  Info 项目部署脚本"
echo "  路径: $DEPLOY_DIR"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

cd "$DEPLOY_DIR"

# 检查必要工具
for cmd in git python3; do
    if ! command -v "$cmd" &>/dev/null; then
        log_error "缺少必要命令: $cmd"
        exit 1
    fi
done

# 检查虚拟环境
if [[ ! -f "$PYTHON" ]]; then
    log_error "虚拟环境不存在: $VENV_DIR"
    log_error "请先按 DEPLOY.md 完成首次部署"
    exit 1
fi

# 检查必要配置文件
MISSING_CONFIGS=()
for cfg in "${LOCAL_CONFIGS[@]}"; do
    if [[ ! -f "$DEPLOY_DIR/$cfg" ]]; then
        MISSING_CONFIGS+=("$cfg")
    fi
done
if [[ ${#MISSING_CONFIGS[@]} -gt 0 ]]; then
    log_warn "以下配置文件不存在（首次部署需手动创建）:"
    for cfg in "${MISSING_CONFIGS[@]}"; do
        log_warn "  - $cfg"
    done
fi

mkdir -p "$LOGS_DIR"

# ── Step 1: 备份本地配置文件 ──────────────────────────────────────────────────
log_info "Step 1: 备份本地配置文件..."

BACKUP_DIR="/tmp/info_deploy_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

BACKED_UP=0
for cfg in "${LOCAL_CONFIGS[@]}"; do
    src="$DEPLOY_DIR/$cfg"
    if [[ -f "$src" ]]; then
        # 保留目录结构
        dst_dir="$BACKUP_DIR/$(dirname "$cfg")"
        mkdir -p "$dst_dir"
        cp "$src" "$dst_dir/"
        log_ok "  已备份: $cfg → $BACKUP_DIR/$cfg"
        BACKED_UP=$((BACKED_UP + 1))
    fi
done

log_ok "备份完成（$BACKED_UP 个文件 → $BACKUP_DIR）"

# ── Step 2: 拉取最新代码 ──────────────────────────────────────────────────────
log_info "Step 2: 从 GitHub 拉取最新代码..."

BEFORE_COMMIT=$(git rev-parse HEAD)
git fetch origin main
git reset --hard origin/main
AFTER_COMMIT=$(git rev-parse HEAD)

if [[ "$BEFORE_COMMIT" == "$AFTER_COMMIT" ]]; then
    log_ok "代码已是最新（$AFTER_COMMIT）"
else
    log_ok "代码已更新: ${BEFORE_COMMIT:0:7} → ${AFTER_COMMIT:0:7}"
    echo ""
    log_info "本次更新内容:"
    git log --oneline "$BEFORE_COMMIT..$AFTER_COMMIT"
    echo ""
fi

# ── Step 3: 还原本地配置文件 ──────────────────────────────────────────────────
log_info "Step 3: 还原本地配置文件..."

for cfg in "${LOCAL_CONFIGS[@]}"; do
    src="$BACKUP_DIR/$cfg"
    dst="$DEPLOY_DIR/$cfg"
    if [[ -f "$src" ]]; then
        # 确保目标目录存在
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
        log_ok "  已还原: $cfg"
    fi
done

# ── Step 4: 安装/更新 Python 依赖 ─────────────────────────────────────────────
log_info "Step 4: 更新 Python 依赖..."

"$PIP" install -r requirements.txt -q --disable-pip-version-check
log_ok "Python 依赖更新完成"

# ── Step 5: 数据库迁移 ────────────────────────────────────────────────────────
if [[ "$SKIP_MIGRATE" == "true" ]]; then
    log_warn "Step 5: 跳过数据库迁移（--skip-migrate）"
else
    log_info "Step 5: 执行数据库迁移..."

    # 检查是否有新的迁移需要执行
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

# ── Step 6: Django 静态文件收集（可选）───────────────────────────────────────
if [[ -d "$DEPLOY_DIR/staticfiles" ]] || grep -q "STATIC_ROOT" "$DEPLOY_DIR/django_api/settings.py" 2>/dev/null; then
    log_info "Step 6: 收集静态文件..."
    "$PYTHON" manage.py collectstatic --no-input -v 0 2>/dev/null || log_warn "collectstatic 跳过（未配置 STATIC_ROOT）"
fi

# ── Step 7: 构建前端 ──────────────────────────────────────────────────────────
if [[ "$SKIP_BUILD" == "true" ]]; then
    log_warn "Step 7: 跳过前端构建（--skip-build）"
else
    log_info "Step 7: 构建前端..."

    if [[ ! -d "$FRONTEND_DIR" ]]; then
        log_warn "frontend 目录不存在，跳过构建"
    else
        cd "$FRONTEND_DIR"

        # 优先用 bun，其次 npm
        if command -v bun &>/dev/null; then
            log_info "  使用 bun 安装依赖..."
            bun install --frozen-lockfile 2>/dev/null || bun install
            log_info "  执行 bun run build..."
            bun run build
        elif command -v npm &>/dev/null; then
            log_info "  使用 npm 安装依赖..."
            npm ci --silent 2>/dev/null || npm install --silent
            log_info "  执行 npm run build..."
            npm run build
        else
            log_error "未找到 bun 或 npm，无法构建前端"
            exit 1
        fi

        cd "$DEPLOY_DIR"
log_ok "前端构建完成（dist/ 已更新）"
    fi
fi

# ── Step 8: 重启服务 ──────────────────────────────────────────────────────────
log_info "Step 8: 重启服务..."

restart_service() {
    local svc="$1"
    if systemctl is-enabled "$svc" &>/dev/null 2>&1; then
        systemctl restart "$svc"
        sleep 2
        if systemctl is-active "$svc" &>/dev/null; then
            log_ok "  $svc 重启成功"
        else
            log_error "  $svc 重启失败！查看日志: journalctl -u $svc -n 50"
            return 1
        fi
    else
        log_warn "  $svc 未注册为 systemd 服务，跳过"
    fi
}

# 需要 root/sudo 才能操作 systemd
if [[ $EUID -eq 0 ]] || sudo -n systemctl status "$BACKEND_SERVICE" &>/dev/null 2>&1; then
    SUDO_CMD=""
    [[ $EUID -ne 0 ]] && SUDO_CMD="sudo"

    $SUDO_CMD systemctl restart "$BACKEND_SERVICE"  2>/dev/null && log_ok "  $BACKEND_SERVICE 重启成功" \
        || log_warn "  $BACKEND_SERVICE 未配置或重启失败"

    $SUDO_CMD systemctl restart "$SCHEDULER_SERVICE" 2>/dev/null && log_ok "  $SCHEDULER_SERVICE 重启成功" \
        || log_warn "  $SCHEDULER_SERVICE 未配置或重启失败"
else
    log_warn "无 sudo 权限，跳过 systemd 重启"
    log_warn "请手动执行:"
    log_warn "  sudo systemctl restart $BACKEND_SERVICE $SCHEDULER_SERVICE"
fi

# ── Step 9: 健康检查 ──────────────────────────────────────────────────────────
log_info "Step 9: 健康检查..."

sleep 3  # 等待服务完全启动

# Django 检查
if "$PYTHON" manage.py check --deploy 2>&1 | grep -q "System check identified no issues"; then
    log_ok "Django system check 通过"
else
    # 非严重检查，只警告
    CHECK_RESULT=$("$PYTHON" manage.py check 2>&1 | tail -1)
    log_warn "Django check: $CHECK_RESULT"
fi

# HTTP 健康探测（如果后端服务在运行）
if curl -sf "http://127.0.0.1:8000/api/platforms/" -o /dev/null --max-time 5 2>/dev/null; then
    log_ok "后端 API 响应正常（/api/platforms/）"
else
    log_warn "后端 API 无响应（服务可能未完全启动，请稍后检查）"
fi

# ── 完成摘要 ──────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo -e "${GREEN}  部署完成！${NC}"
echo "  提交: ${AFTER_COMMIT:0:7}"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  备份: $BACKUP_DIR"
echo "=========================================="
echo ""
echo "常用命令:"
echo "  查看后端日志:    tail -f $LOGS_DIR/app.log"
echo "  手动触发抓取:    $PYTHON manage.py run_all_tasks --parallel"
echo "  手动触发分析:    $PYTHON manage.py extract_keywords_llm --v2 --force"
echo "  查看服务状态:    sudo systemctl status $BACKEND_SERVICE $SCHEDULER_SERVICE"
echo ""
