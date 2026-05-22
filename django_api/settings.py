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

import configparser

_db_config = configparser.ConfigParser()
_db_config_path = BASE_DIR / 'db_config.ini'
if not _db_config_path.exists():
    raise FileNotFoundError(
        f"数据库配置文件不存在: {_db_config_path}\n"
        f"请复制 db_config.ini.example 为 db_config.ini 并填入真实的数据库连接信息"
    )
_db_config.read(_db_config_path, encoding='utf-8')
_db = _db_config['database']

DATABASES = {
    'default': {
        'ENGINE': _db.get('engine', 'django.db.backends.mysql'),
        'NAME': _db.get('name', 'info_api'),
        'USER': _db.get('user', 'root'),
        'PASSWORD': _db.get('password', ''),
        'HOST': _db.get('host', '127.0.0.1'),
        'PORT': _db.get('port', '3306'),
        'OPTIONS': {
            'charset': _db.get('charset', 'utf8mb4'),
            'connect_timeout': int(_db.get('connect_timeout', '10')),
            'read_timeout': int(_db.get('read_timeout', '30')),
            'write_timeout': int(_db.get('write_timeout', '30')),
        },
        'CONN_MAX_AGE': 0,
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
