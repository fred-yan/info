# LLM 热点短语提取 - 设计方案 v2

## 1. 目标

用大模型对新闻标题做短语提取和语义归纳，提取结果逐条存入数据库，再基于权重评分体系计算热点排名。同时支持国内（中文）和国际（英文）两个分组。

## 2. 整体流程

```
数据获取 → 标题去重 → 阶段1:逐条短语提取 → 阶段2:全局语义归纳 → 计分 → 存库
```

### 数据获取

每个平台只取 `MAX(date)` 的最新一批，确保不同抓取频率的平台贡献均等。

**国内（domestic）**：ftchinese、kr36、tmtpost、jiqizhixin、cls、wscn、huxiu、zaobao、zhihu、weibo、pengpai

**国际（international）**：economist、apnews、theverge、techcrunch、mittr、github、hackernews

### 阶段1：逐条短语提取

每批 25 条标题发给 LLM，提取每条标题的关键短语：

```json
{"items": [
  {"id": 1, "title": "苹果发布M4芯片，AI推理速度提升5倍",
   "extracted_phrases": ["M4芯片", "AI推理速度"],
   "normalized_phrases": ["Apple M4", "AI推理加速"]},
  ...
]}
```

结果写入 `llm_phrase_extraction` 表，**12小时缓存**：若 80% 以上文章有缓存则跳过阶段1直接进阶段2。

**形式化校验（阶段1）**：
- [A] 输出 items 数量必须等于输入标题数量（严重，失败则整批重试）
- [B] 每条 item 的 title 必须与对应序号的输入一致（严重，自动修正）
- [C] extracted_phrases 应出现在原标题中（警告，仅记录）
- [D] 空短语率不超过 30%（警告）

### 阶段2：全局语义归纳

过滤掉只出现 1 次的长尾噪声（约占 66%），取频次 ≥ 2 的 Top 300 个短语整体发一次 LLM：

```
"Apple M4" → 文章ID: [123, 178]
"OpenAI"   → 文章ID: [124, 167, 189]
...
```

LLM 对语义相近的短语归并为组：

```json
{"phrase_groups": [
  {"representative": "Apple M4芯片",
   "members": ["Apple M4", "M4芯片", "苹果处理器"],
   "title_ids": [123, 145, 178]}
]}
```

**形式化校验（阶段2）**：
- [E1] representative 不能为空（警告，跳过该组）
- [E2] representative 不能重复（警告，跳过重复组）
- [E3] members 不能为空（警告，跳过该组）
- [E4] 至少一个 member 是阶段1已知短语（警告，防幻觉，跳过）
- [E5] 组数量 ≥ max(5, 输入短语数 × 15%)（严重，过少说明截断或过度合并）

## 3. 计分模型

```
article_weight = section_weight × rank_weight × ranktime_weight

section_weight:  section_1=3.0, section_2=2.5, section_3=2.0, hotlist=1.5
rank_weight:     rank 1-3=2.0, rank 4-10=1.5, 其他=1.0
ranktime_weight: 24hour=2.0, 48hour=1.5, 168hour=1.0, 720hour=0.8

跨平台 boost = 1 + (覆盖平台数 / 总平台数) × 3.0
phrase_group 得分 = Σ(关联文章权重) × 跨平台 boost
```

跨平台 boost 是核心——同一词同时出现在多个媒体，比只出现在一个平台的词得分高 3 倍以上。

## 4. 数据库表

| 表名 | 说明 |
|------|------|
| `llm_phrase_extraction` | 阶段1：每篇文章的短语提取结果（article_id → phrases） |
| `llm_phrase_group` | 阶段2：全局语义归纳组（representative + members + article_ids）|
| `llm_batch_log` | LLM 调用日志（输入/输出，便于调试）|
| `keyword_analysis` | 分析批次元数据（group=domestic_llm / international_llm）|
| `keyword_result` | 最终关键词排名（keyword, score, rank, sources, sample_articles）|

## 5. 命令行

```powershell
# 国内热点（两阶段完整流程）
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group domestic --force

# 国际热点
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group international --force

# 只跑阶段2（复用阶段1缓存，适合调试阶段2）
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --stage2-only --group domestic

# 打印提示词（调试用，不调用 LLM）
.venv\Scripts\python.exe manage.py extract_keywords_llm --debug-v2 --stage 1
.venv\Scripts\python.exe manage.py extract_keywords_llm --debug-v2 --stage 2
```

## 6. API 接口

```
GET /api/keywords/ranking/?group=domestic             # 关键词排行榜（含趋势方向）
GET /api/keywords/trend/?keyword=AI&group=domestic    # 关键词历史趋势（7天折线）
GET /api/keywords/articles/?keyword=AI&group=domestic # 关键词关联文章
```

`ranking` 接口返回的每篇 sample_article 带有 `matched_phrases` 字段，显示该文章阶段1提取的实际短语，便于判断关联是否合理。

## 7. LLM 配置

```ini
# llm_config.ini
[llm]
model = deepseek-v4-flash
max_tokens = 32768
temperature = 0.1
batch_size = 25    # 阶段1每批标题数
```

## 8. Token 消耗估算（每次完整运行）

| 阶段 | 批次数 | 单批 tokens | 小计 |
|------|--------|------------|------|
| 阶段1（国内，~250条标题）| ~10批 | ~3000 | ~30000 |
| 阶段2（~200个短语）| 1-2批 | ~10000 | ~20000 |
| 合计 | | | **~50000** |

每天 2 次（domestic + international）× 4 次定时 ≈ **400,000 tokens/天**（有缓存时阶段1可跳过，实际远少于此）。

## 9. 触发机制

**不走固定 cron**，在所有平台抓取完成后自动触发（见调度器文档）。手动触发也可直接使用上方命令行。
