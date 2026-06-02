"""
命令行入口：LLM 热点短语提取
用法:
    python manage.py extract_keywords_llm
    python manage.py extract_keywords_llm --top 30
    python manage.py extract_keywords_llm --debug-prompt  # 只打印提示词，不调用LLM
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
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="每批标题数量（覆盖默认值 10）",
        )
        parser.add_argument(
            "--debug-prompt",
            action="store_true",
            default=False,
            help="只打印第一批的完整提示词（system + user），不调用 LLM",
        )
        parser.add_argument(
            "--dump-prompt",
            type=str,
            default=None,
            help="将提示词输出到指定文件路径（方便复制到 DeepSeek 界面调试）",
        )

    def handle(self, *args, **options):
        group = options["group"]
        top = options["top"]
        force = options["force"]
        debug_prompt = options["debug_prompt"]
        dump_prompt = options["dump_prompt"]
        batch_size = options["batch_size"]

        if debug_prompt or dump_prompt:
            self._print_prompt(group, dump_prompt, batch_size)
            return

        self.stdout.write(f"开始 LLM 短语提取 group={group} top={top} force={force} batch_size={batch_size or 'default'}")

        result = extract_keywords_llm(group=group, top=top, force=force, batch_size=batch_size)

        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS("完成"))

    def _print_prompt(self, group, dump_path=None, batch_size=None):
        """打印/导出第一批的完整提示词"""
        from django.conf import settings
        from django.db.models import Max
        from parser_api.models import Info
        from parser_api.llm_extractor_tiny import (
            SYSTEM_PROMPT_TEMPLATE, USER_PROMPT_TEMPLATE, TitleInput,
            NewsPhraseExtractor,
        )
        from parser_api.llm_keyword_extractor import BATCH_SIZE

        actual_batch_size = batch_size or BATCH_SIZE

        # 获取标题（和正式流程一样）
        platform_groups = settings.PLATFORM_GROUPS
        cfg = platform_groups.get(group)
        if not cfg:
            self.stderr.write(f"未知分组: {group}")
            return

        platforms = cfg["platforms"]
        titles = []
        for plat in platforms:
            latest = Info.objects.filter(platform=plat).aggregate(latest=Max('date'))['latest']
            if latest:
                batch = Info.objects.filter(platform=plat, date=latest)
                for info in batch:
                    if info.title and info.title.strip():
                        titles.append(info.title.strip())

        unique_titles = list(dict.fromkeys(titles))
        self.stdout.write(f"总标题数: {len(unique_titles)}，批次大小: {actual_batch_size}")
        self.stdout.write(f"第一批标题数: {min(actual_batch_size, len(unique_titles))}")
        self.stdout.write("")

        # 取第一批
        first_batch = unique_titles[:actual_batch_size]
        title_inputs = [TitleInput(id=str(i+1), title=t) for i, t in enumerate(first_batch)]

        extractor = NewsPhraseExtractor()
        formatted = extractor._format_titles(title_inputs)
        user_prompt = USER_PROMPT_TEMPLATE.format(titles=formatted)

        # 构建输出
        output = []
        output.append("=" * 60)
        output.append("SYSTEM PROMPT")
        output.append("=" * 60)
        output.append(SYSTEM_PROMPT_TEMPLATE)
        output.append("")
        output.append("=" * 60)
        output.append("USER PROMPT")
        output.append("=" * 60)
        output.append(user_prompt)
        output.append("")
        output.append("=" * 60)
        output.append(f"预估输入长度: system={len(SYSTEM_PROMPT_TEMPLATE)} chars, user={len(user_prompt)} chars")
        output.append(f"标题数: {len(first_batch)}")
        output.append("=" * 60)

        full_output = "\n".join(output)

        if dump_path:
            with open(dump_path, 'w', encoding='utf-8') as f:
                f.write(full_output)
            self.stdout.write(self.style.SUCCESS(f"提示词已导出到: {dump_path}"))
        else:
            self.stdout.write(full_output)
