from django.db import models


class Info(models.Model):
    """
    信息表模型
    """
    title = models.CharField(max_length=200, verbose_name="标题")
    platform = models.CharField(max_length=64, verbose_name="平台")
    date = models.DateTimeField(verbose_name="日期")
    rank = models.IntegerField(null=True, blank=True, verbose_name="排名")
    url = models.URLField(max_length=1000, verbose_name="链接")  # 增加到 1000 以支持微博等长 URL
    detail = models.TextField(blank=True, verbose_name="详情")
    section = models.CharField(max_length=64, blank=True, verbose_name="栏目")
    ranktime = models.CharField(max_length=32, blank=True, verbose_name="榜单时间范围")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        db_table = "info"
        verbose_name = "信息"
        verbose_name_plural = "信息"
        ordering = ["-date", "-rank"]
        indexes = [
            models.Index(fields=["platform", "date"]),
            models.Index(fields=["platform", "ranktime"]),
            models.Index(fields=["section"]),
        ]
    
    def __str__(self):
        return f"{self.platform} - {self.title}"


class KeywordAnalysis(models.Model):
    """关键词分析批次"""
    analysis_time = models.DateTimeField(verbose_name="分析时间")
    group = models.CharField(max_length=20, verbose_name="分组")  # domestic / international
    article_count = models.IntegerField(verbose_name="文章数")
    platform_count = models.IntegerField(verbose_name="平台数")
    platforms = models.TextField(verbose_name="平台列表")  # JSON
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "keyword_analysis"
        verbose_name = "关键词分析"
        verbose_name_plural = "关键词分析"
        ordering = ["-analysis_time"]
        indexes = [
            models.Index(fields=["analysis_time", "group"]),
        ]

    def __str__(self):
        return f"{self.group} - {self.analysis_time}"


class KeywordResult(models.Model):
    """关键词结果"""
    analysis = models.ForeignKey(KeywordAnalysis, on_delete=models.CASCADE, related_name="results")
    keyword = models.CharField(max_length=100, verbose_name="关键词")
    score = models.FloatField(verbose_name="得分")
    rank = models.IntegerField(verbose_name="排名")
    count = models.IntegerField(verbose_name="出现次数")
    platform_count = models.IntegerField(verbose_name="覆盖平台数")
    coverage = models.FloatField(verbose_name="覆盖率")
    sources = models.TextField(verbose_name="来源平台")  # JSON
    sample_articles = models.TextField(verbose_name="示例文章")  # JSON [{"title","url","platform"}]
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "keyword_result"
        verbose_name = "关键词结果"
        verbose_name_plural = "关键词结果"
        indexes = [
            models.Index(fields=["analysis", "rank"]),
            models.Index(fields=["keyword"]),
        ]

    def __str__(self):
        return f"#{self.rank} {self.keyword} ({self.score:.1f})"


class LLMPhraseExtraction(models.Model):
    """LLM 短语提取结果 - 逐条标题存储"""
    article = models.ForeignKey(Info, on_delete=models.CASCADE, related_name="llm_phrases")
    analysis_time = models.DateTimeField(verbose_name="分析时间")
    extracted_phrases = models.TextField(verbose_name="原文短语")       # JSON list
    normalized_phrases = models.TextField(verbose_name="规范化短语")    # JSON list
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "llm_phrase_extraction"
        verbose_name = "LLM短语提取"
        verbose_name_plural = "LLM短语提取"
        indexes = [
            models.Index(fields=["article", "analysis_time"]),
            models.Index(fields=["analysis_time"]),
        ]

    def __str__(self):
        return f"article={self.article_id} phrases={self.normalized_phrases[:50]}"


class LLMBatchLog(models.Model):
    """LLM 批次调用日志 - 记录每次 LLM 调用的输入和输出，便于调试"""
    analysis_time = models.DateTimeField(verbose_name="分析时间")
    group = models.CharField(max_length=20, verbose_name="分组")
    batch_index = models.IntegerField(verbose_name="批次序号")       # 第几批 (从1开始)
    title_count = models.IntegerField(verbose_name="输入标题数")
    input_titles = models.TextField(verbose_name="输入标题")          # JSON list[{id, title}]
    output_raw = models.TextField(verbose_name="LLM原始输出")         # JSON (完整LLM返回)
    success = models.BooleanField(default=True, verbose_name="是否成功")
    error_msg = models.TextField(blank=True, verbose_name="错误信息")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "llm_batch_log"
        verbose_name = "LLM批次日志"
        verbose_name_plural = "LLM批次日志"
        ordering = ["-analysis_time", "batch_index"]
        indexes = [
            models.Index(fields=["analysis_time", "group"]),
        ]

    def __str__(self):
        return f"{self.group} batch#{self.batch_index} titles={self.title_count} ok={self.success}"
