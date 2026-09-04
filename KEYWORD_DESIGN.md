# 热点关键词提取 - 设计文档

> **注意**：基于 jieba/NLTK 的规则方案（本文档描述的方案）已被 LLM 两阶段方案取代，目前处于弃用状态（`enabled: False`）。当前生产环境使用的是 LLM 方案，详见 `LLM_KEYWORD_DESIGN.md`。

---

## 平台分组配置

```python
# django_api/settings.py
PLATFORM_GROUPS = {
    "domestic": {
        "platforms": ["ftchinese", "kr36", "tmtpost", "jiqizhixin", "cls", "wscn",
                      "huxiu", "zaobao", "zhihu", "weibo", "pengpai"],
        "label": "国内热点",
        "lang": "zh"
    },
    "international": {
        "platforms": ["economist", "apnews", "theverge", "techcrunch", "mittr",
                      "github", "hackernews"],
        "label": "国际热点",
        "lang": "en"
    }
}
```

## 评分模型

### 权重体系

| 维度 | 字段 | 权重 |
|------|------|------|
| 位置 | section_1 | 3.0 |
| | section_2 | 2.5 |
| | section_3 | 2.0 |
| | hotlist | 1.5 |
| 排名 | rank 1-3 | 2.0 |
| | rank 4-10 | 1.5 |
| | 其他 | 1.0 |
| 时间窗口 | 24hour | 2.0 |
| | 48hour | 1.5 |
| | 168hour | 1.0 |
| | 720hour | 0.8 |

### 计分公式

```
article_weight = section_weight × rank_weight × ranktime_weight

跨平台 boost = 1 + (覆盖平台数 / 总平台数) × 3.0
score = Σ(article_weight) × 跨平台 boost
```

## 分词策略

### 中文（jieba）

- 使用 `jieba.posseg` 词性标注
- 提取名词类：n / nr / ns / nt / nz
- 过滤长度 < 2、停用词、纯数字

### 英文（NLTK）

- 使用 `nltk.pos_tag`
- 提取名词类：NN / NNS / NNP / NNPS
- 专有名词保留大小写，普通名词转小写

## 命令行（已弃用，保留参考）

```powershell
.venv\Scripts\python.exe manage.py extract_keywords
.venv\Scripts\python.exe manage.py extract_keywords --group domestic
.venv\Scripts\python.exe manage.py extract_keywords --top 30
```

## 数据库表

与 LLM 方案共用同一套 `keyword_analysis` + `keyword_result` 表，区别在于 `group` 字段值：
- 规则方案：`domestic` / `international`
- LLM 方案：`domestic_llm` / `international_llm`
