# LLM 热点短语提取 - 设计方案 v2

## 1. 目标

用大模型（qwen3.5-plus）对国内平台的中文新闻标题做短语提取和归纳，提取结果逐条存入数据库（标题 id ↔ 短语映射），再基于现有权重评分体系计算热点排名。

先只做中文（domestic 组），英文后续扩展。

## 2. 整体流程

```
┌──────────────────────────────────────────────────────────────┐
│  Step 1: 数据获取                                             │
│  _get_recent_articles() → {platform: [Info, ...]}            │
│  每个平台只取 MAX(date) 的最新一批                              │
│  国内平台: ftchinese, wsj, kr36, huxiu, zaobao,              │
│           zhihu, weibo, pengpai                               │
│  实测: ~192 条原始记录                                         │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 2: 标题去重                                             │
│                                                              │
│  问题: 同平台内存在重复标题（kr36 约14条, wsj 约7条）           │
│  原因: 同一篇文章出现在多个榜单（人气榜+综合榜+收藏榜）         │
│                                                              │
│  去重策略:                                                    │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ 1. 按 title 分组，相同标题的多条记录归为一组           │     │
│  │ 2. 只发送唯一标题给 LLM（节省 token）                 │     │
│  │ 3. 维护 title → [article_id, ...] 的映射关系         │     │
│  │ 4. LLM 返回结果后，通过映射关系展开到所有原始记录      │     │
│  │ 5. 评分时每条原始记录独立计算权重（保留位置/排名信息）  │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  实测: 192 条 → 去重后约 170 条唯一标题                        │
│  发送给 LLM 的是 170 条（而非 192 条）                         │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 3: LLM 短语提取（一次性调用）                            │
│                                                              │
│  输入格式:                                                    │
│  1. 央行宣布下调存款准备金率0.5个百分点                         │
│  2. 降准落地 A股三大指数集体高开                                │
│  ...                                                         │
│  170. xxx                                                    │
│                                                              │
│  注意: 输入中的编号是"去重序号"(1~170)，不是数据库 id           │
│  需要维护 去重序号 → title → [article_ids] 的映射              │
│                                                              │
│  输出 (双层):                                                 │
│  {                                                           │
│    "items": [                                                │
│      {                                                       │
│        "id": 1,                                              │
│        "title": "央行宣布下调存款准备金率0.5个百分点",           │
│        "extracted_phrases": ["央行", "存款准备金率", "0.5个百分点"],│
│        "normalized_phrases": ["央行降准", "存款准备金率"]        │
│      }, ...                                                  │
│    ],                                                        │
│    "phrase_groups": [                                         │
│      {                                                       │
│        "normalized_phrase": "央行降准",                        │
│        "member_titles": [1, 2, 3],                           │
│        "surface_forms": ["央行降准", "降准落地", "降准影响"]     │
│      }, ...                                                  │
│    ]                                                         │
│  }                                                           │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 4: 存入 LLM 提取结果表 (llm_phrase_extraction)          │
│                                                              │
│  对 LLM 返回的 items 中每一条:                                 │
│  - 通过 去重序号 → title → [article_ids] 映射                 │
│  - 为每个 article_id 创建一条记录                              │
│  - 记录该标题的 extracted_phrases 和 normalized_phrases        │
│                                                              │
│  这张表的作用:                                                 │
│  - 保留 LLM 原始提取结果，可追溯                               │
│  - 后续可基于此表做各种统计，不需要重复调用 LLM                  │
│  - 可用于评估 LLM 提取质量                                     │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 5: 基于 phrase_groups 做热点评分                         │
│                                                              │
│  对每个 phrase_group:                                         │
│  1. 通过 member_titles(去重序号) → 展开为所有 article_ids      │
│  2. 每个 article_id 独立计算权重:                              │
│     article_weight = section_weight × rank_weight × ranktime │
│  3. weighted_freq = Σ article_weight                         │
│  4. coverage = unique_platforms / total_platforms             │
│  5. cross_site_boost = 1 + coverage × 3.0                   │
│  6. score = weighted_freq × cross_site_boost                 │
│                                                              │
│  存入 KeywordAnalysis + KeywordResult 表                      │
│  group = "domestic_llm"                                      │
└──────────────────────────────────────────────────────────────┘
```

## 3. 去重详细设计

```python
def _prepare_titles(articles_by_platform, platforms):
    """
    去重并构建映射关系
    
    Returns:
        unique_titles: [{seq: 1, title: "xxx"}, ...]   # 发给 LLM 的去重列表
        title_to_ids: {"xxx": [id1, id2, ...]}         # 标题 → 原始记录 ID 列表
        id_to_article: {id: Info}                      # ID → 原始记录对象
    """
    title_to_ids = defaultdict(list)
    id_to_article = {}
    
    for plat in platforms:
        for article in articles_by_platform.get(plat, []):
            title_to_ids[article.title].append(article.id)
            id_to_article[article.id] = article
    
    unique_titles = []
    for seq, title in enumerate(title_to_ids.keys(), 1):
        unique_titles.append({"seq": seq, "title": title})
    
    # 构建 seq → title 映射（用于 LLM 返回结果的反查）
    seq_to_title = {item["seq"]: item["title"] for item in unique_titles}
    
    return unique_titles, title_to_ids, id_to_article, seq_to_title
```

去重效果（基于实测数据）：

| 平台 | 原始条数 | 唯一标题 | 重复条数 | 重复原因 |
|------|---------|---------|---------|---------|
| kr36 | 30 | 16 | 14 | 同一文章在人气/综合/收藏三个榜 |
| wsj | 20 | 13 | 7 | 同一文章在首页和热门榜 |
| ftchinese | 20 | 19 | 1 | 热门和付费热门重叠 |
| 其他 | 122 | 122 | 0 | 无重复 |
| **合计** | **192** | **170** | **22** | |

## 4. 新增数据库表: llm_phrase_extraction

```python
class LLMPhraseExtraction(models.Model):
    """LLM 短语提取结果 - 逐条标题存储"""
    article = models.ForeignKey(Info, on_delete=models.CASCADE, related_name="llm_phrases")
    analysis_time = models.DateTimeField(verbose_name="分析时间")
    extracted_phrases = models.TextField(verbose_name="原文短语")      # JSON list
    normalized_phrases = models.TextField(verbose_name="规范化短语")    # JSON list
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "llm_phrase_extraction"
        indexes = [
            models.Index(fields=["article", "analysis_time"]),
            models.Index(fields=["analysis_time"]),
        ]
```

示例数据：

| id | article_id | analysis_time | extracted_phrases | normalized_phrases |
|----|-----------|---------------|-------------------|-------------------|
| 1 | 501 | 2026-03-11 22:05 | ["哈梅内伊之子", "最高领袖"] | ["伊朗最高领袖继任", "哈梅内伊家族"] |
| 2 | 502 | 2026-03-11 22:05 | ["哈梅内伊之子", "最高领袖"] | ["伊朗最高领袖继任", "哈梅内伊家族"] |
| 3 | 503 | 2026-03-11 22:05 | ["伊朗战争", "欧洲", "中国"] | ["伊朗战争影响", "中欧关系"] |

说明：article_id 501 和 502 可能是同一标题在 wsj 的首页和热门榜各出现一次，它们的 extracted_phrases 相同，但在评分时各自贡献独立的权重。

## 5. 评分模型

完全复用 `keyword_extractor.py` 的权重体系：

```
article_weight = SECTION_WEIGHT[section] × RANK_WEIGHT[rank] × RANKTIME_WEIGHT[ranktime]
```

对每个 phrase_group（LLM 归纳的短语组）：

```python
# 1. 展开: 去重序号 → 标题 → 所有原始 article_ids
all_article_ids = []
for seq in phrase_group["member_titles"]:
    title = seq_to_title[seq]
    all_article_ids.extend(title_to_ids[title])

# 2. 计算加权频次
weighted_freq = sum(
    _calc_article_weight(id_to_article[aid])
    for aid in all_article_ids
)

# 3. 跨站覆盖
platforms_set = {id_to_article[aid].platform for aid in all_article_ids}
coverage = len(platforms_set) / total_platforms
cross_site_boost = 1 + coverage * 3.0

# 4. 最终得分
score = weighted_freq * cross_site_boost
```

重复标题的处理效果：
- kr36 同一文章在人气榜(rank=1) + 综合榜(rank=3) + 收藏榜(rank=5)
- 去重后只发一次给 LLM，但评分时三条记录各自贡献权重
- 这样既节省了 token，又保留了"多榜上榜 = 更热"的信号

## 6. 热点结果存储

复用现有 `KeywordAnalysis` + `KeywordResult` 表：

| 字段 | 映射 |
|------|------|
| group | "domestic_llm" |
| keyword | phrase_group.normalized_phrase |
| score | 计算得分 |
| count | len(展开后的 all_article_ids) |
| platform_count | 覆盖平台数 |
| coverage | 覆盖率 |
| sources | 来源平台列表 JSON |
| sample_articles | [{title, url, platform}] JSON（最多 3 条） |

KeywordResult 额外信息（存入 sample_articles 的扩展）：
- surface_forms 也一并存入，方便前端展示同义表达

## 7. 文件结构

```
parser_api/
├── llm_extractor_tiny.py              # 已有: LLM 调用封装 + Prompt + NewsPhraseExtractor
├── llm_keyword_extractor.py           # 新增: LLM 热点短语提取主逻辑
│   ├── _prepare_titles()              #   去重 + 构建映射
│   ├── _call_llm()                    #   调用 NewsPhraseExtractor
│   ├── _save_extractions()            #   存入 llm_phrase_extraction 表
│   ├── _score_phrase_groups()          #   评分
│   └── extract_keywords_llm()         #   主入口
├── models.py                          # 新增: LLMPhraseExtraction 模型
├── management/commands/
│   └── extract_keywords_llm.py        # 新增: 命令行入口
├── views.py                           # 新增: llm_keywords_view
└── urls.py                            # 新增路由
```

## 8. API 接口

```
GET /api/keywords/llm/                          # 最近一次 LLM 分析结果
GET /api/keywords/llm/?group=domestic           # 只看国内（目前只有国内）
GET /api/keywords/llm/?top=30                   # 前 30 个
GET /api/keywords/llm/?run=1                    # 立即执行一次分析
```

## 9. 命令行

```bash
python manage.py extract_keywords_llm
python manage.py extract_keywords_llm --top 30
```

## 10. 输出格式示例

```json
{
  "analysis_time": "2026-03-11 22:05:00",
  "method": "llm",
  "domestic_llm": {
    "label": "国内热点(LLM)",
    "article_count": 192,
    "unique_title_count": 170,
    "platform_count": 8,
    "keywords": [
      {
        "keyword": "伊朗最高领袖继任",
        "score": 95.6,
        "rank": 1,
        "count": 15,
        "platform_count": 5,
        "coverage": 0.625,
        "sources": ["ftchinese", "wsj", "zaobao", "zhihu", "weibo"],
        "surface_forms": ["哈梅内伊之子被选为新任最高领袖", "伊朗推选新最高领袖", "新任最高领袖"],
        "sample_articles": [
          {"title": "哈梅内伊之子被选为新任最高领袖...", "url": "https://...", "platform": "wsj"},
          {"title": "伊朗推选哈梅内伊之子...", "url": "https://...", "platform": "zaobao"}
        ]
      }
    ]
  }
}
```

## 11. 定时任务

```python
SCHEDULER_CONFIG = {
    'keyword_analysis_llm': {
        'cron': '5 10,22 * * *',   # 每天 10:05 和 22:05
        'enabled': True,
    },
}
```

## 12. Token 消耗估算

- 输入: 170 条标题 × 平均 25 字 ≈ 4250 字 ≈ 2500 tokens
- System Prompt ≈ 1500 tokens
- 输出: 170 条 items + phrase_groups ≈ 5000 tokens
- 单次调用总计 ≈ 9000 tokens
- 每天 2 次 ≈ 18000 tokens/天

## 13. 依赖

```
openai         # OpenAI SDK（调用 DashScope 兼容接口）
pydantic       # 结果验证
```
