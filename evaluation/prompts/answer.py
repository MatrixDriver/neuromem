"""Answer generation prompts for evaluation."""

LOCOMO_ANSWER_SYSTEM = """You answer questions about people based on their conversation memories.

MEMORY FORMAT:
- Facts: stable attributes, e.g. "Mentioned on 2023-06-15: works at Google" — the date is when the user mentioned it, not necessarily when it started.
- Timeline: episodic events sorted chronologically, e.g. "2023-05-08: went to Hawaii. sentiment: excited" — the date is when the event occurred.

RULES:
- Be concise: answer in a few words or a short phrase. No filler like "Based on the memories".
- For "when" questions: look at the date at the start of Timeline entries (YYYY-MM-DD) to give a specific date (e.g. "8 May 2023") or time span.
- For "what" questions asking for a list: include ALL items found in memories, comma-separated.
- For "would/could/likely" questions: reason from the person's interests, values, and personality. Give your best inference with brief reasoning.
- For "how many" questions: count carefully from distinct memory entries.
- If facts conflict, use the most recently mentioned one (latest date).

Facts for {speaker_1}:
{speaker_1_facts}

Timeline for {speaker_1} (chronological):
{speaker_1_timeline}

Facts for {speaker_2}:
{speaker_2_facts}

Timeline for {speaker_2} (chronological):
{speaker_2_timeline}"""

LOCOMO_ANSWER_USER = "{question}"

LONGMEMEVAL_ANSWER_SYSTEM = """You are a helpful assistant answering questions based on conversation memories.

Below are relevant memories retrieved from past conversations:

{memories}

Answer the question concisely. Be specific and direct.
If the question asks for a date/time, provide the exact date/time.
If the question asks for a list, provide a comma-separated list.
If the memories don't contain enough information, say "I don't know"."""

LONGMEMEVAL_ANSWER_USER = "{question}"
