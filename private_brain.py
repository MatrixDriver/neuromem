"""
PrivateBrain - 私有化外挂大脑核心模块

实现 Y 型分流架构：
- 同步路径：检索相关记忆，立即返回结构化上下文
- 异步路径：隐私分类 + 记忆写入（Fire-and-forget）
"""
import time
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from mem0 import Memory

from config import MEM0_CONFIG
from privacy_filter import classify_privacy, PrivacyType

# 配置日志
logger = logging.getLogger("neuro_memory.brain")

# =============================================================================
# 配置参数
# =============================================================================

# 向量检索返回的最大结果数
VECTOR_TOP_K = 5

# 图谱检索返回的最大关系数
GRAPH_MAX_RELATIONS = 10

# 图谱多跳推理的最大深度
GRAPH_MAX_DEPTH = 2


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class RetrievalResult:
    """检索结果"""
    vector_chunks: list[dict] = field(default_factory=list)
    graph_relations: list[dict] = field(default_factory=list)
    retrieval_time_ms: int = 0
    
    @property
    def has_memory(self) -> bool:
        return len(self.vector_chunks) > 0 or len(self.graph_relations) > 0
    
    def to_dict(self) -> dict:
        """转换为 JSON 可序列化的字典"""
        return {
            "status": "success",
            "vector_chunks": self.vector_chunks,
            "graph_relations": self.graph_relations,
            "metadata": {
                "retrieval_time_ms": self.retrieval_time_ms,
                "has_memory": self.has_memory,
            }
        }


@dataclass
class DebugInfo:
    """调试信息"""
    # 检索信息
    query: str = ""
    vector_results_raw: list[dict] = field(default_factory=list)
    graph_results_raw: list[dict] = field(default_factory=list)
    
    # 存储决策
    privacy_type: PrivacyType | None = None
    privacy_reason: str = ""
    will_store: bool = False
    
    # 性能统计
    retrieval_time_ms: int = 0
    privacy_classify_time_ms: int = 0
    total_time_ms: int = 0
    
    def to_natural_language(self) -> str:
        """生成自然语言格式的调试报告"""
        lines = []
        
        # 检索过程
        lines.append("=== 检索过程 ===")
        lines.append(f'[向量检索] 查询: "{self.query}"')
        if self.vector_results_raw:
            for item in self.vector_results_raw[:VECTOR_TOP_K]:
                memory = item.get("memory", str(item))
                score = item.get("score", "N/A")
                lines.append(f'  - 匹配: "{memory}" (score: {score})')
        else:
            lines.append("  - 无匹配结果")
        
        lines.append("")
        lines.append("[图谱检索]")
        if self.graph_results_raw:
            for rel in self.graph_results_raw[:GRAPH_MAX_RELATIONS]:
                source = _extract_name(rel.get("source", "?"))
                relationship = _normalize_relation(rel.get("relationship", "?"))
                target = _extract_name(rel.get("target", "?"))
                lines.append(f"  - {source} --[{relationship}]--> {target}")
        else:
            lines.append("  - 无关联关系")
        
        # 存储决策
        lines.append("")
        lines.append("=== 存储决策 ===")
        if self.privacy_type:
            lines.append(f"[LLM 分类] 类型: {self.privacy_type}")
            lines.append(f"[分类理由] {self.privacy_reason}")
            decision = "存储" if self.will_store else "不存储"
            lines.append(f"[决策] {decision}")
        else:
            lines.append("[等待分类中...]")
        
        # 性能统计
        lines.append("")
        lines.append("=== 性能统计 ===")
        lines.append(f"- 检索耗时: {self.retrieval_time_ms}ms")
        if self.privacy_classify_time_ms > 0:
            lines.append(f"- 隐私分类耗时: {self.privacy_classify_time_ms}ms")
        lines.append(f"- 总耗时: {self.total_time_ms}ms")
        
        # 原始数据
        lines.append("")
        lines.append("=== 原始数据 ===")
        lines.append(f"向量结果数量: {len(self.vector_results_raw)}")
        lines.append(f"图谱关系数量: {len(self.graph_results_raw)}")
        
        return "\n".join(lines)


# =============================================================================
# 辅助函数
# =============================================================================

# 关系类型映射（英文 → 中文）
RELATION_NORMALIZE_MAP = {
    "daughter": "女儿",
    "son": "儿子",
    "has": "有",
    "has_name": "名字",
    "has_daughter": "有女儿",
    "has_son": "有儿子",
    "brother": "弟弟",
    "sister": "姐妹",
    "father": "父亲",
    "mother": "母亲",
    "parent": "父母",
    "child": "孩子",
    "name": "名字",
    "states_that": "陈述",
    "responds_to_query_about": "回应查询",
}


def _normalize_relation(rel_type: Any) -> str:
    """归一化关系类型"""
    if isinstance(rel_type, dict):
        rel_type = rel_type.get("type", rel_type.get("name", str(rel_type)))
    rel_str = str(rel_type).lower()
    return RELATION_NORMALIZE_MAP.get(rel_str, str(rel_type))


def _extract_name(entity: Any) -> str:
    """从实体中提取名称"""
    if isinstance(entity, dict):
        return entity.get("name", entity.get("id", str(entity)))
    return str(entity)


def _dedupe_relations(relations: list[dict]) -> list[dict]:
    """对图谱关系进行去重"""
    seen = set()
    deduped = []
    for rel in relations:
        source = _extract_name(rel.get("source", "?"))
        relationship = _normalize_relation(rel.get("relationship", "?"))
        target = _extract_name(rel.get("target", "?"))
        key = f"{source}|{relationship}|{target}"
        if key not in seen:
            seen.add(key)
            deduped.append({
                "source": source,
                "relationship": relationship,
                "target": target,
            })
    return deduped


# =============================================================================
# PrivateBrain 核心类
# =============================================================================

class PrivateBrain:
    """
    私有化外挂大脑
    
    提供记忆检索和存储服务，采用 Y 型分流架构：
    - 同步路径：立即检索，返回结构化上下文
    - 异步路径：隐私分类 + 记忆写入
    """
    
    def __init__(self):
        """初始化 PrivateBrain"""
        self.memory = Memory.from_config(MEM0_CONFIG)
        self._executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="brain_consolidate"
        )
        logger.info("PrivateBrain 初始化完成")
    
    def process(self, input_text: str, user_id: str) -> dict:
        """
        处理用户输入（生产模式）
        
        同步返回检索结果，异步执行存储。
        
        Args:
            input_text: 用户输入
            user_id: 用户标识
            
        Returns:
            结构化 JSON 格式的检索结果
        """
        # 同步检索
        result = self._retrieve(input_text, user_id)
        
        # 异步存储（Fire-and-forget）
        self._executor.submit(
            self._background_consolidate,
            input_text,
            user_id
        )
        
        return result.to_dict()
    
    def process_debug(self, input_text: str, user_id: str) -> str:
        """
        处理用户输入（调试模式）
        
        返回自然语言格式的完整流程说明。
        
        Args:
            input_text: 用户输入
            user_id: 用户标识
            
        Returns:
            自然语言格式的调试报告
        """
        total_start = time.perf_counter()
        
        # 创建调试信息
        debug_info = DebugInfo(query=input_text)
        
        # 检索
        retrieval_start = time.perf_counter()
        search_results = self.memory.search(input_text, user_id=user_id)
        debug_info.retrieval_time_ms = int((time.perf_counter() - retrieval_start) * 1000)
        
        # 解析检索结果
        if isinstance(search_results, dict):
            debug_info.vector_results_raw = search_results.get("results", [])
            debug_info.graph_results_raw = search_results.get("relations", [])
        elif isinstance(search_results, list):
            debug_info.vector_results_raw = search_results
        
        # 隐私分类（同步执行以获取结果）
        classify_start = time.perf_counter()
        privacy_type, reason = classify_privacy(input_text)
        debug_info.privacy_classify_time_ms = int((time.perf_counter() - classify_start) * 1000)
        
        debug_info.privacy_type = privacy_type
        debug_info.privacy_reason = reason
        debug_info.will_store = (privacy_type == "PRIVATE")
        
        # 如果是私有数据，执行存储
        if debug_info.will_store:
            self._executor.submit(
                self._store_memory,
                input_text,
                user_id
            )
        
        debug_info.total_time_ms = int((time.perf_counter() - total_start) * 1000)
        
        return debug_info.to_natural_language()
    
    def get_user_graph(self, user_id: str) -> dict:
        """
        获取用户的知识图谱
        
        Args:
            user_id: 用户标识
            
        Returns:
            用户的知识图谱数据
        """
        try:
            # 使用空查询来获取用户的所有记忆
            all_memories = self.memory.get_all(user_id=user_id)
            
            # 提取图谱关系（如果有）
            relations = []
            memories = []
            
            if isinstance(all_memories, dict):
                memories = all_memories.get("results", [])
                relations = all_memories.get("relations", [])
            elif isinstance(all_memories, list):
                memories = all_memories
            
            # 去重和格式化关系
            formatted_relations = _dedupe_relations(relations) if relations else []
            
            return {
                "status": "success",
                "user_id": user_id,
                "memories": [
                    {"id": m.get("id"), "memory": m.get("memory")}
                    for m in memories
                ],
                "graph_relations": formatted_relations,
                "metadata": {
                    "memory_count": len(memories),
                    "relation_count": len(formatted_relations),
                }
            }
        except Exception as e:
            logger.error(f"获取用户图谱失败: {e}")
            return {
                "status": "error",
                "user_id": user_id,
                "error": str(e),
            }
    
    def search(self, query: str, user_id: str) -> dict:
        """
        仅检索，不存储
        
        Args:
            query: 查询文本
            user_id: 用户标识
            
        Returns:
            检索结果
        """
        return self._retrieve(query, user_id).to_dict()
    
    def add(self, text: str, user_id: str) -> dict:
        """
        直接添加记忆（跳过隐私过滤）
        
        Args:
            text: 要存储的文本
            user_id: 用户标识
            
        Returns:
            存储结果
        """
        try:
            self.memory.add(text, user_id=user_id)
            return {"status": "success", "stored": True}
        except Exception as e:
            logger.error(f"存储失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def _retrieve(self, query: str, user_id: str) -> RetrievalResult:
        """
        内部检索方法
        
        Args:
            query: 查询文本
            user_id: 用户标识
            
        Returns:
            RetrievalResult 对象
        """
        start_time = time.perf_counter()
        
        try:
            search_results = self.memory.search(query, user_id=user_id)
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return RetrievalResult()  # 静默降级：返回空结果
        
        # 解析结果
        vector_chunks = []
        graph_relations = []
        
        if isinstance(search_results, dict):
            raw_vectors = search_results.get("results", [])
            raw_relations = search_results.get("relations", [])
        elif isinstance(search_results, list):
            raw_vectors = search_results
            raw_relations = []
        else:
            raw_vectors = []
            raw_relations = []
        
        # 处理向量结果
        for item in raw_vectors[:VECTOR_TOP_K]:
            if isinstance(item, dict):
                vector_chunks.append({
                    "memory": item.get("memory", str(item)),
                    "score": item.get("score", 0),
                })
        
        # 处理图谱关系
        graph_relations = _dedupe_relations(raw_relations)[:GRAPH_MAX_RELATIONS]
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        return RetrievalResult(
            vector_chunks=vector_chunks,
            graph_relations=graph_relations,
            retrieval_time_ms=elapsed_ms,
        )
    
    def _background_consolidate(self, text: str, user_id: str) -> None:
        """
        后台记忆整合（隐私分类 + 存储）
        
        Args:
            text: 用户输入
            user_id: 用户标识
        """
        try:
            # 隐私分类
            privacy_type, reason = classify_privacy(text)
            logger.info(f"[隐私分类] {privacy_type}: {reason}")
            
            if privacy_type == "PRIVATE":
                self._store_memory(text, user_id)
            else:
                logger.info(f"[跳过存储] 公共知识: {text[:50]}...")
                
        except Exception as e:
            logger.error(f"后台整合失败: {e}")
    
    def _store_memory(self, text: str, user_id: str) -> None:
        """
        存储记忆
        
        Args:
            text: 要存储的文本
            user_id: 用户标识
        """
        try:
            self.memory.add(text, user_id=user_id)
            logger.info(f"[记忆存储] 成功: {text[:50]}...")
        except Exception as e:
            logger.error(f"记忆存储失败: {e}")


# =============================================================================
# 模块级便捷函数
# =============================================================================

_brain_instance: PrivateBrain | None = None


def get_brain() -> PrivateBrain:
    """获取 PrivateBrain 单例"""
    global _brain_instance
    if _brain_instance is None:
        _brain_instance = PrivateBrain()
    return _brain_instance


def process_memory(input_text: str, user_id: str) -> dict:
    """
    处理记忆（生产模式）
    
    Args:
        input_text: 用户输入
        user_id: 用户标识
        
    Returns:
        结构化 JSON 格式的检索结果
    """
    return get_brain().process(input_text, user_id)


def debug_process_memory(input_text: str, user_id: str) -> str:
    """
    处理记忆（调试模式）
    
    Args:
        input_text: 用户输入
        user_id: 用户标识
        
    Returns:
        自然语言格式的调试报告
    """
    return get_brain().process_debug(input_text, user_id)


def get_user_graph(user_id: str) -> dict:
    """
    获取用户知识图谱
    
    Args:
        user_id: 用户标识
        
    Returns:
        用户的知识图谱数据
    """
    return get_brain().get_user_graph(user_id)
