import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

os.makedirs(BASE_DIR / "logs", exist_ok=True)

SECRET_KEY = 'django-insecure-dev-only-key-change-in-production'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'parser_api',
]

ROOT_URLCONF = 'django_api.urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'info_api',
        'USER': 'root',
        'PASSWORD': 'mysql@123',
        'HOST': '47.106.210.117',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'connect_timeout': 10,
            'read_timeout': 30,
            'write_timeout': 30,
        },
        'CONN_MAX_AGE': 0,  # 每次请求后关闭连接，避免长时间空闲超时
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/app.log",
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "formatter": "standard",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "news_homepage_parser": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "parser_api": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# ==================== 定时任务配置 ====================
# 是否启用调度器
SCHEDULER_ENABLED = True

# 调度器时区
SCHEDULER_TIMEZONE = 'Asia/Shanghai'

# 定时任务配置 - 使用 crontab 格式
# 格式: "分 时 日 月 周"
# 示例:
#   "*/30 * * * *"  - 每30分钟
#   "0 */6 * * *"   - 每6小时
#   "0 8 * * *"     - 每天8点
#   "0 0 * * 0"     - 每周日0点
SCHEDULER_CONFIG = {
    'economist': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'apnews': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'ftchinese': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'wsj': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'kr36': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'huxiu': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'zaobao': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'zaobao_hotlist': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'github_trending_daily': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
        'params': {'since': 'daily'},
    },
    'github_trending_weekly': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
        'params': {'since': 'weekly'},
    },
    'github_trending_monthly': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
        'params': {'since': 'monthly'},
    },
    'hacker_news': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'zhihu': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'weibo': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'pengpai': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'washingtonpost': {
        'cron': '0 6,12,18,0 * * *',  # 每天6/12/18/0点
        'enabled': True,
    },
    'keyword_analysis': {
        'cron': '5 6,12,18,0 * * *',
        'enabled': False,  # 已弃用，改用 LLM 方案
    },
    'keyword_analysis_llm': {
        'cron': '10 6,12,18,0 * * *',  # 抓取后10分钟运行
        'enabled': False,  # 改为由抓取完成后动态触发
    },
}

# ==================== 平台分组配置 ====================
PLATFORM_GROUPS = {
    "domestic": {
        "platforms": ["ftchinese", "wsj", "kr36", "huxiu", "zaobao", "zhihu", "weibo", "pengpai"],
        "label": "国内热点",
        "lang": "zh"
    },
    "international": {
        "platforms": ["economist", "apnews", "washingtonpost", "github", "hackernews"],
        "label": "国际热点",
        "lang": "en"
    }
}
