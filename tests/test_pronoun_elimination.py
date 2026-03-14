"""Test that sliding window extraction eliminates pronouns and produces self-contained memories.
Uses real LLM (Kimi K2.5) for extraction quality verification.
"""
import json
import pytest

# Mark all tests as slow (requires real API calls)
pytestmark = pytest.mark.slow


@pytest.fixture
def kimi_llm():
    from neuromem.providers.openai_llm import OpenAILLM

    class KimiK2LLM(OpenAILLM):
        """Kimi K2.5 only accepts temperature=1."""

        async def chat(self, messages, temperature=1.0, max_tokens=2048):
            return await super().chat(messages, temperature=1.0, max_tokens=max_tokens)

    return KimiK2LLM(
        api_key="sk-OvyTvj94ZANCpIK5iK15BrjPon02CfuSrXLNEHORyxmabGEf",
        model="kimi-k2.5",
        base_url="https://api.moonshot.cn/v1",
    )


def _parse_json_response(text: str) -> dict:
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    assert json_start >= 0, f"No JSON in response: {text[:200]}"
    return json.loads(text[json_start:json_end])


class TestPronounElimination:

    async def test_pronouns_resolved_in_window_extraction(self, kimi_llm):
        """Messages with pronouns should produce self-contained extracted memories."""
        from neuromem._core import NeuroMemory

        # This is a conversation with heavy pronoun usage
        messages = [
            {"role": "user", "content": "我叫张三，在腾讯工作，是一个后端工程师"},
            {"role": "assistant", "content": "你好张三！作为后端工程师在腾讯一定很忙吧"},
            {"role": "user", "content": "是啊，他们最近让我负责一个新项目，用Go语言重写支付系统"},
            {"role": "assistant", "content": "支付系统重写是个大工程，用Go是个好选择"},
            {"role": "user", "content": "对，我上周和我老婆去了日本旅游，她特别喜欢京都"},
            {"role": "assistant", "content": "京都确实很美，你们玩得开心吗"},
            {"role": "user", "content": "开心，我们还去了东京，那边的拉面太好吃了，我决定以后每年都去"},
        ]

        msg_text = "\n\n".join(f"[{m['role']}]: {m['content']}" for m in messages)

        # _build_zh_window_prompt is an instance method; use an unbound call with a dummy instance
        # We only need the method body which only uses msg_text and previous_summary
        nm = object.__new__(NeuroMemory)
        prompt = nm._build_zh_window_prompt(msg_text, "")

        # Call LLM
        response = await kimi_llm.chat([{"role": "user", "content": prompt}])
        text = response if isinstance(response, str) else str(response)
        data = _parse_json_response(text)

        facts = data.get("facts", [])
        episodes = data.get("episodes", [])
        all_memories = facts + episodes

        assert len(all_memories) > 0, "Should extract at least some memories"

        # Check for unresolved pronouns
        pronouns_to_check = ["他们", "她"]

        problematic = []
        for mem in all_memories:
            content = mem if isinstance(mem, str) else mem.get("content", "")
            # "他们" without "腾讯" is problematic
            if "他们" in content and "腾讯" not in content:
                problematic.append((content, "他们"))
            # "她" without reference to wife is problematic
            if "她" in content and not any(w in content for w in ["老婆", "妻子", "张三"]):
                problematic.append((content, "她"))

        print("\n=== Extracted Facts ===")
        for f in facts:
            c = f if isinstance(f, str) else f.get("content", "")
            print(f"  - {c}")
        print("\n=== Extracted Episodes ===")
        for e in episodes:
            c = e if isinstance(e, str) else e.get("content", "")
            print(f"  - {c}")

        if problematic:
            print("\n=== Problematic (unresolved pronouns) ===")
            for content, pronoun in problematic:
                print(f"  - [{pronoun}] {content}")

        # Allow up to 1 unresolved pronoun (LLM isn't perfect)
        assert len(problematic) <= 1, f"Too many unresolved pronouns: {problematic}"

    async def test_english_pronouns_resolved(self, kimi_llm):
        """English conversation with pronouns should also produce self-contained memories."""
        from neuromem._core import NeuroMemory

        messages = [
            {"role": "user", "content": "My name is Alice and I work at Google as a product manager"},
            {"role": "assistant", "content": "Nice to meet you Alice! Product management at Google sounds exciting"},
            {"role": "user", "content": "Yeah, my husband Bob is also in tech, he works at Meta"},
            {"role": "assistant", "content": "That's a tech power couple!"},
            {"role": "user", "content": "He just got promoted to senior engineer last week. We celebrated at a Japanese restaurant"},
        ]

        msg_text = "\n\n".join(f"[{m['role']}]: {m['content']}" for m in messages)

        nm = object.__new__(NeuroMemory)
        prompt = nm._build_en_window_prompt(msg_text, "")

        response = await kimi_llm.chat([{"role": "user", "content": prompt}], max_tokens=4096)
        text = response if isinstance(response, str) else str(response)
        data = _parse_json_response(text)

        facts = data.get("facts", [])
        episodes = data.get("episodes", [])
        all_memories = facts + episodes

        assert len(all_memories) > 0

        # Check for unresolved "he", "she", "they" without proper context
        problematic = []
        for mem in all_memories:
            content = mem if isinstance(mem, str) else mem.get("content", "")
            content_lower = content.lower()
            # "he" without "Bob" or "husband" is problematic
            if " he " in content_lower and "bob" not in content_lower and "husband" not in content_lower:
                problematic.append((content, "he"))
            # "she" without "Alice" is problematic
            if " she " in content_lower and "alice" not in content_lower:
                problematic.append((content, "she"))

        print("\n=== Extracted Memories ===")
        for m in all_memories:
            c = m if isinstance(m, str) else m.get("content", "")
            print(f"  - {c}")

        if problematic:
            print("\n=== Problematic (unresolved pronouns) ===")
            for content, pronoun in problematic:
                print(f"  - [{pronoun}] {content}")

        assert len(problematic) <= 1, f"Unresolved pronouns: {problematic}"
