"""
Parser API 应用配置
"""
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class ParserApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parser_api'

    def ready(self):
        """
        应用启动时初始化调度器
        """
        import os
        import sys
        
        # 只在 runserver 或 gunicorn 时启动调度器
        if 'runserver' not in sys.argv and 'gunicorn' not in sys.argv[0]:
            return

        # Django runserver 的 auto-reloader 会启动两个进程：
        # 主进程（监控文件变化）和子进程（实际运行服务）
        # RUN_MAIN=true 表示是子进程（实际运行的那个）
        # 只在子进程中启动调度器，避免重复注册
        if os.environ.get('RUN_MAIN') != 'true':
            return

        try:
            from .scheduler import setup_scheduler
            setup_scheduler()
            logger.info("[ParserApiConfig] Scheduler initialized")
        except Exception as e:
            logger.error(f"[ParserApiConfig] Failed to initialize scheduler: {e}", exc_info=True)
