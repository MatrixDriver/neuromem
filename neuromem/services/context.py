"""Context inference service - infer user context from query embedding."""

from __future__ import annotations

import logging
import math

from neuromem.providers.embedding import EmbeddingProvider

logger = logging.getLogger(__name__)


CONTEXT_PROTOTYPE_SENTENCES: dict[str, list[str]] = {
    "work": [
        "帮我写一个 Python 函数",
        "这个 API 接口怎么设计",
        "代码审查发现了一个 bug",
        "明天有个技术评审会议",
        "部署到生产环境",
        "项目架构需要重构",
        "数据库查询太慢了需要优化",
        "这个模块的单元测试怎么写",
        "CI/CD 流水线配置有问题",
        "这个需求的技术方案怎么做",
        "线上出了一个紧急故障",
        "代码合并有冲突需要解决",
        "这个功能的性能指标是什么",
        "项目进度需要更新一下",
        "帮我做一下代码重构",
        "Help me write a Python function",
        "How should I design this API endpoint",
        "Found a bug during code review",
        "I have a technical review meeting tomorrow",
        "Deploy to production environment",
        "The project architecture needs refactoring",
        "Database query is too slow and needs optimization",
        "How to write unit tests for this module",
        "CI/CD pipeline configuration has issues",
        "What's the technical approach for this requirement",
        "There's an urgent production incident",
        "Need to resolve merge conflicts",
        "What are the performance metrics for this feature",
        "Need to update the project progress",
        "Help me refactor this code",
    ],
    "personal": [
        "周末去哪里玩",
        "晚饭吃什么好",
        "最近在看一部电视剧",
        "我妈妈生日快到了",
        "今天天气真好想出去走走",
        "最近睡眠质量不太好",
        "家里需要买些什么东西",
        "推荐一部好看的电影",
        "最近在减肥控制饮食",
        "宠物猫今天不太舒服",
        "想买一台新的笔记本电脑",
        "假期准备去旅行",
        "最近在学做饭",
        "健身计划怎么安排",
        "家里要装修了",
        "Where should I go this weekend",
        "What should I have for dinner",
        "I've been watching a TV series lately",
        "My mom's birthday is coming up",
        "The weather is nice today I want to go for a walk",
        "My sleep quality has been poor lately",
        "What do I need to buy for home",
        "Recommend a good movie",
        "I'm on a diet controlling my food intake",
        "My cat doesn't feel well today",
        "I want to buy a new laptop",
        "Planning to travel during the holiday",
        "I've been learning to cook recently",
        "How should I plan my fitness routine",
        "My home needs renovation",
    ],
    "social": [
        "朋友聚会怎么安排",
        "同事关系不太好怎么处理",
        "社交场合穿什么合适",
        "如何拒绝别人的邀请",
        "团建活动有什么好的建议",
        "和朋友吵架了怎么和好",
        "第一次见面聊什么话题好",
        "怎么维持长距离的友谊",
        "邻居太吵了怎么沟通",
        "送朋友什么礼物好",
        "同学聚会要不要参加",
        "怎么在社交中给人留下好印象",
        "约会去哪里比较好",
        "如何处理人际冲突",
        "怎么扩大社交圈子",
        "How to plan a friends gathering",
        "How to deal with difficult colleague relationships",
        "What to wear for social occasions",
        "How to decline an invitation politely",
        "Any good suggestions for team building activities",
        "Had a fight with a friend how to make up",
        "What topics to talk about when meeting someone for the first time",
        "How to maintain long-distance friendships",
        "My neighbor is too noisy how to communicate",
        "What gift should I get for a friend",
        "Should I attend the class reunion",
        "How to make a good impression in social settings",
        "Where is a good place for a date",
        "How to handle interpersonal conflicts",
        "How to expand my social circle",
    ],
    "learning": [
        "这个概念的原理是什么",
        "推荐一些学习资源",
        "怎么入门机器学习",
        "这篇论文的核心观点是什么",
        "有没有好的在线课程推荐",
        "这个数学公式怎么推导",
        "如何提高英语口语水平",
        "这个历史事件的背景是什么",
        "量子计算的基本概念是什么",
        "怎么系统地学习一门新技能",
        "这本书的主要内容是什么",
        "深度学习和传统机器学习有什么区别",
        "这个实验的设计思路是什么",
        "怎么写好一篇学术论文",
        "请解释一下这个理论",
        "What's the principle behind this concept",
        "Recommend some learning resources",
        "How to get started with machine learning",
        "What are the key points of this paper",
        "Are there any good online courses you'd recommend",
        "How to derive this mathematical formula",
        "How to improve English speaking skills",
        "What's the historical background of this event",
        "What are the basic concepts of quantum computing",
        "How to systematically learn a new skill",
        "What are the main contents of this book",
        "What's the difference between deep learning and traditional ML",
        "What's the design approach of this experiment",
        "How to write a good academic paper",
        "Please explain this theory",
    ],
}

CONTEXT_KEYWORDS: dict[str, set[str]] = {
    "work": {"代码", "项目", "API", "部署", "会议", "deadline", "code", "debug",
             "重构", "测试", "review", "上线", "需求", "sprint", "issue", "bug",
             "服务器", "数据库", "接口", "编程", "开发", "server", "deploy",
             "commit", "merge", "pull request", "CI", "CD"},
    "personal": {"周末", "家里", "旅行", "做饭", "朋友", "家人", "生日", "假期",
                 "看电影", "运动", "健身", "宠物", "减肥", "睡眠", "装修",
                 "weekend", "home", "travel", "cooking", "family", "birthday",
                 "holiday", "movie", "exercise", "fitness", "pet"},
    "social": {"聚会", "社交", "团建", "聊天", "约会", "关系", "邻居", "同事",
               "礼物", "party", "gathering", "date", "relationship",
               "colleague", "friend", "gift", "reunion"},
    "learning": {"学习", "教程", "原理", "论文", "课程", "入门", "理解", "概念",
                 "公式", "理论", "实验", "学术", "study", "tutorial", "theory",
                 "paper", "course", "concept", "formula", "research",
                 "principle", "textbook"},
}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors (pure Python)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class ContextService:
    """Context inference service - infer user context from query embedding.

    Pure computation service, no database access. Prototype vectors are
    lazily loaded and cached in memory.
    """

    MARGIN_THRESHOLD = 0.05
    MAX_CONTEXT_BOOST = 0.10
    GENERAL_CONTEXT_BOOST = 0.07
    CONFIDENCE_NORMALIZER = 0.15

    def __init__(self, embedding: EmbeddingProvider):
        self._embedding = embedding
        self._prototypes: dict[str, list[float]] | None = None
        self._prototype_norms: dict[str, float] | None = None

    async def ensure_prototypes(self) -> None:
        """Lazily initialize prototype vectors. Skips if already cached."""
        if self._prototypes is not None:
            return

        try:
            all_sentences: list[str] = []
            context_ranges: dict[str, tuple[int, int]] = {}
            offset = 0
            for ctx, sentences in CONTEXT_PROTOTYPE_SENTENCES.items():
                context_ranges[ctx] = (offset, offset + len(sentences))
                all_sentences.extend(sentences)
                offset += len(sentences)

            logger.warning(
                "Context prototype init: embedding %d sentences...",
                len(all_sentences),
            )
            embeddings = await self._embedding.embed_batch(all_sentences)
            logger.warning(
                "Context prototype init: got %d embeddings",
                len(embeddings),
            )

            self._prototypes = {}
            self._prototype_norms = {}
            dims = len(embeddings[0]) if embeddings else 0
            for ctx, (start, end) in context_ranges.items():
                ctx_embeddings = embeddings[start:end]
                mean_vec = [
                    sum(e[d] for e in ctx_embeddings) / len(ctx_embeddings)
                    for d in range(dims)
                ]
                self._prototypes[ctx] = mean_vec
                self._prototype_norms[ctx] = math.sqrt(sum(x * x for x in mean_vec))

            logger.info(
                "Context prototypes initialized: %d contexts, %d dims",
                len(self._prototypes), dims,
            )
        except Exception as e:
            logger.warning("Failed to initialize context prototypes: %s", e)
            self._prototypes = {}
            self._prototype_norms = {}

    def infer_context(
        self, query_embedding: list[float], query_text: str = ""
    ) -> tuple[str, float]:
        """Infer the most likely context from a query embedding.

        Returns:
            (context_label, confidence) where confidence=0 means general/unknown.
        """
        if not self._prototypes:
            logger.warning("infer_context: no prototypes, returning general")
            return ("general", 0.0)

        query_norm = math.sqrt(sum(x * x for x in query_embedding))
        if query_norm == 0:
            return ("general", 0.0)

        similarities: dict[str, float] = {}
        for ctx, proto in self._prototypes.items():
            proto_norm = self._prototype_norms.get(ctx, 0.0)
            if proto_norm == 0:
                similarities[ctx] = 0.0
                continue
            dot = sum(q * p for q, p in zip(query_embedding, proto))
            similarities[ctx] = dot / (query_norm * proto_norm)

        sorted_items = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
        best_ctx, best_score = sorted_items[0]
        second_score = sorted_items[1][1] if len(sorted_items) > 1 else 0.0
        margin = best_score - second_score

        if margin < self.MARGIN_THRESHOLD:
            kw_result = self._infer_context_keywords(query_text)
            if kw_result:
                return kw_result
            return ("general", 0.0)

        confidence = min(margin / self.CONFIDENCE_NORMALIZER, 1.0)
        return (best_ctx, confidence)

    def _infer_context_keywords(self, query_text: str) -> tuple[str, float] | None:
        """Keyword fallback inference."""
        if not query_text:
            return None

        query_lower = query_text.lower()
        scores: dict[str, int] = {}
        for ctx, keywords in CONTEXT_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw.lower() in query_lower)
            if count > 0:
                scores[ctx] = count

        if not scores:
            return None

        best_ctx = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_count = scores[best_ctx]
        if best_count >= 2:
            return (best_ctx, 0.6)
        elif best_count == 1:
            tied = [ctx for ctx, c in scores.items() if c == 1]
            if len(tied) == 1:
                return (best_ctx, 0.4)
        return None

    def clear_prototypes(self) -> None:
        """Clear prototype vector cache."""
        self._prototypes = None
        self._prototype_norms = None
        logger.info("Context prototypes cache cleared")
