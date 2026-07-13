import os
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "8"))

_client = None


SYSTEM_PROMPT = """You are an expert technical interviewer grading candidate answers.
Score 0-3 based on: accuracy, depth, structure, examples, communication.
Return ONLY valid JSON: {"feedback": "string", "points": 0-3, "breakdown": "string"}

SCORING GUIDE:
- 3: Accurate, detailed, well-structured, includes concrete example
- 2: Mostly correct, minor gaps, some structure, maybe an example
- 1: Partial understanding, missing key concepts, weak structure
- 0: Incorrect, vague, or missing core concepts entirely

FEEDBACK STYLE: Direct, constructive, interviewer tone. Mention specific strengths/gaps.
BREAKDOWN: Bullet points of what was covered vs missed."""


def _build_prompt(role: str, question: str, answer: str, meta: dict) -> list[dict]:
    """Build msgs array for OpenAI chat completion."""
    keywords = meta.get("keywords", [])
    concepts = meta.get("concepts", [])
    mistakes = meta.get("common_mistakes", [])
    ideal = meta.get("ideal_length", 80)

    user_content = (
        f"""Role: {role}"
        Question: {question}"
        Target Length: {ideal} words"
        Core concepts: {concepts}"
        Important Keywords: {keywords}"
        Common mistakes: {mistakes}"
        Candidate answer: {answer}"""
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=AI_TIMEOUT,
        )
    return _client


def ai_grade(role: str, question: str, answer: str, meta: dict) -> Optional[dict]:
    """
    Returns dict with keys: feedback, points, breakdown
    Returns None if AI disabled, no key, or any error (caller falls back to rule-based)
    """
    if not AI_ENABLED:
        return None
    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        messages = _build_prompt(role, question, answer, meta)
        client = _get_client()

        resp = client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"},
        )

        content = resp.choices[0].message.content
        result = json.loads(content)

        if not all(k in result for k in ("feedback", "points", "breakdown")):
            return None
        if not isinstance(result["points"], int) or not 0 <= result["points"] <= 3:
            return None

        return result
    except Exception:
        return None