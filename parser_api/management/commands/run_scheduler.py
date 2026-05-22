"""
独立运行调度器的管理命令
用法: python manage.py run_scheduler
"""
from django.core.management.base import BaseCommand
from parser_api.scheduler import setup_scheduler, shutdown_scheduler
import signal
import sys
import time


class Command(BaseCommand):
    help = 'Run the news fetching scheduler'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting scheduler...'))
        
        # 设置信号处理
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('\nShutting down scheduler...'))
            shutdown_scheduler()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 启动调度器
        scheduler = setup_scheduler()
        
        if scheduler is None:
            self.stdout.write(self.style.ERROR('Failed to start scheduler'))
            return
        
        self.stdout.write(self.style.SUCCESS('Scheduler is running. Press Ctrl+C to exit.'))
        
        # 显示已注册的任务
        jobs = scheduler.get_jobs()
        if jobs:
            self.stdout.write(self.style.SUCCESS(f'\nRegistered {len(jobs)} tasks:'))
            for job in jobs:
                next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'N/A'
                self.stdout.write(f'  - {job.name}: next run at {next_run}')
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nShutting down...'))
            shutdown_scheduler()
