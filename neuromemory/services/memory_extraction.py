"""Memory extraction service - Extract and store memories from conversations."""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from neuromemory.models.conversation import Conversation
from neuromemory.models.memory import Embedding
from neuromemory.providers.embedding import EmbeddingProvider
from neuromemory.providers.llm import LLMProvider
from neuromemory.services.kv import KVService

logger = logging.getLogger(__name__)


class MemoryExtractionService:
    """Service for extracting memories from conversations using LLM."""

    def __init__(
        self,
        db: AsyncSession,
        embedding: EmbeddingProvider,
        llm: LLMProvider,
    ):
        self.db = db
        self._embedding = embedding
        self._llm = llm

    async def extract_from_messages(
        self,
        user_id: str,
        messages: list[Conversation],
    ) -> dict[str, int]:
        """Extract memories from a list of conversation messages.

        Returns:
            Statistics: {preferences_extracted, facts_extracted, episodes_extracted, messages_processed}
        """
        if not messages:
            return {
                "preferences_extracted": 0,
                "facts_extracted": 0,
                "episodes_extracted": 0,
                "messages_processed": 0,
            }

        message_dicts = [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ]

        classified = await self._classify_messages(message_dicts, user_id)

        prefs_count = await self._store_preferences(user_id, classified["preferences"])
        facts_count = await self._store_facts(user_id, classified["facts"])
        episodes_count = await self._store_episodes(user_id, classified["episodes"])

        return {
            "preferences_extracted": prefs_count,
            "facts_extracted": facts_count,
            "episodes_extracted": episodes_count,
            "messages_processed": len(messages),
        }

    async def _classify_messages(
        self,
        messages: list[dict],
        user_id: str,
    ) -> dict[str, list[dict]]:
        """Classify messages using LLM."""
        conversation_text = self._format_conversation(messages)
        prompt = self._build_classification_prompt(conversation_text, user_id)

        try:
            result_text = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048,
            )
            extracted = self._parse_classification_result(result_text)
            return extracted
        except Exception as e:
            logger.error("Classification failed: %s", e, exc_info=True)
            return {"preferences": [], "facts": [], "episodes": []}

    def _format_conversation(self, messages: list[dict]) -> str:
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _build_classification_prompt(self, conversation: str, user_id: str) -> str:
        return f"""分析以下对话，提取用户的记忆信息。请严格按照 JSON 格式返回结果。

对话内容：
```
{conversation}
```

请提取以下三类记忆：

1. **Preferences（偏好）**: 用户的喜好、习惯、设置
   - 格式: {{"key": "偏好名称", "value": "偏好值", "confidence": 0.0-1.0}}
   - key 应该用英文，value 可以是中文

2. **Facts（事实）**: 用户的客观信息
   - 格式: {{"content": "事实描述", "category": "分类", "confidence": 0.0-1.0}}
   - category 可选: work, skill, hobby, personal, education, location

3. **Episodes（情景）**: 事件、经历、时间相关信息
   - 格式: {{"content": "事件描述", "timestamp": "时间信息或null", "confidence": 0.0-1.0}}

要求：
- 只提取明确提到的信息，不要推测
- confidence 表示提取的确信度 (0.0-1.0)
- 如果某类没有信息，返回空列表
- 必须返回有效的 JSON 格式，不要有其他文字说明

返回格式（只返回 JSON，不要其他内容）：
```json
{{
  "preferences": [...],
  "facts": [...],
  "episodes": [...]
}}
```"""

    def _parse_classification_result(self, result_text: str) -> dict[str, list[dict]]:
        """Parse LLM classification result."""
        try:
            text = result_text.strip()

            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()

            result = json.loads(text)

            if not isinstance(result, dict):
                raise ValueError("Result is not a dictionary")

            preferences = result.get("preferences", [])
            facts = result.get("facts", [])
            episodes = result.get("episodes", [])

            if not isinstance(preferences, list):
                preferences = []
            if not isinstance(facts, list):
                facts = []
            if not isinstance(episodes, list):
                episodes = []

            return {
                "preferences": preferences,
                "facts": facts,
                "episodes": episodes,
            }

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from classification result: %s", e)
            return {"preferences": [], "facts": [], "episodes": []}
        except Exception as e:
            logger.error("Error parsing classification result: %s", e)
            return {"preferences": [], "facts": [], "episodes": []}

    async def _store_preferences(
        self,
        user_id: str,
        preferences: list[dict],
    ) -> int:
        count = 0
        kv_service = KVService(self.db)
        for pref in preferences:
            key = pref.get("key")
            value = pref.get("value")
            if not key or not value:
                continue
            try:
                await kv_service.set(
                    namespace="preferences",
                    scope_id=user_id,
                    key=key,
                    value=value,
                )
                count += 1
            except Exception as e:
                logger.error("Failed to store preference %s: %s", key, e)
        return count

    async def _store_facts(
        self,
        user_id: str,
        facts: list[dict],
    ) -> int:
        count = 0
        for fact in facts:
            content = fact.get("content")
            category = fact.get("category", "general")
            confidence = fact.get("confidence", 1.0)
            if not content:
                continue
            try:
                embedding_vector = await self._embedding.embed(content)
                embedding_obj = Embedding(
                    user_id=user_id,
                    content=content,
                    embedding=embedding_vector,
                    memory_type="fact",
                    metadata_={
                        "category": category,
                        "confidence": confidence,
                        "extracted_from": "conversation",
                    },
                )
                self.db.add(embedding_obj)
                count += 1
            except Exception as e:
                logger.error("Failed to store fact: %s", e)

        if count > 0:
            await self.db.commit()

        return count

    async def _store_episodes(
        self,
        user_id: str,
        episodes: list[dict],
    ) -> int:
        count = 0
        for episode in episodes:
            content = episode.get("content")
            timestamp = episode.get("timestamp")
            confidence = episode.get("confidence", 1.0)
            if not content:
                continue
            try:
                embedding_vector = await self._embedding.embed(content)
                embedding_obj = Embedding(
                    user_id=user_id,
                    content=content,
                    embedding=embedding_vector,
                    memory_type="episodic",
                    metadata_={
                        "timestamp": timestamp,
                        "confidence": confidence,
                        "extracted_from": "conversation",
                    },
                )
                self.db.add(embedding_obj)
                count += 1
            except Exception as e:
                logger.error("Failed to store episode: %s", e)

        if count > 0:
            await self.db.commit()

        return count
