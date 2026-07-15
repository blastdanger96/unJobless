import os
import json
import time
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
AI_MODEL = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "8"))

_client = None

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
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
            timeout=AI_TIMEOUT,
        )
    return _client


def _rule_based_grade(role: str, question: str, answer: str, meta: dict) -> dict:
    """Fallback grading using simple rules when AI is unavailable."""
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
        return None
    if not os.getenv("GROQ_API_KEY"):
        return None

    from cost_tracker import get_cost_tracker
    tracker = get_cost_tracker()
    status = tracker.get_status()
    if status["over_daily"] or status["over_monthly"]:
        logger.warning("AI budget exceeded, falling back to rule-based")
        return None

    if not _check_circuit():
        logger.warning("Circuit breaker open, falling back")
        return _rule_based_grade(role, question, answer, meta)

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

        latency_ms = int((time.time() - start_time) * 1000)
        tokens_in = resp.usage.prompt_tokens
        tokens_out = resp.usage.completion_tokens

        within_budget = tracker.record(AI_MODEL, tokens_in, tokens_out)
        if not within_budget:
            logger.warning("Budget exceeded after this request")

        content = resp.choices[0].message.content
        result = json.loads(content)

        if not all(k in result for k in ("feedback", "points", "breakdown")):
            return None
        if not isinstance(result["points"], int) or not 0 <= result["points"] <= 3:
            return None

        _record_success()

        result["_meta"] = {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "model": AI_MODEL,
            "prompt_version": os.getenv("PROMPT_VERSION", "v1.0"),
            "fallback_reason": None,
        }

        logger.info(f"AI graded: role={role} points={result['points']} "
                    f"tokens={tokens_in}/{tokens_out} latency={latency_ms}ms")

        return result

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"AI grading failed: {e} (latency={latency_ms}ms)")
        _record_failure()
        error_str = str(e).lower()
        if "insufficient_quota" in error_str or "quota" in error_str or "billing" in error_str or "429" in error_str:
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


def _build_correct_prompt(role: str, question: str, answer: str, meta: dict, feedback: str) -> list[dict]:
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
Candidate answer: {answer}"
Current feedback: {feedback}"""
    )

    return [
        {"role": "system", "content": CORRECT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _rule_based_correct(role: str, question: str, answer: str, meta: dict, feedback: str) -> dict:
    """Fallback correction using simple rules when AI is unavailable."""
    improved = answer.strip()
    changes = []
    
    # Ensure ends with period
    if improved and not improved[-1] in '.!?':
        improved += '.'
        changes.append({"type": "add", "original": "", "improved": ".", "reason": "Add proper sentence ending"})
    
    # Add keywords from meta if missing
    keywords = meta.get("keywords", [])
    for kw in keywords[:3]:
        if kw.lower() not in improved.lower():
            improved += f" Key concept: {kw}."
            changes.append({"type": "add", "original": "", "improved": f" Key concept: {kw}.", "reason": f"Include missing keyword: {kw}"})
    
    # Add structure transition if missing
    transitions = ["First", "Second", "Finally", "However", "In addition"]
    has_transition = any(t.lower() in improved.lower() for t in transitions)
    if not has_transition and len(improved.split('.')) > 1:
        improved = "First, " + improved[0].lower() + improved[1:]
        changes.append({"type": "replace", "original": improved[:6], "improved": "First, ", "reason": "Add structural transition"})
    
    # Add concrete example placeholder if feedback suggests it
    if "example" in feedback.lower() and "example" not in improved.lower():
        improved += " For example, consider a practical scenario demonstrating this concept."
        changes.append({"type": "add", "original": "", "improved": " For example, consider a practical scenario demonstrating this concept.", "reason": "Add concrete example as suggested by feedback"})
    
    # Fix common grammar issues
    if " i " in f" {improved.lower()} ":
        improved = improved.replace(" i ", " I ")
        changes.append({"type": "replace", "original": " i ", "improved": " I ", "reason": "Capitalize first-person pronoun"})
    
    return {
        "improved_answer": improved,
        "changes": changes[:6],  # limit to 6 changes
        "key_improvements": [c["reason"] for c in changes[:4]],
        "_meta": {"fallback": "rule_based"}
    }


def ai_correct(role: str, question: str, answer: str, meta: dict, feedback: str) -> Optional[dict]:
    start_time = time.time()

    if not AI_ENABLED:
        return None
    if not os.getenv("GROQ_API_KEY"):
        return None

    from cost_tracker import get_cost_tracker
    tracker = get_cost_tracker()
    status = tracker.get_status()
    if status["over_daily"] or status["over_monthly"]:
        logger.warning("AI budget exceeded, falling back to rule-based correction")
        return _rule_based_correct(role, question, answer, meta, feedback)

    if not _check_circuit():
        logger.warning("Circuit breaker open, falling back to rule-based correction")
        return _rule_based_correct(role, question, answer, meta, feedback)

    try:
        messages = _build_correct_prompt(role, question, answer, meta, feedback)
        client = _get_client()

        resp = client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=600,
            response_format={"type": "json_object"},
        )

        latency_ms = int((time.time() - start_time) * 1000)
        tokens_in = resp.usage.prompt_tokens
        tokens_out = resp.usage.completion_tokens

        within_budget = tracker.record(AI_MODEL, tokens_in, tokens_out)
        if not within_budget:
            logger.warning("Budget exceeded after correction request")

        content = resp.choices[0].message.content
        result = json.loads(content)

        if not all(k in result for k in ("improved_answer", "changes", "key_improvements")):
            return None

        _record_success()

        result["_meta"] = {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "model": AI_MODEL,
            "prompt_version": os.getenv("PROMPT_VERSION", "v1.0"),
        }

        logger.info(f"AI corrected: role={role} tokens={tokens_in}/{tokens_out} latency={latency_ms}ms")
        return result

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"AI correction failed: {e} (latency={latency_ms}ms)")
        _record_failure()
        error_str = str(e).lower()
        if "insufficient_quota" in error_str or "quota" in error_str or "billing" in error_str or "429" in error_str:
            logger.warning("Quota exceeded, falling back to rule-based correction")
            return _rule_based_correct(role, question, answer, meta, feedback)
        return _rule_based_correct(role, question, answer, meta, feedback)