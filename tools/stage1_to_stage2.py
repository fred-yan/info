"""
工具脚本：将阶段1的 LLM 输出（JSON）转换为阶段2的输入提示词。

用法:
    python tools/stage1_to_stage2.py stage1_output.json
    python tools/stage1_to_stage2.py stage1_output.json --output stage2_input.txt
    python tools/stage1_to_stage2.py stage1_batch1.json stage1_batch2.json  (合并多个批次)
"""
import json
import sys
import os
from collections import defaultdict

# 阶段2的 system prompt
STAGE2_SYSTEM_PROMPT = """你是一个短语归纳助手。对输入的一批 normalized_phrases 做语义聚类归纳。

【任务】
将语义相同或高度相近的短语归并为同一组，输出每组的代表短语和成员。

【归纳规则】
- 同义词合并：如"降准"和"下调存款准备金率"归为一组
- 同一事件合并：如"SpaceX IPO"和"SpaceX 上市"归为一组
- 不要过度合并：只有语义确实高度相近才归并
- 每组选择最具代表性、最适合做新闻标签的短语作为组名

【输出要求】
只输出 JSON，格式如下:
{"phrase_groups": [{"representative": "代表短语", "members": ["成员1", "成员2", ...], "title_ids": [1, 3, 5]}]}

其中 title_ids 是包含该组短语的标题编号列表。
"""


def convert_stage1_to_stage2(stage1_results: list[dict]) -> str:
    """
    将阶段1的输出转换为阶段2的 user prompt。
    
    Args:
        stage1_results: 阶段1输出的 items 列表（可以是多个批次合并的）
    
    Returns:
        阶段2的完整提示词（system + user）
    """
    # 构建 phrase → title_ids 映射
    phrase_to_ids = defaultdict(set)
    
    for item in stage1_results:
        title_id = item["id"]
        for phrase in item.get("normalized_phrases", []):
            phrase_to_ids[phrase].add(title_id)
    
    # 格式化短语列表
    total_titles = len(stage1_results)
    total_phrases = len(phrase_to_ids)
    
    lines = []
    for phrase, ids in sorted(phrase_to_ids.items(), key=lambda x: -len(x[1])):
        ids_str = ", ".join(str(i) for i in sorted(ids))
        lines.append(f"  \"{phrase}\" → 标题: [{ids_str}]")
    
    phrase_list = "\n".join(lines)
    
    user_prompt = f"""以下是从 {total_titles} 条新闻标题中提取出的 {total_phrases} 个规范化短语，以及对应的标题编号。
请对这些短语进行语义归纳聚类，输出 json 格式：

{phrase_list}
"""
    
    # 拼接完整输出
    output = []
    output.append("=" * 60)
    output.append("【阶段2】SYSTEM PROMPT")
    output.append("=" * 60)
    output.append(STAGE2_SYSTEM_PROMPT)
    output.append("")
    output.append("=" * 60)
    output.append("【阶段2】USER PROMPT")
    output.append("=" * 60)
    output.append(user_prompt)
    output.append("")
    output.append("=" * 60)
    output.append(f"统计: {total_titles} 条标题, {total_phrases} 个唯一短语")
    output.append(f"预估输入: system={len(STAGE2_SYSTEM_PROMPT)} chars, user={len(user_prompt)} chars")
    output.append("=" * 60)
    
    return "\n".join(output)


def main():
    if len(sys.argv) < 2:
        print("用法: python tools/stage1_to_stage2.py <stage1_output.json> [stage1_batch2.json ...] [--output file.txt]")
        print("")
        print("输入: 阶段1的 LLM JSON 输出文件（包含 items 数组）")
        print("输出: 阶段2的完整提示词（可复制到 DeepSeek 界面调试）")
        sys.exit(1)
    
    # 解析参数
    input_files = []
    output_file = None
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        else:
            input_files.append(sys.argv[i])
            i += 1
    
    # 加载并合并所有批次
    all_items = []
    for filepath in input_files:
        with open(filepath, 'r', encoding='utf-8-sig') as f:  # utf-8-sig 自动去除 BOM
            content = f.read().strip()
            if not content:
                print(f"警告: {filepath} 为空文件，跳过")
                continue
            data = json.loads(content)
        
        if isinstance(data, dict) and "items" in data:
            all_items.extend(data["items"])
        elif isinstance(data, list):
            all_items.extend(data)
        else:
            print(f"警告: {filepath} 格式不识别，跳过")
    
    if not all_items:
        print("错误: 没有找到有效的 items 数据")
        sys.exit(1)
    
    print(f"加载了 {len(all_items)} 条标题的提取结果")
    
    # 转换
    result = convert_stage1_to_stage2(all_items)
    
    # 输出
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"阶段2提示词已写入: {output_file}")
    else:
        print(result)


if __name__ == "__main__":
    main()
