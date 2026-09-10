"""
立即执行所有配置的任务一次
用法: python manage.py run_all_tasks [--platform PLATFORM] [--exclude PLATFORM]
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import time


def _run_fetch_direct(platform: str, **params):
    """
    直接执行单平台抓取（绕过调度器队列，供手动命令使用）。
    与定时任务的 _run_fetch 逻辑相同，但不写 SchedulerTask 记录。
    """
    from parser_api import views
    from django.test import RequestFactory

    view_map = {
        'economist':               views.economist_view,
        'apnews':                  views.apnews_view,
        'ftchinese':               views.ftchinese_view,
        'wsj':                     views.wsj_view,
        'kr36':                    views.kr36_view,
        'huxiu':                   views.huxiu_view,
        'wscn':                    views.wscn_view,
        'cls':                     views.cls_view,
        'jiqizhixin':              views.jiqizhixin_view,
        'tmtpost':                 views.tmtpost_view,
        'theverge':                views.theverge_view,
        'techcrunch':              views.techcrunch_view,
        'mittr':                   views.mittr_view,
        'zaobao':                  views.zaobao_view,
        'zaobao_hotlist':          views.zaobao_hotlist_view,
        'github_trending_daily':   views.github_trending_view,
        'github_trending_weekly':  views.github_trending_view,
        'github_trending_monthly': views.github_trending_view,
        'hacker_news':             views.hacker_news_top_stories_view,
        'zhihu':                   views.zhihu_view,
        'weibo':                   views.weibo_view,
        'pengpai':                 views.pengpai_view,
        'washingtonpost':          views.wst_post_view,
        'keyword_analysis_llm':    None,
    }

    # 特殊任务：LLM 全量分析
    if platform == 'keyword_analysis_llm':
        from django.db import close_old_connections
        from parser_api.llm_extractor_v2 import extract_keywords_llm_v2
        close_old_connections()
        extract_keywords_llm_v2(group="domestic")
        close_old_connections()
        extract_keywords_llm_v2(group="international")
        return

    view_func = view_map.get(platform)
    if not view_func:
        raise ValueError(f"No view mapped for platform: {platform}")

    factory = RequestFactory()
    request = factory.get('/', params) if params else factory.get('/')
    response = view_func(request)

    if response.status_code != 200:
        raise RuntimeError(f"Fetch failed: platform={platform} status={response.status_code}")

# 默认从批量执行中排除的任务（耗时过长，应单独运行）
_DEFAULT_EXCLUDE = {'keyword_analysis_llm'}


class Command(BaseCommand):
    help = 'Run all configured tasks once immediately'

    def add_arguments(self, parser):
        parser.add_argument(
            '--platform',
            type=str,
            help='Only run tasks for specific platform(s), comma-separated'
        )
        parser.add_argument(
            '--exclude',
            type=str,
            help='Exclude specific platform(s), comma-separated. '
                 'Default excludes: keyword_analysis_llm'
        )
        parser.add_argument(
            '--parallel',
            action='store_true',
            help='Run tasks in parallel (default: sequential)'
        )
        parser.add_argument(
            '--include-all',
            action='store_true',
            help='Include all tasks, ignoring default exclusions'
        )

    def handle(self, *args, **options):
        platform_filter = options.get('platform')
        exclude_filter = options.get('exclude')
        parallel = options.get('parallel', False)
        include_all = options.get('include_all', False)
        
        # 构建排除集合
        exclude_set = set()
        if not include_all:
            exclude_set = _DEFAULT_EXCLUDE.copy()
        if exclude_filter:
            exclude_set.update(p.strip() for p in exclude_filter.split(','))
        
        # 获取配置
        scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})
        
        if not scheduler_config:
            self.stdout.write(self.style.ERROR('No tasks configured in SCHEDULER_CONFIG'))
            return
        
        # 过滤任务
        tasks_to_run = []
        excluded_tasks = []
        for platform, config in scheduler_config.items():
            # 检查是否启用
            if not config.get('enabled', True):
                continue
            
            # 检查平台过滤（--platform 指定时忽略排除规则）
            if platform_filter:
                platforms = [p.strip() for p in platform_filter.split(',')]
                if platform not in platforms:
                    continue
            else:
                # 检查排除
                if platform in exclude_set:
                    excluded_tasks.append(platform)
                    continue
            
            params = config.get('params', {})
            tasks_to_run.append((platform, params))
        
        if not tasks_to_run:
            self.stdout.write(self.style.WARNING('No tasks to run'))
            return
        
        if excluded_tasks:
            self.stdout.write(
                self.style.WARNING(f'Excluded (run separately): {", ".join(excluded_tasks)}')
            )
        
        self.stdout.write(self.style.SUCCESS(f'Running {len(tasks_to_run)} tasks...'))
        
        # 执行任务
        if parallel:
            self._run_parallel(tasks_to_run)
        else:
            self._run_sequential(tasks_to_run)
    
    def _run_sequential(self, tasks):
        """顺序执行任务"""
        total_start = time.time()
        success_count = 0
        failed_count = 0
        
        for i, (platform, params) in enumerate(tasks, 1):
            self.stdout.write(f'\n[{i}/{len(tasks)}] Running: {platform}')
            
            try:
                start = time.time()
                _run_fetch_direct(platform, **params)
                elapsed = time.time() - start
                
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Completed in {elapsed:.1f}s')
                )
                success_count += 1
            except Exception as e:
                elapsed = time.time() - start
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Failed in {elapsed:.1f}s: {e}')
                )
                failed_count += 1
        
        total_elapsed = time.time() - total_start
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'Total: {len(tasks)} tasks'))
        self.stdout.write(self.style.SUCCESS(f'Success: {success_count}'))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f'Failed: {failed_count}'))
        self.stdout.write(f'Total time: {total_elapsed:.1f}s')
        self.stdout.write('='*60)

    
    def _run_parallel(self, tasks):
        """并行执行任务"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        total_start = time.time()
        success_count = 0
        failed_count = 0
        
        self.stdout.write(f'Running {len(tasks)} tasks in parallel...\n')
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            # 提交所有任务
            future_to_platform = {
                executor.submit(_run_fetch_direct, platform, **params): platform
                for platform, params in tasks
            }
            
            # 等待完成
            for future in as_completed(future_to_platform):
                platform = future_to_platform[future]
                try:
                    future.result()
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ {platform} completed')
                    )
                    success_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ {platform} failed: {e}')
                    )
                    failed_count += 1
        
        total_elapsed = time.time() - total_start
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'Total: {len(tasks)} tasks'))
        self.stdout.write(self.style.SUCCESS(f'Success: {success_count}'))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f'Failed: {failed_count}'))
        self.stdout.write(f'Total time: {total_elapsed:.1f}s')
        self.stdout.write('='*60)
