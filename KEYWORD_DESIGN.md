# 热点关键词提取 - 设计文档

## 1. 目标

从最近一次抓取的新闻标题中，分别提取国内热点和国际热点的关键词/短语，按热度排序，结果存入数据库。

## 2. 平台分组配置（settings.py）

```python
PLATFORM_GROUPS = {
    "domestic": {
        "platforms": ["ftchinese", "wsj", "kr36", "huxiu", "zaobao", "zhihu", "weibo", "pengpai"],
        "label": "国内热点",
        "lang": "zh"
    },
    "international": {
        "platforms": ["economist", "apnews", "washingtonpost", "github", "hackernews"],
        "label": "国际热点",
        "lang": "en"
    }
}
```

## 3. 数据范围

每个平台只取最新一批数据（MAX(date)），确保不同抓取频率的平台贡献均等。

```python
def _get_recent_articles():
    """每个平台只取最近一次抓取的数据"""
    latest_dates = Info.objects.values('platform').annotate(latest=Max('date'))
    result = {}
    for item in latest_dates:
        batch = list(Info.objects.filter(platform=item['platform'], date=item['latest']))
        result[item['platform']] = batch
    return result
```

## 4. 评分模型

### 4.1 位置权重

| section | 权重 |
|---------|------|
| section_1 | 3.0 |
| section_2 | 2.5 |
| section_3 | 2.0 |
| hotlist | 1.5 |
| 其他 | 1.0 |

### 4.2 排名权重

| rank | 权重 |
|------|------|
| 1-3 | 2.0 |
| 4-10 | 1.5 |
| 11+ 或 None | 1.0 |

### 4.3 时间范围权重

| ranktime | 权重 |
|----------|------|
| 24hour | 2.0 |
| 48hour | 1.5 |
| 168hour | 1.0 |
| 720hour | 0.8 |
| 无 | 1.0 |

### 4.4 单条记录权重

```
article_weight = section_weight × rank_weight × ranktime_weight
```

### 4.5 关键词最终得分

```
weighted_freq = sum(article_weight for each article containing keyword)
coverage = platform_count / total_platforms_in_group
cross_site_boost = 1 + coverage × 3.0
score = weighted_freq × cross_site_boost
```

## 5. 分词策略

### 5.1 中文（jieba）

- 使用 jieba.posseg 词性标注
- 提取名词类：n(名词), nr(人名), ns(地名), nt(机构名), nz(专名)
- 过滤：长度 >= 2，去停用词

### 5.2 英文（NLTK）

- 使用 nltk.pos_tag 词性标注
- 提取名词类：NN, NNS, NNP, NNPS
- 过滤：长度 >= 2，去停用词，转小写（专有名词保留原始大小写）

## 6. 数据库表设计

### keyword_analysis（分析批次表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BigAutoField | 主键 |
| analysis_time | DateTimeField | 分析时间 |
| group | CharField(20) | domestic / international |
| article_count | IntegerField | 文章数 |
| platform_count | IntegerField | 平台数 |
| platforms | TextField | 平台列表 JSON |
| created_at | DateTimeField | 创建时间 |

### keyword_result（关键词结果表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BigAutoField | 主键 |
| analysis | ForeignKey | 外键 → keyword_analysis |
| keyword | CharField(100) | 关键词 |
| score | FloatField | 最终得分 |
| rank | IntegerField | 排名 |
| count | IntegerField | 出现次数 |
| platform_count | IntegerField | 覆盖平台数 |
| coverage | FloatField | 覆盖率 |
| sources | TextField | 来源平台 JSON |
| sample_articles | TextField | 示例文章 JSON [{"title","url","platform"}] |
| created_at | DateTimeField | 创建时间 |

## 7. 文件结构

```
parser_api/
├── keyword_extractor.py              # 核心提取逻辑
├── models.py                         # 新增 KeywordAnalysis, KeywordResult
├── management/commands/
│   └── extract_keywords.py           # 命令行入口
├── views.py                          # 添加 keywords_view
└── urls.py                           # 添加路由
```

## 8. 定时任务配置

```python
SCHEDULER_CONFIG = {
    # ... 现有抓取任务 ...
    'keyword_analysis': {
        'cron': '0 10,22 * * *',  # 每天10点和22点
        'enabled': True,
    },
}
```

## 9. API 接口

```
GET /api/keywords/                    # 最近一次分析结果
GET /api/keywords/?group=domestic     # 只看国内
GET /api/keywords/?top=30             # 返回前30个
```

## 10. 命令行

```bash
python manage.py extract_keywords
python manage.py extract_keywords --group domestic
python manage.py extract_keywords --top 30
```

## 11. 输出格式

```json
{
  "analysis_time": "2026-03-09 22:00:00",
  "domestic": {
    "label": "国内热点",
    "article_count": 100,
    "platform_count": 8,
    "keywords": [
      {
        "keyword": "两会",
        "score": 25.6,
        "rank": 1,
        "count": 12,
        "platform_count": 6,
        "coverage": 0.75,
        "sources": ["pengpai", "zhihu", "ftchinese"],
        "sample_articles": [
          {"title": "直击两会丨...", "url": "https://...", "platform": "pengpai"},
          {"title": "两会外长会...", "url": "https://...", "platform": "zhihu"}
        ]
      }
    ]
  },
  "international": {
    "label": "国际热点",
    "article_count": 50,
    "platform_count": 5,
    "keywords": [
      {
        "keyword": "Iran",
        "score": 18.3,
        "rank": 1,
        "count": 8,
        "platform_count": 4,
        "coverage": 0.80,
        "sources": ["economist", "apnews", "washingtonpost"],
        "sample_articles": [
          {"title": "The Long-Feared...", "url": "https://...", "platform": "apnews"}
        ]
      }
    ]
  }
}
```

## 12. 依赖

```
jieba          # 中文分词
nltk           # 英文分词和词性标注
```
