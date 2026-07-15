import os
import json
import time
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-5-20250929")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "8"))

_failure_count = 0
_circuit_open_until = 0
CIRCUIT_THRESHOLD = 5
CIRCUIT_COOLDOWN_SECONDS = 60

logger = logging.getLogger(__name__)


def _check_circuit() -> bool:
    global _circuit_open_until
    if _circuit_open_until > time.time():
        return False
    if _failure_count >= CIRCUIT_THRESHOLD:
        _circuit_open_until = time.time() + CIRCUIT_COOLDOWN_SECONDS
        return False
    return True


def _record_success():
    global _failure_count, _circuit_open_until
    _failure_count = 0
    _circuit_open_until = 0


def _record_failure():
    global _failure_count
    if _circuit_open_until <= time.time():
        _failure_count += 1


def _load_system_prompt() -> str:
    version = os.getenv("PROMPT_VERSION", "v1.0")
    path = f"prompts/{version}_system.txt"
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return """You are an expert technical interviewer grading candidate answers.
Score 0-3 based on: accuracy, depth, structure, examples, communication.
Return ONLY valid JSON: {"feedback": "string", "points": 0-3, "breakdown": "string"}

SCORING GUIDE:
- 3: Accurate, detailed, well-structured, includes concrete example
- 2: Mostly correct, minor gaps, some structure, maybe an example
- 1: Partial understanding, missing key concepts, weak structure
- 0: Incorrect, vague, or missing core concepts entirely

FEEDBACK STYLE: Direct, constructive, interviewer tone. Mention specific strengths/gaps.
BREAKDOWN: Bullet points of what was covered vs missed."""


SYSTEM_PROMPT = _load_system_prompt()


def _build_prompt(role: str, question: str, answer: str, meta: dict) -> str:
    keywords = meta.get("keywords", [])
    concepts = meta.get("concepts", [])
    mistakes = meta.get("common_mistakes", [])
    ideal = meta.get("ideal_length", 80)

    return (
        f"""Role: {role}"
Question: {question}"
Target Length: {ideal} words"
Core concepts: {concepts}"
Important Keywords: {keywords}"
Common mistakes: {mistakes}"
Candidate answer: {answer}"""
    )


def _get_claude_client():
    import anthropic
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```"):
            text = "\n".join(lines[1:-1])
    return text.strip()


def _extract_text_from_response(resp) -> str:
    for block in resp.content:
        if hasattr(block, "text") and block.text:
            return _strip_markdown_fences(block.text)
    return ""


def _rule_based_grade(role: str, question: str, answer: str, meta: dict) -> dict:
    from app import grade as rule_grade
    feedback, points, breakdown = rule_grade(role, answer, question)
    return {
        "feedback": feedback,
        "points": points,
        "breakdown": breakdown,
        "_meta": {"fallback_reason": "rule_based"}
    }


def ai_grade(role: str, question: str, answer: str, meta: dict) -> Optional[dict]:
    start_time = time.time()

    if not AI_ENABLED:
        return _rule_based_grade(role, question, answer, meta)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _rule_based_grade(role, question, answer, meta)

    if not _check_circuit():
        logger.warning("Circuit breaker open, falling back")
        return _rule_based_grade(role, question, answer, meta)

    try:
        prompt = _build_prompt(role, question, answer, meta)
        client = _get_claude_client()

        resp = client.messages.create(
            model=AI_MODEL,
            max_tokens=1024,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        latency_ms = int((time.time() - start_time) * 1000)

        content = _extract_text_from_response(resp)
        result = json.loads(content)

        if not all(k in result for k in ("feedback", "points", "breakdown")):
            return None
        if not isinstance(result["points"], int) or not 0 <= result["points"] <= 3:
            return None

        _record_success()

        result["_meta"] = {
            "tokens_in": resp.usage.input_tokens,
            "tokens_out": resp.usage.output_tokens,
            "latency_ms": latency_ms,
            "model": AI_MODEL,
            "prompt_version": os.getenv("PROMPT_VERSION", "v1.0"),
            "fallback_reason": None,
        }

        logger.info(f"AI graded: role={role} points={result['points']} "
                    f"tokens={resp.usage.input_tokens}/{resp.usage.output_tokens} latency={latency_ms}ms")

        return result

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"AI grading failed: {e} (latency={latency_ms}ms)")
        _record_failure()
        error_str = str(e).lower()
        if "quota" in error_str or "429" in error_str or "rate limit" in error_str:
            logger.warning("Quota exceeded, falling back to rule-based grading")
            return _rule_based_grade(role, question, answer, meta)
        return _rule_based_grade(role, question, answer, meta)


CORRECT_SYSTEM_PROMPT = """You are an expert technical interviewer improving candidate answers.
Given a question, the candidate's answer, and the grading feedback, produce an IMPROVED version.
Return ONLY valid JSON:
{
  "improved_answer": "string - the complete improved answer",
  "changes": [
    {"type": "add|replace|remove", "original": "text", "improved": "text", "reason": "why"}
  ],
  "key_improvements": ["bullet points of what was fixed"]
}

RULES:
- Preserve the candidate's voice and valid points
- Add missing keywords/concepts from the question metadata
- Add concrete examples where missing
- Improve structure with transitions (first, second, finally, however)
- Fix factual inaccuracies
- Keep length close to ideal_length
- changes array should have 3-8 items max"""


def _build_correct_prompt(role: str, question: str, answer: str, meta: dict, feedback: str) -> str:
    keywords = meta.get("keywords", [])
    concepts = meta.get("concepts", [])
    mistakes = meta.get("common_mistakes", [])
    ideal = meta.get("ideal_length", 80)

    return (
        f"""Role: {role}"
Question: {question}"
Target Length: {ideal} words"
Core concepts: {concepts}"
Important Keywords: {keywords}"
Common mistakes: {mistakes}"
Candidate answer: {answer}"
Current feedback: {feedback}"""
    )


def _rule_based_correct(role: str, question: str, answer: str, meta: dict, feedback: str) -> dict:
    improved = answer.strip()
    changes = []

    if improved and not improved[-1] in '.!?':
        improved += '.'
        changes.append({"type": "add", "original": "", "improved": ".", "reason": "Add proper sentence ending"})

    keywords = meta.get("keywords", [])
    for kw in keywords[:3]:
        if kw.lower() not in improved.lower():
            improved += f" Key concept: {kw}."
            changes.append({"type": "add", "original": "", "improved": f" Key concept: {kw}.", "reason": f"Include missing keyword: {kw}"})

    transitions = ["First", "Second", "Finally", "However", "In addition"]
    has_transition = any(t.lower() in improved.lower() for t in transitions)
    if not has_transition and len(improved.split('.')) > 1:
        improved = "First, " + improved[0].lower() + improved[1:]
        changes.append({"type": "replace", "original": improved[:6], "improved": "First, ", "reason": "Add structural transition"})

    if "example" in feedback.lower() and "example" not in improved.lower():
        improved += " For example, consider a practical scenario demonstrating this concept."
        changes.append({"type": "add", "original": "", "improved": " For example, consider a practical scenario demonstrating this concept.", "reason": "Add concrete example as suggested by feedback"})

    if " i " in f" {improved.lower()} ":
        improved = improved.replace(" i ", " I ")
        changes.append({"type": "replace", "original": " i ", "improved": " I ", "reason": "Capitalize first-person pronoun"})

    return {
        "improved_answer": improved,
        "changes": changes[:6],
        "key_improvements": [c["reason"] for c in changes[:4]],
        "_meta": {"fallback": "rule_based"}
    }


def ai_correct(role: str, question: str, answer: str, meta: dict, feedback: str) -> Optional[dict]:
    start_time = time.time()

    if not AI_ENABLED:
        return _rule_based_correct(role, question, answer, meta, feedback)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _rule_based_correct(role, question, answer, meta, feedback)

    if not _check_circuit():
        logger.warning("Circuit breaker open, falling back to rule-based correction")
        return _rule_based_correct(role, question, answer, meta, feedback)

    try:
        prompt = _build_correct_prompt(role, question, answer, meta, feedback)
        client = _get_claude_client()

        resp = client.messages.create(
            model=AI_MODEL,
            max_tokens=1024,
            temperature=0.2,
            system=CORRECT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        latency_ms = int((time.time() - start_time) * 1000)

        content = _extract_text_from_response(resp)
        result = json.loads(content)

        if not all(k in result for k in ("improved_answer", "changes", "key_improvements")):
            return None

        _record_success()

        result["_meta"] = {
            "tokens_in": resp.usage.input_tokens,
            "tokens_out": resp.usage.output_tokens,
            "latency_ms": latency_ms,
            "model": AI_MODEL,
            "prompt_version": os.getenv("PROMPT_VERSION", "v1.0"),
        }

        logger.info(f"AI corrected: role={role} tokens={resp.usage.input_tokens}/{resp.usage.output_tokens} latency={latency_ms}ms")
        return result

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"AI correction failed: {e} (latency={latency_ms}ms)")
        _record_failure()
        error_str = str(e).lower()
        if "quota" in error_str or "429" in error_str or "rate limit" in error_str:
            logger.warning("Quota exceeded, falling back to rule-based correction")
            return _rule_based_correct(role, question, answer, meta, feedback)
        return _rule_based_correct(role, question, answer, meta, feedback)