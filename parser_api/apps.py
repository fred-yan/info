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
        # 避免在 migrate 等命令时启动调度器
        import sys
        
        # 只在 runserver 或 gunicorn 时启动调度器
        if 'runserver' in sys.argv or 'gunicorn' in sys.argv[0]:
            try:
                from .scheduler import setup_scheduler
                setup_scheduler()
                logger.info("[ParserApiConfig] Scheduler initialized")
            except Exception as e:
                logger.error(f"[ParserApiConfig] Failed to initialize scheduler: {e}", exc_info=True)
