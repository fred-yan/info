# 运行命令手册

## 服务启动

```powershell
# 启动 Django 后端（含定时调度器）
.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000

# 启动前端开发服务器
cd frontend
bun run dev
```

## 平台抓取

```powershell
# 运行所有平台抓取（并行，默认排除LLM分析）
.venv\Scripts\python.exe manage.py run_all_tasks --parallel

# 运行所有任务（含LLM热点词分析）
.venv\Scripts\python.exe manage.py run_all_tasks --parallel --include-all

# 只运行指定平台
.venv\Scripts\python.exe manage.py run_all_tasks --platform ftchinese,kr36

# 顺序执行所有平台
.venv\Scripts\python.exe manage.py run_all_tasks
```

## LLM 热点词分析（两阶段流程）

```powershell
# 国内热点 - 两阶段流程（默认）
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group domestic --force

# 国际热点
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group international --force

# 自定义批次大小
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group domestic --batch-size 20 --force

# 使用旧版一阶段流程（兼容）
.venv\Scripts\python.exe manage.py extract_keywords_llm --group domestic --force
```

## 提示词调试

```powershell
# 打印阶段1提示词（短语提取）
.venv\Scripts\python.exe manage.py extract_keywords_llm --debug-v2 --stage 1 --batch-size 10

# 打印阶段2提示词（全局归纳）
.venv\Scripts\python.exe manage.py extract_keywords_llm --debug-v2 --stage 2

# 导出提示词到文件（方便复制到 DeepSeek 界面调试）
.venv\Scripts\python.exe manage.py extract_keywords_llm --debug-v2 --stage 1 --dump-prompt stage1.txt
.venv\Scripts\python.exe manage.py extract_keywords_llm --debug-v2 --stage 2 --dump-prompt stage2.txt

# 阶段1输出转换为阶段2输入
.venv\Scripts\python.exe tools/stage1_to_stage2.py batch1.json --output stage2_input.txt
```

## 定时调度器

```powershell
# 独立启动定时调度器（不启动 Web 服务）
.venv\Scripts\python.exe manage.py run_scheduler

# 查看调度器状态（需要后端运行中）
curl http://127.0.0.1:8000/api/scheduler/status/
```

## 数据库

```powershell
# 创建/更新数据库迁移
.venv\Scripts\python.exe manage.py makemigrations parser_api

# 执行迁移
.venv\Scripts\python.exe manage.py migrate
```

## 前端

```powershell
# 安装依赖
cd frontend && bun install

# 开发模式
bun run dev

# 构建生产版本
bun run build

# 运行测试
bun run test
```

## 配置文件

| 文件 | 用途 | 是否提交 Git |
|------|------|-------------|
| `llm_config.ini` | LLM API Key、模型、批次大小 | ❌ |
| `llm_config.ini.example` | LLM 配置示例 | ✅ |
| `db_config.ini` | 数据库连接信息 | ❌ |
| `db_config.ini.example` | 数据库配置示例 | ✅ |
| `frontend/.env` | 前端 API 地址 | ❌ |
| `frontend/.env.example` | 前端配置示例 | ✅ |

## 注意事项

- 修改 `llm_config.ini` 后需要重启服务或清除 `__pycache__/` 才能生效
- `run_all_tasks --parallel` 默认排除 LLM 分析（因为需要先完成抓取）
- 定时调度器会在抓取完成后自动延迟 5 分钟触发 LLM 分析
- 前端通过 Vite 代理（`/api` → `localhost:8000`）访问后端
