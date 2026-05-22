"""
热点关键词提取器
从最近一次抓取的新闻标题中提取热点关键词，按热度排序。
"""
import json
import logging
import re
from collections import defaultdict

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from .models import Info, KeywordAnalysis, KeywordResult

logger = logging.getLogger(__name__)

# ==================== 权重配置 ====================

SECTION_WEIGHT = {
    "section_1": 3.0,
    "section_2": 2.5,
    "section_3": 2.0,
    "hotlist": 1.5,
}

RANKTIME_WEIGHT = {
    "24hour": 2.0,
    "48hour": 1.5,
    "168hour": 1.0,
    "720hour": 0.8,
}

# ==================== 停用词 ====================

ZH_STOPWORDS = {
    # 通用虚词
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "这", "那", "他", "她", "它", "们", "什么", "怎么", "如何", "为什么", "哪", "哪些",
    "可以", "可能", "应该", "需要", "已经", "正在", "将", "被", "把", "让", "给",
    "而", "但", "但是", "然而", "因为", "所以", "如果", "虽然", "还是", "或者",
    "这个", "那个", "这些", "那些", "自己", "什么样", "怎样", "多少",
    "来", "去", "过", "起来", "下去", "出来", "进去",
    # 新闻通用词
    "记者", "报道", "消息", "表示", "称", "据", "日", "月", "年", "时", "分",
    "发布", "公布", "通报", "建议", "认为", "指出", "强调", "透露",
    "新华社", "中新网", "央视", "新闻", "快讯", "速递", "头条",
    "代表", "委员", "回应", "关注", "热议", "聚焦",
    # 标点符号相关
    "丨", "｜", "①", "②", "③", "④", "⑤",
    # 数字和量词
    "万", "亿", "多", "余", "约", "近", "超", "达",
}

EN_STOPWORDS = {
    # 通用
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "between",
    "through", "during", "before", "after", "above", "below", "up", "down",
    "out", "off", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "both", "each",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "because",
    "but", "and", "or", "if", "while", "that", "this", "these", "those",
    "it", "its", "he", "she", "they", "them", "his", "her", "their",
    "what", "which", "who", "whom", "we", "you", "me", "my", "your",
    # 新闻通用词
    "says", "said", "report", "reports", "new", "news", "show", "shows",
    "according", "year", "years", "people", "time", "first", "last",
    "also", "many", "much", "well", "way", "even", "back", "still",
    "get", "got", "make", "made", "take", "took", "come", "came",
    "know", "think", "see", "look", "want", "give", "use", "find",
    "tell", "ask", "work", "seem", "feel", "try", "leave", "call",
}


# ==================== 分词函数 ====================

def _tokenize_zh(title: str) -> list[str]:
    """中文分词，提取名词类关键词"""
    import jieba.posseg as pseg
    
    words = pseg.cut(title)
    keywords = []
    for w in words:
        # 提取名词类: n 名词, nr 人名, ns 地名, nt 机构名, nz 专名, vn 动名词
        if not w.flag.startswith('n'):
            continue
        word = w.word.strip()
        if len(word) < 2:
            continue
        if word in ZH_STOPWORDS:
            continue
        # 过滤纯数字
        if word.isdigit():
            continue
        keywords.append(word)
    return keywords


def _tokenize_en(title: str) -> list[str]:
    """英文分词，提取名词类关键词"""
    from nltk import pos_tag, word_tokenize
    
    tokens = word_tokenize(title)
    tagged = pos_tag(tokens)
    keywords = []
    for word, tag in tagged:
        # 提取名词和专有名词
        if tag not in ('NN', 'NNS', 'NNP', 'NNPS'):
            continue
        if len(word) < 2:
            continue
        # 专有名词保留原始大小写，普通名词转小写
        if tag in ('NNP', 'NNPS'):
            key = word
        else:
            key = word.lower()
        if key.lower() in EN_STOPWORDS:
            continue
        # 过滤纯数字和标点
        if word.isdigit() or not re.search(r'[a-zA-Z]', word):
            continue
        keywords.append(key)
    return keywords


# ==================== 权重计算 ====================

def _calc_article_weight(article: Info) -> float:
    """计算单条记录的权重"""
    # 位置权重
    sw = SECTION_WEIGHT.get(article.section, 1.0)
    
    # 排名权重
    rank = article.rank
    if rank is not None and rank <= 3:
        rw = 2.0
    elif rank is not None and rank <= 10:
        rw = 1.5
    else:
        rw = 1.0
    
    # 时间范围权重
    tw = RANKTIME_WEIGHT.get(article.ranktime, 1.0)
    
    return sw * rw * tw


# ==================== 数据获取 ====================

def _get_recent_articles() -> dict[str, list]:
    """
    每个平台只取最近一批数据（MAX(date)），确保不同抓取频率的平台贡献均等。
    Returns: {platform: [Info, ...]}
    """
    latest_dates = Info.objects.values('platform').annotate(latest=Max('date'))
    result = {}
    for item in latest_dates:
        batch = list(Info.objects.filter(
            platform=item['platform'],
            date=item['latest']
        ))
        if batch:
            result[item['platform']] = batch
    return result


# ==================== 关键词聚合 ====================

def _calc_keyword_scores(
    articles_by_platform: dict[str, list],
    platforms: list[str],
    lang: str,
) -> list[dict]:
    """
    对指定平台组的文章做分词、加权、跨站聚合，返回排序后的关键词列表。
    """
    tokenize = _tokenize_zh if lang == "zh" else _tokenize_en

    # keyword -> {weighted_freq, count, platforms: set, articles: list}
    kw_stats: dict[str, dict] = defaultdict(lambda: {
        "weighted_freq": 0.0,
        "count": 0,
        "platforms": set(),
        "articles": [],
    })

    total_platforms = 0

    for plat in platforms:
        batch = articles_by_platform.get(plat)
        if not batch:
            continue
        total_platforms += 1

        for article in batch:
            weight = _calc_article_weight(article)
            keywords = tokenize(article.title)
            seen = set()  # 同一篇文章同一关键词只计一次
            for kw in keywords:
                if kw in seen:
                    continue
                seen.add(kw)
                st = kw_stats[kw]
                st["weighted_freq"] += weight
                st["count"] += 1
                st["platforms"].add(plat)
                # 最多保留 3 条示例
                if len(st["articles"]) < 3:
                    st["articles"].append({
                        "title": article.title,
                        "url": article.url,
                        "platform": plat,
                    })

    if total_platforms == 0:
        return []

    # 计算最终得分
    scored = []
    for kw, st in kw_stats.items():
        plat_count = len(st["platforms"])
        coverage = plat_count / total_platforms
        cross_site_boost = 1 + coverage * 3.0
        score = st["weighted_freq"] * cross_site_boost
        scored.append({
            "keyword": kw,
            "score": round(score, 2),
            "count": st["count"],
            "platform_count": plat_count,
            "coverage": round(coverage, 4),
            "sources": sorted(st["platforms"]),
            "sample_articles": st["articles"],
        })

    # 按得分降序
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


# ==================== 主入口 ====================

def extract_keywords(group: str | None = None, top: int = 50) -> dict:
    """
    提取热点关键词并存入数据库。

    Args:
        group: "domestic" / "international" / None(两组都跑)
        top: 每组返回前 N 个关键词

    Returns:
        完整分析结果 dict
    """
    platform_groups = settings.PLATFORM_GROUPS
    articles_by_platform = _get_recent_articles()
    now = timezone.now()

    groups_to_run = (
        [group] if group else list(platform_groups.keys())
    )

    output = {"analysis_time": now.strftime("%Y-%m-%d %H:%M:%S")}

    for grp in groups_to_run:
        cfg = platform_groups.get(grp)
        if not cfg:
            logger.warning("Unknown group: %s", grp)
            continue

        platforms = cfg["platforms"]
        lang = cfg["lang"]
        label = cfg["label"]

        scored = _calc_keyword_scores(articles_by_platform, platforms, lang)
        top_keywords = scored[:top]

        # 统计文章数
        article_count = sum(
            len(articles_by_platform.get(p, [])) for p in platforms
        )
        active_platforms = [p for p in platforms if p in articles_by_platform]

        # 写入数据库
        analysis = KeywordAnalysis.objects.create(
            analysis_time=now,
            group=grp,
            article_count=article_count,
            platform_count=len(active_platforms),
            platforms=json.dumps(active_platforms, ensure_ascii=False),
        )

        for idx, kw in enumerate(top_keywords, 1):
            KeywordResult.objects.create(
                analysis=analysis,
                keyword=kw["keyword"],
                score=kw["score"],
                rank=idx,
                count=kw["count"],
                platform_count=kw["platform_count"],
                coverage=kw["coverage"],
                sources=json.dumps(kw["sources"], ensure_ascii=False),
                sample_articles=json.dumps(kw["sample_articles"], ensure_ascii=False),
            )

        logger.info(
            "keyword_analysis group=%s articles=%d platforms=%d keywords=%d",
            grp, article_count, len(active_platforms), len(top_keywords),
        )

        output[grp] = {
            "label": label,
            "article_count": article_count,
            "platform_count": len(active_platforms),
            "keywords": top_keywords,
        }

    return output
