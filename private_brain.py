"""
PrivateBrain - 私有化外挂大脑核心模块

实现 Y 型分流架构：
- 同步路径：检索相关记忆，立即返回结构化上下文
- 异步路径：隐私分类 + 记忆写入（Fire-and-forget）

新增功能：
- Session 管理：内部自动管理短期记忆
- 指代消解：检索时规则匹配，整合时 LLM 消解
"""
import time
import logging
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

from mem0 import Memory

from config import MEM0_CONFIG, create_chat_llm
from privacy_filter import classify_privacy, PrivacyType
from session_manager import get_session_manager, Event
from coreference import get_coreference_resolver
# 延迟导入 consolidator，避免循环导入

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
    memories: list[dict] = field(default_factory=list)  # 语义化命名
    relations: list[dict] = field(default_factory=list)  # 简化命名
    resolved_query: str = ""  # 消解后的查询
    retrieval_time_ms: int = 0
    
    @property
    def has_memory(self) -> bool:
        return len(self.memories) > 0 or len(self.relations) > 0
    
    def to_dict(self) -> dict:
        """转换为 JSON 可序列化的字典"""
        return {
            "status": "success",
            "resolved_query": self.resolved_query,
            "memories": self.memories,
            "relations": self.relations,
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
        
        # Session 管理和指代消解
        self.session_manager = get_session_manager()
        self.coreference_resolver = get_coreference_resolver()
        # 延迟导入 consolidator，避免循环导入
        self._consolidator = None
        
        # 设置整合回调
        self.session_manager.set_consolidate_callback(self._consolidate_session_sync)
        logger.info("PrivateBrain 初始化完成（Session 管理）")
    
    def _get_consolidator(self):
        """延迟获取 consolidator 实例，避免循环导入"""
        if self._consolidator is None:
            from consolidator import get_consolidator
            self._consolidator = get_consolidator()
        return self._consolidator
    
    async def _process_async(self, input_text: str, user_id: str) -> dict:
        """
        处理用户输入的异步实现。
        供 process_async 与 process（仅同步/无 loop 时）使用。
        """
        # 1. 获取或创建 Session
        await self.session_manager.get_or_create_session(user_id)
        
        # 2. 获取最近事件进行指代消解
        context_events = await self.session_manager.get_session_events(user_id, limit=5)
        
        # 3. 消解查询（同步）
        resolved_query = self.coreference_resolver.resolve_query(input_text, context_events)
        
        # 4. 使用消解后的查询检索长期记忆（同步）
        result = self._retrieve(resolved_query, user_id)
        result.resolved_query = resolved_query
        
        # 5. 创建 Event 并添加到 Session
        event = Event(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            role="user",
            content=input_text,  # 存原始输入，不存消解后的
            timestamp=datetime.now(),
        )
        await self.session_manager.add_event(user_id, event)
        
        return result.to_dict()
    
    async def process_async(self, input_text: str, user_id: str) -> dict:
        """
        处理用户输入（生产模式，异步入口）。
        
        在已有 event loop 的上下文中使用（如 FastAPI、MCP）时，应调用本方法并用
        await；否则会因 process() 内部的 asyncio.run() 触发 RuntimeError。
        
        流程同 process()；返回格式（memories/relations/resolved_query）。
        """
        return await self._process_async(input_text, user_id)
    
    def process(self, input_text: str, user_id: str) -> dict:
        """
        处理用户输入（生产模式，同步入口）
        
        仅用于无运行中 event loop 的上下文（如 pytest、CLI、脚本）。从
        async  handler（FastAPI、MCP）调用时请使用 process_async 并 await。
        
        流程：
        1. 获取或创建 Session
        2. 获取最近事件进行指代消解
        3. 使用消解后的查询检索长期记忆
        4. 创建 Event 并添加到 Session
        5. 返回格式（memories/relations/resolved_query）
        """
        return asyncio.run(self._process_async(input_text, user_id))
    
    def process_debug(self, input_text: str, user_id: str) -> str:
        """
        处理用户输入（调试模式，旧版流程）
        
        不写 Session、不做指代消解，仅演示「检索 + 隐私分类 + 存储决策」；
        返回自然语言格式的完整流程说明。生产级流程请使用 process / process_async。
        
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
    
    def get_user_graph(self, user_id: str, depth: int = 2) -> dict:
        """
        获取用户的知识图谱。
        depth 预留：当前 memory.get_all 与 Neo4j 层无深度参数，后续若支持再接入。
        
        Args:
            user_id: 用户标识
            depth: 预留的遍历深度，默认 2，当前未参与查询
            
        Returns:
            用户的知识图谱数据，含 memories、graph_relations、nodes、edges、metadata
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
            
            # 从关系中推导 nodes；edges 与 graph_relations 同构
            unique = set()
            for r in formatted_relations:
                s, t = r.get("source", ""), r.get("target", "")
                if s:
                    unique.add(s)
                if t:
                    unique.add(t)
            nodes = [{"id": n, "name": n} for n in sorted(unique)]
            edges = [
                {
                    "source": r.get("source", ""),
                    "relationship": r.get("relationship", r.get("relation", "")),
                    "target": r.get("target", ""),
                }
                for r in formatted_relations
            ]
            
            return {
                "status": "success",
                "user_id": user_id,
                "memories": [
                    {"id": m.get("id"), "memory": m.get("memory")}
                    for m in memories
                ],
                "graph_relations": formatted_relations,
                "nodes": nodes,
                "edges": edges,
                "metadata": {
                    "memory_count": len(memories),
                    "relation_count": len(formatted_relations),
                },
            }
        except Exception as e:
            logger.error(f"获取用户图谱失败: {e}")
            return {
                "status": "error",
                "user_id": user_id,
                "error": str(e),
            }
    
    def search(self, query: str, user_id: str, limit: int = 10) -> dict:
        """
        仅检索，不存储
        
        Args:
            query: 查询文本
            user_id: 用户标识
            limit: 返回的记忆与关系数量上限，默认 10
            
        Returns:
            检索结果（memories, relations, metadata）
        """
        return self._retrieve(query, user_id, limit=limit).to_dict()
    
    def ask(self, question: str, user_id: str = "default") -> dict:
        """
        基于记忆回答问题：检索 + LLM 生成回答。不写 Session。
        
        Args:
            question: 用户问题
            user_id: 用户标识
            
        Returns:
            {"answer": str, "sources": list}；异常时含 "error" 键
        """
        try:
            r = self._retrieve(question, user_id)
            parts = []
            if r.memories:
                parts.append("记忆：\n" + "\n".join(m.get("content", "") for m in r.memories))
            if r.relations:
                parts.append(
                    "关系：\n"
                    + "\n".join(
                        f"{x.get('source','')} -{x.get('relation','')}- {x.get('target','')}"
                        for x in r.relations
                    )
                )
            context = "\n\n".join(parts) if parts else "（无相关记忆与关系）"
            system = "你是一个基于用户记忆回答问题的助手。请仅根据下述记忆与关系回答，不知道则明确说明。"
            prompt = f"{system}\n\n{context}\n\n问题：{question}"
            llm = create_chat_llm()
            ans = llm.invoke(prompt)
            content = ans.content if hasattr(ans, "content") else str(ans)
            sources = [
                {"type": "memory", "content": m.get("content", ""), "score": m.get("score")}
                for m in r.memories
            ] + [
                {
                    "type": "relation",
                    "source": x.get("source", ""),
                    "relation": x.get("relation", ""),
                    "target": x.get("target", ""),
                }
                for x in r.relations
            ]
            return {"answer": content, "sources": sources}
        except Exception as e:
            logger.error(f"ask 失败: {e}")
            return {"answer": "", "sources": [], "error": str(e)}
    
    def add(self, text: str, user_id: str) -> dict:
        """
        直接添加记忆（跳过隐私过滤）。

        返回 memory_id：若 mem0.add 返回 list 且首项含 id 则使用，否则生成 mem_<uuid12>。
        
        Args:
            text: 要存储的文本
            user_id: 用户标识
            
        Returns:
            {"status":"success","memory_id": str} 或 {"status":"error","error": str}
        """
        try:
            res = self.memory.add(text, user_id=user_id)
            if isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict) and res[0].get("id"):
                mid = str(res[0]["id"])
            else:
                mid = f"mem_{uuid.uuid4().hex[:12]}"
            return {"status": "success", "memory_id": mid}
        except Exception as e:
            logger.error(f"存储失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def _retrieve(self, query: str, user_id: str, limit: int | None = None) -> RetrievalResult:
        """
        内部检索方法。
        limit 为 None 时使用 VECTOR_TOP_K / GRAPH_MAX_RELATIONS，与 process 等原有行为一致。
        
        Args:
            query: 查询文本
            user_id: 用户标识
            limit: 记忆与关系数量上限；None 时用模块常量
            
        Returns:
            RetrievalResult 对象
        """
        start_time = time.perf_counter()
        cap_vec = limit if limit is not None else VECTOR_TOP_K
        cap_rel = limit if limit is not None else GRAPH_MAX_RELATIONS
        
        try:
            search_results = self.memory.search(query, user_id=user_id)
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return RetrievalResult(resolved_query=query)  # 静默降级：返回空结果
        
        # 解析结果
        memories = []
        relations = []
        
        if isinstance(search_results, dict):
            raw_vectors = search_results.get("results", [])
            raw_relations = search_results.get("relations", [])
        elif isinstance(search_results, list):
            raw_vectors = search_results
            raw_relations = []
        else:
            raw_vectors = []
            raw_relations = []
        
        # 处理向量结果（memories）
        for item in raw_vectors[:cap_vec]:
            if isinstance(item, dict):
                memories.append({
                    "content": item.get("memory", str(item)),  # content 替代 memory
                    "score": item.get("score", 0),
                })
        
        # 处理图谱关系（relations，简化字段名）
        deduped_relations = _dedupe_relations(raw_relations)[:cap_rel]
        for rel in deduped_relations:
            relations.append({
                "source": rel.get("source", ""),
                "relation": rel.get("relationship", ""),  # v3: relation 替代 relationship
                "target": rel.get("target", ""),
            })
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        return RetrievalResult(
            memories=memories,
            relations=relations,
            resolved_query=query,
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
    
    async def end_session_async(self, user_id: str) -> dict:
        """
        显式结束用户的当前会话（异步入口）。
        
        在已有 event loop 的上下文中（如 FastAPI、MCP）应调用本方法并 await；
        否则 end_session() 内部的 asyncio.run() 会触发 RuntimeError。
        """
        summary = await self.session_manager.end_session(user_id)
        if summary is None:
            return {
                "status": "success",
                "message": "No active session",
                "session_info": None,
            }
        return {
            "status": "success",
            "message": "Session ending, consolidation started",
            "session_info": summary.to_dict(),
        }
    
    def end_session(self, user_id: str) -> dict:
        """
        显式结束用户的当前会话（同步入口）
        
        仅用于无运行中 event loop 的上下文（如 pytest、CLI）。从
        async handler（FastAPI、MCP）调用时请使用 end_session_async 并 await。
        """
        return asyncio.run(self.end_session_async(user_id))
    
    def _consolidate_session_sync(self, session) -> None:
        """
        同步版本的 Session 整合（用于回调）
        
        Args:
            session: Session 对象
        """
        try:
            result = self._get_consolidator().consolidate(session)
            logger.info(f"Session {session.session_id} 整合完成: {result.to_dict()}")
        except Exception as e:
            logger.error(f"Session {session.session_id} 整合失败: {e}")


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
