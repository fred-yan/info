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


class LLMPhraseGroup(models.Model):
    """阶段2: LLM 全局短语归纳组"""
    analysis_time = models.DateTimeField(verbose_name="分析时间")
    group = models.CharField(max_length=20, verbose_name="分组")  # domestic_llm / international_llm
    representative = models.CharField(max_length=200, verbose_name="代表短语")
    members = models.TextField(verbose_name="成员短语列表")  # JSON list
    article_ids = models.TextField(verbose_name="关联文章ID")  # JSON list of info.id
    article_count = models.IntegerField(verbose_name="关联文章数")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "llm_phrase_group"
        verbose_name = "LLM短语归纳组"
        verbose_name_plural = "LLM短语归纳组"
        indexes = [
            models.Index(fields=["analysis_time", "group"]),
            models.Index(fields=["representative"]),
        ]

    def __str__(self):
        return f"{self.representative} ({self.article_count} articles)"


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


class SchedulerLock(models.Model):
    """
    分布式调度器锁表。
    多个 Gunicorn worker 同时触发同一任务时，通过此表确保只有一个 worker 真正执行。
    锁超时后（locked_at 距今超过 ttl_seconds）自动释放，防止任务崩溃导致锁永久占用。
    """
    task_name = models.CharField(max_length=128, primary_key=True, verbose_name="任务名")
    locked_at = models.DateTimeField(verbose_name="加锁时间")
    worker_id = models.CharField(max_length=64, blank=True, verbose_name="Worker标识")

    class Meta:
        db_table = "scheduler_lock"
        verbose_name = "调度器锁"
        verbose_name_plural = "调度器锁"

    def __str__(self):
        return f"{self.task_name} @ {self.locked_at}"


class SchedulerTask(models.Model):
    """
    数据库任务队列，替代进程内内存状态。

    每次定时批次启动时，向此表写入一批任务记录（fetch/llm_extract/llm_cluster）。
    Worker 通过 select_for_update(skip_locked=True) 抢占 pending 任务，保证多 worker
    不重复处理同一任务。任务状态、进度、错误全持久化，进程重启不丢失。

    任务类型：
      fetch       - 平台页面抓取
      llm_extract - 单平台 LLM 短语提取（依赖对应 fetch 完成）
      llm_cluster - 全局短语归类（依赖当前批次所有 llm_extract 完成）

    状态流转：
      waiting  → pending（依赖任务完成后由 worker 触发）
      pending  → running（worker 抢占后设置）
      running  → done / failed
      failed   → pending（retry_count < MAX_RETRY 时重置重试）
      failed   → skipped（fetch 失败时对应 llm_extract 标记为跳过）
    """

    # 状态常量
    STATUS_WAITING  = 'waiting'   # 等待依赖任务完成
    STATUS_PENDING  = 'pending'   # 等待被 worker 领取
    STATUS_RUNNING  = 'running'   # 正在执行
    STATUS_DONE     = 'done'      # 执行成功
    STATUS_FAILED   = 'failed'    # 执行失败（已超过重试上限）
    STATUS_SKIPPED  = 'skipped'   # 前置任务失败，跳过本任务

    STATUS_CHOICES = [
        (STATUS_WAITING,  '等待依赖'),
        (STATUS_PENDING,  '待执行'),
        (STATUS_RUNNING,  '执行中'),
        (STATUS_DONE,     '已完成'),
        (STATUS_FAILED,   '已失败'),
        (STATUS_SKIPPED,  '已跳过'),
    ]

    # 任务类型常量
    TYPE_FETCH       = 'fetch'
    TYPE_LLM_EXTRACT = 'llm_extract'
    TYPE_LLM_CLUSTER = 'llm_cluster'

    TYPE_CHOICES = [
        (TYPE_FETCH,       '平台抓取'),
        (TYPE_LLM_EXTRACT, 'LLM短语提取'),
        (TYPE_LLM_CLUSTER, 'LLM全局归类'),
    ]

    # llm_cluster 任务的 platform 占位值
    PLATFORM_ALL = '__all__'

    batch_id    = models.CharField(max_length=20, verbose_name="批次ID")      # "20260909_1800"
    task_type   = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="任务类型")
    platform    = models.CharField(max_length=64, verbose_name="平台")         # llm_cluster 时为 "__all__"
    status      = models.CharField(max_length=16, choices=STATUS_CHOICES,
                                   default=STATUS_PENDING, verbose_name="状态")
    worker_id   = models.CharField(max_length=64, blank=True, verbose_name="Worker ID")
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    started_at  = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    error_msg   = models.TextField(blank=True, verbose_name="错误信息")
    retry_count = models.IntegerField(default=0, verbose_name="已重试次数")
    timeout_at  = models.DateTimeField(null=True, blank=True, verbose_name="预计超时时间")

    class Meta:
        db_table = "scheduler_task"
        verbose_name = "调度任务"
        verbose_name_plural = "调度任务"
        unique_together = [('batch_id', 'task_type', 'platform')]
        indexes = [
            models.Index(fields=['status', 'task_type']),
            models.Index(fields=['batch_id', 'status']),
            models.Index(fields=['batch_id', 'task_type']),
            models.Index(fields=['timeout_at', 'status']),
        ]

    def __str__(self):
        return f"[{self.batch_id}] {self.task_type}/{self.platform} → {self.status}"
