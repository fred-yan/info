"""
命令行入口：提取热点关键词
用法:
    python manage.py extract_keywords
    python manage.py extract_keywords --group domestic
    python manage.py extract_keywords --top 30
"""
import json
from django.core.management.base import BaseCommand
from parser_api.keyword_extractor import extract_keywords


class Command(BaseCommand):
    help = "从最近一次抓取的新闻标题中提取热点关键词"

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            type=str,
            choices=["domestic", "international"],
            default=None,
            help="只分析指定分组 (domestic/international)",
        )
        parser.add_argument(
            "--top",
            type=int,
            default=50,
            help="每组返回前 N 个关键词 (默认 50)",
        )

    def handle(self, *args, **options):
        group = options["group"]
        top = options["top"]

        self.stdout.write(f"开始提取关键词 group={group or 'all'} top={top}")

        result = extract_keywords(group=group, top=top)

        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS("完成"))
