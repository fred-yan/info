# 部署文档

## 系统要求

- Linux (Ubuntu 22.04+ 推荐) 或 CentOS 8+
- Python 3.11+
- MySQL 5.7+ 或 8.0+
- Node.js 18+ (前端构建)
- Chromium (Playwright 依赖，用于网页抓取)
- 2GB+ 内存（Playwright + LLM 调用需要）

## 第一步：系统依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
  build-essential libmysqlclient-dev pkg-config \
  git curl wget

# 安装 Node.js (前端构建)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 或使用 bun (更快)
curl -fsSL https://bun.sh/install | bash
```

## 第二步：克隆代码

```bash
cd /opt
git clone git@github.com:fred-yan/info.git
cd info
```

## 第三步：Python 环境

```bash
# 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install openai pydantic gunicorn

# 安装 Playwright 浏览器
playwright install chromium
playwright install-deps
```

## 第四步：配置文件

```bash
# 数据库配置
cp db_config.ini.example db_config.ini
vim db_config.ini
# 填入: host, user, password, name 等

# LLM 配置
cp llm_config.ini.example llm_config.ini
vim llm_config.ini
# 填入: api_key (DeepSeek API Key)

# 前端配置
cp frontend/.env.example frontend/.env
# 默认 VITE_API_BASE_URL=/api 即可
```

### db_config.ini 示例

```ini
[database]
engine = django.db.backends.mysql
name = info_api
user = root
password = your-mysql-password
host = 127.0.0.1
port = 3306
charset = utf8mb4
connect_timeout = 10
read_timeout = 30
write_timeout = 30
```

### llm_config.ini 示例

```ini
[llm]
model = deepseek-v4-pro
api_key = sk-your-deepseek-api-key
base_url = https://api.deepseek.com
max_tokens = 16384
temperature = 0.1
batch_size = 30
```

## 第五步：数据库初始化

```bash
# 确保 MySQL 中已创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS info_api CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 执行 Django 迁移
python manage.py migrate
```

## 第六步：构建前端

```bash
cd frontend
bun install       # 或 npm install
bun run build     # 生成 dist/ 目录
cd ..
```

## 第七步：验证

```bash
# 测试后端能启动
python manage.py check

# 测试数据库连接
python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_api.settings'); django.setup(); from parser_api.models import Info; print(f'DB OK, articles: {Info.objects.count()}')"

# 测试 LLM 连接
python -c "from parser_api.llm_extractor_tiny import LLMConfig; print(f'LLM OK: model={LLMConfig.MODEL}')"

# 测试抓取功能
python manage.py run_all_tasks --platform pengpai
```

## 第八步：生产部署

### 方案 A：Gunicorn + Nginx（推荐）

#### 启动后端

```bash
# 创建 systemd 服务文件
sudo tee /etc/systemd/system/info-backend.service << 'EOF'
[Unit]
Description=Info Backend (Django + Gunicorn)
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/info
Environment="PATH=/opt/info/.venv/bin"
ExecStart=/opt/info/.venv/bin/gunicorn django_api.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 2 \
  --timeout 120 \
  --access-logfile /opt/info/logs/gunicorn_access.log \
  --error-logfile /opt/info/logs/gunicorn_error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable info-backend
sudo systemctl start info-backend
```

#### 启动定时调度器

```bash
sudo tee /etc/systemd/system/info-scheduler.service << 'EOF'
[Unit]
Description=Info Scheduler (APScheduler)
After=network.target mysql.service info-backend.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/info
Environment="PATH=/opt/info/.venv/bin"
ExecStart=/opt/info/.venv/bin/python manage.py run_scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable info-scheduler
sudo systemctl start info-scheduler
```

#### Nginx 配置

```bash
sudo tee /etc/nginx/sites-available/info << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或 IP

    # 前端静态文件
    location / {
        root /opt/info/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 10s;
        proxy_read_timeout 120s;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/info /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 方案 B：简单部署（开发/测试用）

```bash
# 后端（后台运行）
nohup python manage.py runserver 0.0.0.0:8000 > logs/backend.log 2>&1 &

# 调度器（后台运行）
nohup python manage.py run_scheduler > logs/scheduler.log 2>&1 &
```

## 第九步：日常运维

```bash
# 查看服务状态
sudo systemctl status info-backend
sudo systemctl status info-scheduler

# 查看日志
tail -f /opt/info/logs/app.log
journalctl -u info-backend -f
journalctl -u info-scheduler -f

# 手动触发一次全量抓取 + LLM 分析
source .venv/bin/activate
python manage.py run_all_tasks --parallel
python manage.py extract_keywords_llm --v2 --group domestic --force
python manage.py extract_keywords_llm --v2 --group international --force

# 更新代码
cd /opt/info
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
cd frontend && bun run build && cd ..
sudo systemctl restart info-backend
sudo systemctl restart info-scheduler
```

## 第十步：防火墙

```bash
# 只开放 80/443 端口
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

## 目录结构（部署后）

```
/opt/info/
├── .venv/                  # Python 虚拟环境
├── db_config.ini           # 数据库配置（不提交 git）
├── llm_config.ini          # LLM 配置（不提交 git）
├── logs/                   # 日志目录
│   ├── app.log
│   ├── gunicorn_access.log
│   └── gunicorn_error.log
├── frontend/
│   └── dist/               # 前端构建产物
├── django_api/             # Django 配置
├── parser_api/             # 后端核心逻辑
├── news_homepage_parser/   # 抓取器
└── manage.py
```

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `mysqlclient` 安装失败 | 缺少开发库 | `apt install libmysqlclient-dev` |
| Playwright 报错 | 缺少浏览器依赖 | `playwright install-deps` |
| 前端 502 | 后端未启动 | `systemctl start info-backend` |
| LLM 分析无结果 | API Key 无效 | 检查 `llm_config.ini` |
| 数据库连接超时 | MySQL 配置 | 检查 `db_config.ini` 中的 host/port |
| 抓取全部失败 | 服务器无外网 | 检查 DNS 和防火墙出站规则 |
