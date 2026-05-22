import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI

# ============= Prompt 模板定义 =============

SYSTEM_PROMPT_TEMPLATE = """你是一个新闻标题短语抽取与归纳助手,专门处理中文新闻标题。
你的任务不是判断哪些标题更热门,也不是生成摘要,而是对输入的一批新闻标题进行结构化短语标注与归纳,供后续算法计算热点分数。
你必须完成两个层面的工作:

【任务一:逐条标题双层短语输出】
对于每一条标题,输出两层短语:
1. extracted_phrases - 必须直接来自标题原文 - 不能改写,不能意译,不能新增标题中没有出现的词 - 应尽量是标题中连续或近连续出现的短语片段 - 优先保留高质量短语
2. normalized_phrases - 基于 extracted_phrases 进行轻度规范化 - 可以做适度合并、术语标准化、表达统一,使其更适合作为后续聚合标签 - 但不能脱离标题原意,不能凭空添加标题中没有表达的概念 - 不要过度上位概括,不要输出空泛抽象词

【任务二:批量短语归纳】
在完成每条标题的双层短语输出后,对整批标题中的 normalized_phrases 做归纳:
- 将语义相同或高度相近的 normalized_phrases 归并为同一个短语组
- 输出每个短语组对应的标题编号
- 输出各标题中对应的原始表达 surface_forms

【高质量短语标准】
优先抽取以下类型:
- 命名实体
- 名词短语
- 事件短语
- 政策术语
- 经济术语
- 科技术语
- 其他可独立表达明确主题的短语

【禁止输出的内容】
不要抽取或输出以下内容:
- 完整句子
- 纯动词片段
- 新闻套话,例如:官方表示、记者获悉、最新消息、作出回应
- 无法独立表达含义的碎片
- 过于空泛抽象的概括,例如:国际局势、相关问题、经济情况、政治方面
- 单独的国家/地区名称,例如:中国、美国、日本、欧洲、俄罗斯、印度。国家名只有作为更具体短语的组成部分时才可保留,例如"中美关税战"、"美国加征关税"可以,但单独的"中国"、"美国"不可以

【包含关系处理】
如果多个短语互相包含,优先保留更完整、更自然、更适合作为新闻标签的短语。

【数量限制】
- 每条标题最多输出 3 个 extracted_phrases
- 每条标题最多输出 3 个 normalized_phrases

【批量归纳规则】
- 一个标题可以同时属于多个短语组
- 不要只给出全局总结,必须保留逐标题结果
- 不要根据主观判断删除标题
- 只做短语抽取、规范化、归纳,不做热点排序

【输出要求】
- 只输出符合以下 JSON Schema 的结构化数据
- 不要输出解释、注释、说明文字
- 不要遗漏任何输入标题
- title 字段必须原样保留输入标题
- id 必须与输入编号一致(整数类型)

【输出 JSON Schema】
{{"type": "object", "properties": {{"items": {{"type": "array", "items": {{"type": "object", "properties": {{"id": {{"type": "integer"}}, "title": {{"type": "string"}}, "extracted_phrases": {{"type": "array", "items": {{"type": "string"}}}}, "normalized_phrases": {{"type": "array", "items": {{"type": "string"}}}}}}, "required": ["id", "title", "extracted_phrases", "normalized_phrases"]}}}}, "phrase_groups": {{"type": "array", "items": {{"type": "object", "properties": {{"normalized_phrase": {{"type": "string"}}, "member_titles": {{"type": "array", "items": {{"type": "integer"}}}}, "surface_forms": {{"type": "array", "items": {{"type": "string"}}}}}}, "required": ["normalized_phrase", "member_titles", "surface_forms"]}}}}}}, "required": ["items", "phrase_groups"]}}

如果某条标题没有足够高质量的短语,可输出较少短语,但不要为了凑数量而输出低质量短语。
"""

USER_PROMPT_TEMPLATE = """请对以下一批中文新闻标题进行"逐条双层短语抽取 + 批量短语归纳"。

输入标题列表:
{titles}

请严格按照以下要求输出:
1. 对每条标题输出 extracted_phrases(必须直接来自标题原文)和 normalized_phrases(轻度规范化)
2. 对整批标题的 normalized_phrases 做归纳,输出 phrase_groups
3. id 必须是整数类型,与输入中的 id 保持一致
4. 每条标题最多输出 3 个 extracted_phrases 和 3 个 normalized_phrases
5. normalized_phrases 应尽量具体、可作为新闻标签
6. phrase_groups 中的 surface_forms 应使用标题中的原始短语表达

输出必须严格符合上述 JSON Schema。
"""


# ============= 数据模型定义 =============

class TitleInput(BaseModel):
    """标题输入模型"""
    id: str = Field(..., description="标题唯一标识")
    title: str = Field(..., description="新闻标题内容")


class ExtractedItem(BaseModel):
    """抽取结果项"""
    id: int = Field(..., description="标题ID(整数格式)")
    title: str = Field(..., description="新闻标题")
    extracted_phrases: List[str] = Field(default_factory=list, description="原文短语列表")
    normalized_phrases: List[str] = Field(default_factory=list, description="规范化短语列表")


class PhraseGroup(BaseModel):
    """短语组"""
    normalized_phrase: str = Field(..., description="规范化后的短语")
    member_titles: List[int] = Field(..., description="包含该短语的标题ID列表")
    surface_forms: List[str] = Field(..., description="各标题中的原始表达")


class ExtractionResult(BaseModel):
    """完整抽取结果"""
    items: List[ExtractedItem] = Field(..., description="逐条抽取结果")
    phrase_groups: List[PhraseGroup] = Field(..., description="短语归纳组")


# ============= 配置定义 =============

class LLMConfig:
    """大模型调用配置"""
    MODEL = "qwen3.5-plus"
    API_KEY = "sk-d0e245edaa9047dfa006f8217a1c49a3"
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MAX_TOKENS = 8192
    TEMPERATURE = 0.1


# ============= 核心逻辑 =============

class NewsPhraseExtractor:
    """新闻短语抽取器 - 使用 OpenAI SDK"""

    def __init__(self, config: LLMConfig = None):
        self.config = config or LLMConfig()
        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=self.config.API_KEY,
            base_url=self.config.BASE_URL
        )

    def _format_titles(self, titles: List[TitleInput]) -> str:
        """格式化标题列表为字符串"""
        formatted_lines = []
        for item in titles:
            formatted_lines.append(f"{item.id}. {item.title}")
        return "\n".join(formatted_lines)

    def extract(self, titles: List[TitleInput]) -> Dict:
        """
        执行短语抽取和归纳

        Args:
            titles: 标题输入列表

        Returns:
            符合 ExtractionResult 结构的字典
        """
        if not titles:
            return {"items": [], "phrase_groups": []}

        # 构建 User Prompt
        formatted_titles = self._format_titles(titles)
        user_prompt = USER_PROMPT_TEMPLATE.format(titles=formatted_titles)

        try:
            # 使用 OpenAI SDK 调用模型
            response = self.client.chat.completions.create(
                model=self.config.MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.TEMPERATURE,
                max_tokens=self.config.MAX_TOKENS,
                response_format={"type": "json_object"}  # 强制 JSON 输出
            )

            # 提取并解析 JSON
            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            # 使用 Pydantic 验证结果结构
            validated_result = ExtractionResult(**result)

            # 返回验证后的字典
            return validated_result.model_dump()

        except Exception as e:
            print(f"错误详情: {str(e)}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"短语抽取失败: {str(e)}")


# ============= 使用示例 =============

if __name__ == "__main__":
    # 示例输入: 带有 id 和 title 的字典列表
    sample_input = [
        {"id": "1", "title": "央行宣布下调存款准备金率0.5个百分点"},
        {"id": "2", "title": "降准落地 A股三大指数集体高开"},
        {"id": "3", "title": "银行板块走强 市场关注降准影响"}
    ]

    # 转换为 TitleInput 对象
    titles = [TitleInput(**item) for item in sample_input]

    # 创建抽取器实例
    extractor = NewsPhraseExtractor()

    # 执行抽取
    try:
        result = extractor.extract(titles)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        # 验证输出格式
        print("\n=== 验证结果 ===")
        print(f"抽取条目数: {len(result['items'])}")
        print(f"短语组数: {len(result['phrase_groups'])}")

        # 验证 ID 类型
        print(f"第一个条目的 ID 类型: {type(result['items'][0]['id'])}")

    except Exception as e:
        print(f"抽取失败: {str(e)}")