"""
Session 整合器

负责将 Session 中的短期记忆整合为长期记忆：
1. 语义分组 + 指代消解
2. 隐私过滤
3. 存储到长期记忆
"""
import logging
from dataclasses import dataclass
from typing import Optional

from session_manager import Session
from coreference import get_coreference_resolver, CoreferenceResolver
from privacy_filter import get_privacy_filter, PrivacyFilter

logger = logging.getLogger("neuro_memory.consolidator")


@dataclass
class ConsolidationResult:
    """整合结果"""
    stored_count: int = 0
    total_events: int = 0
    skipped: bool = False
    reason: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "stored_count": self.stored_count,
            "total_events": self.total_events,
            "skipped": self.skipped,
            "reason": self.reason,
        }


class SessionConsolidator:
    """Session 整合器"""
    
    def __init__(
        self,
        coreference: Optional[CoreferenceResolver] = None,
        privacy_filter: Optional[PrivacyFilter] = None,
    ):
        """
        初始化整合器
        
        Args:
            coreference: 指代消解器（默认使用单例）
            privacy_filter: 隐私过滤器（默认使用单例）
        """
        self.coreference = coreference or get_coreference_resolver()
        self.privacy_filter = privacy_filter or get_privacy_filter()
        # 延迟导入，避免循环导入
        self._brain = None
        logger.info("SessionConsolidator 初始化完成")
    
    def _get_brain(self):
        """延迟获取 brain 实例，避免循环导入"""
        if self._brain is None:
            from private_brain import get_brain
            self._brain = get_brain()
        return self._brain
    
    def consolidate(self, session: Session) -> ConsolidationResult:
        """
        整合 Session 到长期记忆
        
        流程:
        1. 跳过空 Session
        2. LLM 语义分组 + 指代消解
        3. 隐私过滤（跳过 PUBLIC 和消解失败的）
        4. 存入长期记忆（Qdrant + Neo4j）
        
        Args:
            session: 要整合的 Session
            
        Returns:
            ConsolidationResult: 整合统计
        """
        # 跳过空 Session
        if not session.events:
            logger.info(f"Session {session.session_id} 为空，跳过整合")
            return ConsolidationResult(
                skipped=True,
                reason="empty_session",
                total_events=0,
            )
        
        try:
            # 1. LLM 消解 + 合并
            logger.info(f"开始整合 Session {session.session_id}: {len(session.events)} 条事件")
            resolved_memories = self.coreference.resolve_events(session.events)
            
            if not resolved_memories:
                logger.warning(f"Session {session.session_id} 消解后无有效记忆")
                return ConsolidationResult(
                    skipped=True,
                    reason="no_resolved_memories",
                    total_events=len(session.events),
                )
            
            # 2. 隐私过滤 + 存储
            stored_count = 0
            for memory in resolved_memories:
                try:
                    privacy_type, reason = self.privacy_filter.classify(memory)
                    logger.debug(f"[隐私分类] {privacy_type}: {memory[:50]}...")
                    
                    if privacy_type == "PRIVATE":
                        # 存储到长期记忆
                        self._get_brain().add(memory, user_id=session.user_id)
                        stored_count += 1
                        logger.info(f"[存储记忆] {memory[:50]}...")
                    else:
                        logger.info(f"[跳过存储] PUBLIC: {memory[:50]}...")
                        
                except Exception as e:
                    logger.error(f"处理记忆失败: {memory[:50]}... 错误: {e}")
                    continue
            
            logger.info(f"Session {session.session_id} 整合完成: {stored_count}/{len(resolved_memories)} 条记忆已存储")
            
            return ConsolidationResult(
                stored_count=stored_count,
                total_events=len(session.events),
            )
            
        except Exception as e:
            logger.error(f"Session {session.session_id} 整合失败: {e}")
            return ConsolidationResult(
                skipped=True,
                reason=f"consolidation_error: {str(e)}",
                total_events=len(session.events),
            )


# =============================================================================
# 模块级单例
# =============================================================================

_consolidator_instance: Optional[SessionConsolidator] = None


def get_consolidator() -> SessionConsolidator:
    """获取 SessionConsolidator 单例"""
    global _consolidator_instance
    if _consolidator_instance is None:
        _consolidator_instance = SessionConsolidator()
    return _consolidator_instance
