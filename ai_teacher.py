import os
import json
import time
import logging
from dotenv import load_dotenv

load_dotenv()

AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
AI_MODEL = os.getenv("AI_MODEL", "claude-3-5-sonnet-20241022")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))

# simple circuit breaker so that if API fails 5 times, wait 60s
fail_count = 0
circuit_open_until = 0
THRESHOLD = 5
COOLDOWN = 60

logger = logging.getLogger(__name__)


# just keeping the prompt here
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


def _mk_prompt(role, question, answer, meta):
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
    return anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        timeout=AI_TIMEOUT
    )


def _clean_json(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```"):
            text = "\n".join(lines[1:-1])
    return text.strip()


def _get_text(resp):
    for block in resp.content:
        if hasattr(block, "text") and block.text:
            return _clean_json(block.text)
    return ""


def _fallback_grade(role, question, answer, meta):
    from app import grade as rule_grade
    feedback, points, breakdown = rule_grade(role, answer, question)
    return {
        "feedback": feedback,
        "points": points,
        "breakdown": breakdown,
        "_meta": {"fallback_reason": "rule_based"}
    }


def ai_grade(role, question, answer, meta):
    global fail_count, circuit_open_until
    start_time = time.time()

    if not AI_ENABLED:
        return _fallback_grade(role, question, answer, meta)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _fallback_grade(role, question, answer, meta)

    # if API keeps failing, just use fallback - no need to burn money
    if circuit_open_until > time.time():
        logger.warning("Circuit breaker open, falling back")
        return _fallback_grade(role, question, answer, meta)
    if fail_count >= THRESHOLD:
        circuit_open_until = time.time() + COOLDOWN
        logger.warning("Too many failures, circuit open for %ds", COOLDOWN)
        return _fallback_grade(role, question, answer, meta)

    try:
        prompt = _mk_prompt(role, question, answer, meta)
        client = _get_claude_client()

        resp = client.messages.create(
            model=AI_MODEL,
            max_tokens=1024,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        latency_ms = int((time.time() - start_time) * 1000)

        content = _get_text(resp)
        result = json.loads(content)

        if not all(k in result for k in ("feedback", "points", "breakdown")):
            return None
        if not isinstance(result["points"], int) or not 0 <= result["points"] <= 3:
            return None

        fail_count = 0
        circuit_open_until = 0

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
        fail_count += 1
        error_str = str(e).lower()
        if "quota" in error_str or "429" in error_str or "rate limit" in error_str:
            logger.warning("Quota exceeded, falling back to rule-based grading")
            return _fallback_grade(role, question, answer, meta)
        return _fallback_grade(role, question, answer, meta)


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


def _mk_correct_prompt(role, question, answer, meta, feedback):
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


def _fallback_correct(role, question, answer, meta, feedback):
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


def ai_correct(role, question, answer, meta, feedback):
    global fail_count, circuit_open_until
    start_time = time.time()

    if not AI_ENABLED:
        return _fallback_correct(role, question, answer, meta, feedback)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _fallback_correct(role, question, answer, meta, feedback)

    # circuit open for corrections too
    if circuit_open_until > time.time():
        logger.warning("Circuit breaker open for corrections, falling back")
        return _fallback_correct(role, question, answer, meta, feedback)
    if fail_count >= THRESHOLD:
        circuit_open_until = time.time() + COOLDOWN
        return _fallback_correct(role, question, answer, meta, feedback)

    try:
        prompt = _mk_correct_prompt(role, question, answer, meta, feedback)
        client = _get_claude_client()

        resp = client.messages.create(
            model=AI_MODEL,
            max_tokens=1024,
            temperature=0.2,
            system=CORRECT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        latency_ms = int((time.time() - start_time) * 1000)

        content = _get_text(resp)
        result = json.loads(content)

        if not all(k in result for k in ("improved_answer", "changes", "key_improvements")):
            return None

        fail_count = 0
        circuit_open_until = 0

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
        fail_count += 1
        error_str = str(e).lower()
        if "quota" in error_str or "429" in error_str or "rate limit" in error_str:
            logger.warning("Quota exceeded, falling back to rule-based correction")
            return _fallback_correct(role, question, answer, meta, feedback)
        return _fallback_correct(role, question, answer, meta, feedback)