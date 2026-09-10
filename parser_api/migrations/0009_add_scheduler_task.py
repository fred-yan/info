from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parser_api', '0008_add_scheduler_lock'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchedulerTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_id', models.CharField(max_length=20, verbose_name='批次ID')),
                ('task_type', models.CharField(
                    choices=[
                        ('fetch', '平台抓取'),
                        ('llm_extract', 'LLM短语提取'),
                        ('llm_cluster', 'LLM全局归类'),
                    ],
                    max_length=20,
                    verbose_name='任务类型',
                )),
                ('platform', models.CharField(max_length=64, verbose_name='平台')),
                ('status', models.CharField(
                    choices=[
                        ('waiting', '等待依赖'),
                        ('pending', '待执行'),
                        ('running', '执行中'),
                        ('done', '已完成'),
                        ('failed', '已失败'),
                        ('skipped', '已跳过'),
                    ],
                    default='pending',
                    max_length=16,
                    verbose_name='状态',
                )),
                ('worker_id', models.CharField(blank=True, max_length=64, verbose_name='Worker ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='开始时间')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='完成时间')),
                ('error_msg', models.TextField(blank=True, verbose_name='错误信息')),
                ('retry_count', models.IntegerField(default=0, verbose_name='已重试次数')),
                ('timeout_at', models.DateTimeField(blank=True, null=True, verbose_name='预计超时时间')),
            ],
            options={
                'verbose_name': '调度任务',
                'verbose_name_plural': '调度任务',
                'db_table': 'scheduler_task',
            },
        ),
        migrations.AlterUniqueTogether(
            name='schedulertask',
            unique_together={('batch_id', 'task_type', 'platform')},
        ),
        migrations.AddIndex(
            model_name='schedulertask',
            index=models.Index(fields=['status', 'task_type'], name='sched_status_type_idx'),
        ),
        migrations.AddIndex(
            model_name='schedulertask',
            index=models.Index(fields=['batch_id', 'status'], name='sched_batch_status_idx'),
        ),
        migrations.AddIndex(
            model_name='schedulertask',
            index=models.Index(fields=['batch_id', 'task_type'], name='sched_batch_type_idx'),
        ),
        migrations.AddIndex(
            model_name='schedulertask',
            index=models.Index(fields=['timeout_at', 'status'], name='sched_timeout_status_idx'),
        ),
    ]
