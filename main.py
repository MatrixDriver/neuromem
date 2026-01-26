"""
NeuroMemory 主程序
命令行演示工具 - 基于 PrivateBrain 的 Y 型分流架构

架构核心：
- 只检索，不推理（推理交给调用方的主 LLM）
- 隐私过滤：PRIVATE 数据存储，PUBLIC 数据丢弃
- Y 型分流：同步返回检索结果，异步执行存储决策
"""
import re
from typing import Literal

from pydantic import BaseModel

from config import (
    LLM_PROVIDER,
    EMBEDDING_PROVIDER,
    DEEPSEEK_API_KEY,
    DEEPSEEK_CONFIG,
)
from private_brain import PrivateBrain, debug_process_memory


# =============================================================================
# 代词消解模块 (Coreference Resolution)
# =============================================================================

# 用户身份上下文（可扩展为持久化存储）
USER_IDENTITY_CACHE: dict[str, dict] = {}


def extract_user_identity(user_input: str, user_id: str) -> str | None:
    """
    从输入中提取用户身份信息
    
    Args:
        user_input: 用户输入
        user_id: 用户标识
        
    Returns:
        提取到的用户名，如果没有则返回 None
    """
    # 匹配 "我的名字叫XXX"、"我叫XXX"、"我是XXX" 等模式
    patterns = [
        r"我的名字叫(\S+)",
        r"我叫(\S+)",
        r"我是(\S+)",
        r"我的名字是(\S+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, user_input)
        if match:
            name = match.group(1)
            USER_IDENTITY_CACHE[user_id] = {"name": name}
            print(f"[身份提取] 识别到用户名: {name}")
            return name
    return None


def resolve_pronouns(user_input: str, user_id: str) -> str:
    """
    将代词"我"替换为用户名（如果已知）
    
    Args:
        user_input: 用户输入
        user_id: 用户标识
        
    Returns:
        代词消解后的输入
    """
    identity = USER_IDENTITY_CACHE.get(user_id, {})
    user_name = identity.get("name")
    
    if not user_name:
        return user_input
    
    # 排除身份声明语句（不应消解）
    # 如 "我的名字叫小朱" 不应变成 "小朱的名字叫小朱"
    identity_patterns = [
        r"我的名字叫",
        r"我叫",
        r"我是",
        r"我的名字是",
    ]
    for pattern in identity_patterns:
        if re.search(pattern, user_input):
            return user_input  # 身份声明语句，不消解
    
    # 替换"我的"为"用户名的"，"我"为"用户名"
    # 注意：先替换"我的"再替换"我"，避免"我的"变成"用户名的"后又被替换
    resolved = user_input.replace("我的", f"{user_name}的")
    resolved = resolved.replace("我", user_name)
    return resolved


# =============================================================================
# 意图判断模块（仅用于演示输出）
# =============================================================================

class IntentResult(BaseModel):
    """意图判断结果"""
    intent: Literal["personal", "factual", "general"]
    reasoning: str
    needs_external_search: bool


def classify_intent(user_input: str) -> IntentResult:
    """
    通过 DeepSeek LLM 判断用户输入的意图类型
    
    意图类型:
    - personal: 个人信息/记忆查询（如家庭关系、个人偏好等）
    - factual: 需要外部事实知识的查询（如历史事件、科学知识等）
    - general: 通用对话/闲聊
    
    Returns:
        IntentResult: 包含意图类型、推理过程和是否需要外部搜索的结构化结果
    """
    import json
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.0,
        base_url=DEEPSEEK_CONFIG["base_url"],
        api_key=DEEPSEEK_API_KEY,
    )
    
    prompt = f"""分析以下用户输入，判断其意图类型。

用户输入: "{user_input}"

意图类型说明:
1. personal - 涉及个人信息、记忆、关系的查询
   - 例如: "我的名字叫什么"、"小朱的儿子是谁"、"我喜欢什么颜色"
   - 这类查询应该从本地记忆中检索，不需要外部搜索

2. factual - 需要外部事实知识的查询
   - 例如: "谁发明了电灯"、"Python的最新版本是什么"、"今天天气如何"
   - 这类查询可能需要外部搜索或最新信息

3. general - 通用对话或闲聊
   - 例如: "你好"、"谢谢"、"帮我写一首诗"
   - 不需要特定知识检索

请以 JSON 格式返回结果，格式如下：
```json
{{
  "intent": "personal/factual/general 三选一",
  "reasoning": "你的推理过程",
  "needs_external_search": true/false
}}
```

只返回 JSON，不要有其他内容。"""

    response = llm.invoke(prompt)
    content = response.content.strip()
    
    # 提取 JSON（处理可能的 markdown 代码块包装）
    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = content
    
    try:
        data = json.loads(json_str)
        return IntentResult(
            intent=data.get("intent", "general"),
            reasoning=data.get("reasoning", "无法解析推理过程"),
            needs_external_search=data.get("needs_external_search", False),
        )
    except json.JSONDecodeError as e:
        print(f"[警告] 意图解析失败: {e}")
        print(f"[警告] 原始响应: {content}")
        # 返回默认值
        return IntentResult(
            intent="general",
            reasoning="解析失败，使用默认值",
            needs_external_search=False,
        )


# =============================================================================
# 演示函数
# =============================================================================

def demo_v2_architecture():
    """
    演示架构：Y 型分流 + 隐私过滤
    
    展示：
    1. 私有数据被正确存储
    2. 公共知识被丢弃
    3. 检索返回结构化 JSON
    """
    print("=" * 60)
    print("NeuroMemory 架构演示")
    print(f"当前配置: LLM={LLM_PROVIDER}, Embedding={EMBEDDING_PROVIDER}")
    print("=" * 60)
    
    brain = PrivateBrain()
    user_id = "demo_user"
    
    # 演示场景 1: 私有数据（应该存储）
    print("\n" + "=" * 60)
    print("场景 1: 私有数据（个人信息 - 应该存储）")
    print("=" * 60)
    
    private_data = [
        "我的名字叫小朱",
        "小朱有两个孩子",
        "灿灿是小朱的女儿",
        "灿灿还有一个弟弟，叫帅帅",
    ]
    
    for text in private_data:
        print(f"\n>>> 输入: {text}")
        result = brain.process_debug(text, user_id)
        print(result)
    
    # 演示场景 2: 公共知识（应该丢弃）
    print("\n" + "=" * 60)
    print("场景 2: 公共知识（应该丢弃，不存储）")
    print("=" * 60)
    
    public_data = [
        "北京是中国的首都",
        "Python 是一种编程语言",
    ]
    
    for text in public_data:
        print(f"\n>>> 输入: {text}")
        result = brain.process_debug(text, user_id)
        print(result)
    
    # 演示场景 3: 查询（只检索，不存储）
    print("\n" + "=" * 60)
    print("场景 3: 查询（只检索，不存储查询本身）")
    print("=" * 60)
    
    queries = [
        "小朱的儿子叫什么名字？",
        "灿灿有弟弟吗？",
    ]
    
    for query in queries:
        print(f"\n>>> 查询: {query}")
        result = brain.process_debug(query, user_id)
        print(result)
    
    # 演示场景 4: 生产模式（JSON 输出）
    print("\n" + "=" * 60)
    print("场景 4: 生产模式（结构化 JSON 输出）")
    print("=" * 60)
    
    import json
    
    print(f"\n>>> 查询: 小朱有几个孩子？")
    json_result = brain.process("小朱有几个孩子？", user_id)
    print(json.dumps(json_result, ensure_ascii=False, indent=2))


def demo_multi_hop_reasoning():
    """
    演示多跳推理能力
    
    注意：NeuroMemory 只负责检索，不做推理。
    此演示展示检索结果，推理由调用方完成。
    """
    print("=" * 60)
    print("NeuroMemory 多跳检索演示")
    print(f"当前配置: LLM={LLM_PROVIDER}, Embedding={EMBEDDING_PROVIDER}")
    print("=" * 60)
    print("\n注意：NeuroMemory 只负责检索，不做推理。")
    print("以下展示检索结果，推理应由调用方的主 LLM 完成。")
    
    brain = PrivateBrain()
    user_id = "demo_user"
    
    # 构建私有记忆
    print("\n" + "-" * 40)
    print("阶段 1: 构建私有记忆")
    print("-" * 40)
    
    memories = [
        "我的名字叫小朱",
        "小朱有两个孩子",
        "灿灿是小朱的女儿",
        "灿灿还有一个弟弟，叫帅帅",
    ]
    
    for text in memories:
        print(f"\n>>> 存储: {text}")
        # 使用 debug 模式查看存储决策
        result = brain.process_debug(text, user_id)
        print(result)
    
    # 等待异步存储完成
    import time
    print("\n[等待异步存储完成...]")
    time.sleep(3)
    
    # 测试检索
    print("\n" + "-" * 40)
    print("阶段 2: 测试检索能力")
    print("-" * 40)
    
    query = "小朱的儿子叫什么名字？"
    print(f"\n>>> 查询: {query}")
    result = brain.process_debug(query, user_id)
    print(result)
    
    print("\n" + "-" * 40)
    print("提示：根据检索到的信息，调用方 LLM 应能推理出：")
    print("  - 帅帅是灿灿的弟弟（弟弟 = 男性）")
    print("  - 灿灿是小朱的女儿（灿灿是小朱的孩子）")
    print("  - 帅帅是灿灿的弟弟 + 灿灿是小朱的孩子 → 帅帅是小朱的孩子")
    print("  - 帅帅是男性 + 帅帅是小朱的孩子 → 帅帅是小朱的儿子")
    print("-" * 40)


if __name__ == "__main__":
    # 默认运行架构演示
    demo_v2_architecture()
    
    # 也可以运行多跳检索演示
    # demo_multi_hop_reasoning()
