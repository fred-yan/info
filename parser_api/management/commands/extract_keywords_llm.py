"""
命令行入口：LLM 热点短语提取
用法:
    python manage.py extract_keywords_llm
    python manage.py extract_keywords_llm --top 30
"""
import json
from django.core.management.base import BaseCommand
from parser_api.llm_keyword_extractor import extract_keywords_llm


class Command(BaseCommand):
    help = "用大模型从新闻标题中提取热点短语"

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            type=str,
            default="domestic",
            help="分组 (默认 domestic)",
        )
        parser.add_argument(
            "--top",
            type=int,
            default=50,
            help="返回前 N 个短语 (默认 50)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="跳过缓存，强制重新调用 LLM",
        )

    def handle(self, *args, **options):
        group = options["group"]
        top = options["top"]
        force = options["force"]

        self.stdout.write(f"开始 LLM 短语提取 group={group} top={top} force={force}")

        result = extract_keywords_llm(group=group, top=top, force=force)

        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS("完成"))
