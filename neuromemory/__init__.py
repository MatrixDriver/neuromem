"""
NeuroMemory - 神经符号混合记忆系统 Python SDK

封装 PrivateBrain，提供 add / search / ask / get_graph 接口。
"""

import logging
from typing import Any

from private_brain import get_brain

logger = logging.getLogger("neuromemory.sdk")

__all__ = ["NeuroMemory"]


class NeuroMemory:
    """
    神经符号混合记忆系统主接口。

    委托 PrivateBrain（get_brain()），不重复实现业务逻辑。
    config 非 None 时首版忽略并 log，使用默认 get_brain()。
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        if config is not None:
            logger.debug(
                "NeuroMemory(config=...) 暂未使用 config，将使用默认 get_brain()"
            )
        self._brain = get_brain()

    def add(
        self,
        content: str,
        user_id: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        添加记忆。

        Args:
            content: 要记忆的文本内容
            user_id: 用户标识
            metadata: 可选元数据，接受但暂不持久化

        Returns:
            memory_id: 记忆唯一标识

        Raises:
            ValueError: brain.add 返回 status=="error" 时
        """
        _ = metadata  # 接受不传 brain
        r = self._brain.add(content, user_id)
        if r.get("status") == "error":
            raise ValueError(r.get("error", "添加失败"))
        return r["memory_id"]

    def search(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 10,
    ) -> dict:
        """
        混合检索记忆。

        Args:
            query: 查询文本
            user_id: 用户标识
            limit: 返回结果数量上限

        Returns:
            与 brain.search 一致的 dict（memories, relations, metadata）
        """
        return self._brain.search(query, user_id, limit=limit)

    def ask(self, question: str, user_id: str = "default") -> str:
        """
        基于记忆回答问题。

        Args:
            question: 用户问题
            user_id: 用户标识

        Returns:
            AI 生成的回答

        Raises:
            ValueError: brain.ask 返回含 error 时
        """
        r = self._brain.ask(question, user_id)
        if r.get("error"):
            raise ValueError(r["error"])
        return r["answer"]

    def get_graph(self, user_id: str = "default", depth: int = 2) -> dict:
        """
        获取用户的知识图谱。

        Args:
            user_id: 用户标识
            depth: 遍历深度（当前由 brain 预留）

        Returns:
            图谱数据，含 status, nodes, edges, metadata 等
        """
        return self._brain.get_user_graph(user_id, depth=depth)
