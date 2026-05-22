# 命令参考手册

## 1. 数据库迁移

```bash
# 生成迁移文件
./.venv/Scripts/python manage.py makemigrations parser_api

# 应用所有迁移
./.venv/Scripts/python manage.py migrate

# 应用到指定版本
./.venv/Scripts/python manage.py migrate parser_api 0006
```

## 2. 新闻抓取

### 执行所有平台抓取

```bash
# 顺序执行
./.venv/Scripts/python manage.py run_all_tasks

# 并行执行（推荐，速度快 3-4 倍）
./.venv/Scripts/python manage.py run_all_tasks --parallel

# 只执行指定平台
./.venv/Scripts/python manage.py run_all_tasks --platform weibo,zhihu,pengpai

# 指定平台 + 并行
./.venv/Scripts/python manage.py run_all_tasks --platform weibo,zhihu --parallel
```

### 启动定时调度器

```bash
./.venv/Scripts/python manage.py run_scheduler
```

## 3. 关键词提取（jieba/nltk）

```bash
# 默认：两组都跑（domestic + international）
./.venv/Scripts/python manage.py extract_keywords

# 只跑国内组
./.venv/Scripts/python manage.py extract_keywords --group domestic

# 只跑国际组
./.venv/Scripts/python manage.py extract_keywords --group international

# 指定返回数量
./.venv/Scripts/python manage.py extract_keywords --top 30
```

## 4. LLM 短语提取

```bash
# 默认执行（有缓存时跳过 LLM 调用）
./.venv/Scripts/python manage.py extract_keywords_llm

# 强制重新调用 LLM（跳过缓存）
./.venv/Scripts/python manage.py extract_keywords_llm --force

# 指定分组
./.venv/Scripts/python manage.py extract_keywords_llm --group domestic
./.venv/Scripts/python manage.py extract_keywords_llm --group international

# 指定返回数量
./.venv/Scripts/python manage.py extract_keywords_llm --top 30

# 组合使用
./.venv/Scripts/python manage.py extract_keywords_llm --group domestic --top 30 --force
```

## 5. 数据清理

```bash
# 清空 LLM 短语提取缓存（llm_phrase_extraction 表）
./.venv/Scripts/python -c "import os; os.environ['DJANGO_SETTINGS_MODULE']='django_api.settings'; import django; django.setup(); from parser_api.models import LLMPhraseExtraction; n,_=LLMPhraseExtraction.objects.all().delete(); print(f'deleted {n}')"

# 清空 LLM 批次日志（llm_batch_log 表）
./.venv/Scripts/python -c "import os; os.environ['DJANGO_SETTINGS_MODULE']='django_api.settings'; import django; django.setup(); from parser_api.models import LLMBatchLog; n,_=LLMBatchLog.objects.all().delete(); print(f'deleted {n}')"

# 清空关键词分析结果（keyword_analysis + keyword_result 表）
./.venv/Scripts/python -c "import os; os.environ['DJANGO_SETTINGS_MODULE']='django_api.settings'; import django; django.setup(); from parser_api.models import KeywordAnalysis; n,_=KeywordAnalysis.objects.all().delete(); print(f'deleted {n}')"
```

## 6. 数据查询

```bash
# 查看各平台最新数据条数
./.venv/Scripts/python -c "
import os; os.environ['DJANGO_SETTINGS_MODULE']='django_api.settings'
import django; django.setup()
from django.db.models import Max, Count
from parser_api.models import Info
for r in Info.objects.values('platform').annotate(latest=Max('date'), cnt=Count('id')).order_by('platform'):
    print(f\"{r['platform']:20s} count={r['cnt']:4d} latest={r['latest']}\")
"

# 查看某篇文章是否在最新批次中
./.venv/Scripts/python -c "
import os; os.environ['DJANGO_SETTINGS_MODULE']='django_api.settings'
import django; django.setup()
from django.db.models import Max
from parser_api.models import Info
a = Info.objects.get(id=1630)
latest = Info.objects.filter(platform=a.platform).aggregate(m=Max('date'))['m']
print(f'article {a.id}: platform={a.platform}, date={a.date}, latest={latest}, in_batch={a.date==latest}')
"

# 查看 LLM 批次日志
./.venv/Scripts/python -c "
import os; os.environ['DJANGO_SETTINGS_MODULE']='django_api.settings'
import django; django.setup()
from parser_api.models import LLMBatchLog
for log in LLMBatchLog.objects.order_by('-analysis_time', 'batch_index')[:10]:
    print(f'batch#{log.batch_index} group={log.group} titles={log.title_count} ok={log.success} time={log.analysis_time}')
"

# 查看 LLM 短语提取缓存记录数
./.venv/Scripts/python -c "
import os; os.environ['DJANGO_SETTINGS_MODULE']='django_api.settings'
import django; django.setup()
from parser_api.models import LLMPhraseExtraction
print(f'total records: {LLMPhraseExtraction.objects.count()}')
print(f'unique articles: {LLMPhraseExtraction.objects.values(\"article_id\").distinct().count()}')
"
```

## 7. Django 开发服务器

```bash
./.venv/Scripts/python manage.py runserver 0.0.0.0:8000
```

## 8. API 端点

启动服务器后可访问以下接口（默认 `http://localhost:8000/api/`）：

| 端点 | 说明 |
|------|------|
| `/api/economist/` | Economist 抓取 |
| `/api/apnews/` | AP News 抓取 |
| `/api/ftchinese/` | FT中文网 抓取 |
| `/api/cn_wsj/` | 华尔街日报中文网 抓取 |
| `/api/kr36/` | 36氪 抓取 |
| `/api/huxiu/` | 虎嗅 抓取 |
| `/api/wst_post/` | Washington Post 抓取 |
| `/api/zaobao/` | 早报首页 抓取 |
| `/api/zaobao/hotlist/` | 早报热榜 抓取 |
| `/api/github/trending` | GitHub Trending 抓取 |
| `/api/hacker_news/topstories/` | Hacker News 抓取 |
| `/api/zhihu/` | 知乎热榜 抓取 |
| `/api/pengpai/` | 澎湃新闻 抓取 |
| `/api/weibo/` | 微博热搜 抓取 |
| `/api/keywords/` | jieba/nltk 关键词提取结果 |
| `/api/keywords/llm/` | LLM 短语提取结果 |
| `/api/scheduler/status/` | 调度器状态 |
