"""Claude-backed grading and answer correction.

Everything in here degrades to the rule-based grader in grader.py rather than
blowing up, so app.py only ever has to deal with one shape of response.
"""

import os
import json
import time
import logging

from dotenv import load_dotenv

from grader import grade as rule_grade
from cost_tracker import get_cost_tracker

load_dotenv()

logger = logging.getLogger(__name__)

AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
AI_MODEL = os.getenv("AI_MODEL", "claude-3-5-sonnet-20241022")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1.0")

MAX_TOKENS = 1024
TEMPERATURE = 0.2


class CircuitBreaker:
    """Stops us hammering (and paying for) an API that is clearly down.

    After `threshold` failures it stays open for `cooldown` seconds, then
    resets the counter and gives it another go.
    """

    def __init__(self, threshold=5, cooldown=60):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.open_until = 0.0

    @property
    def is_open(self):
        return self.open_until > time.time()

    def allow(self):
        if self.is_open:
            return False
        # cooldown has elapsed, so wipe the slate - this is what used to be
        # missing and it left the breaker stuck open forever
        if self.failures >= self.threshold:
            self.failures = 0
        return True

    def record_success(self):
        self.failures = 0
        self.open_until = 0.0

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.time() + self.cooldown
            logger.warning(
                "circuit opened after %d failures, cooling down %ds",
                self.failures, self.cooldown,
            )

    def status(self):
        return "open" if self.is_open else "closed"


breaker = CircuitBreaker()


GRADE_SYSTEM_PROMPT = """You are an expert technical interviewer grading candidate answers.
Score 0-3 based on: accuracy, depth, structure, examples, communication.
Return ONLY valid JSON: {"feedback": "string", "points": 0-3, "breakdown": "string"}

SCORING GUIDE:
- 3: Accurate, detailed, well-structured, includes concrete example
- 2: Mostly correct, minor gaps, some structure, maybe an example
- 1: Partial understanding, missing key concepts, weak structure
- 0: Incorrect, vague, or missing core concepts entirely

FEEDBACK STYLE: Direct, constructive, interviewer tone. Mention specific strengths/gaps.
BREAKDOWN: Bullet points of what was covered vs missed."""


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


def _build_prompt(role, question, answer, meta, feedback=None):
    """One builder for both prompts - the correction one just gets an extra line."""
    parts = [
        f"Role: {role}",
        f"Question: {question}",
        f"Target length: {meta.get('ideal_length', 80)} words",
        f"Core concepts: {meta.get('concepts', [])}",
        f"Important keywords: {meta.get('keywords', [])}",
        f"Common mistakes: {meta.get('common_mistakes', [])}",
        f"Candidate answer: {answer}",
    ]
    if feedback:
        parts.append(f"Current feedback: {feedback}")
    return "\n".join(parts)


def _client():
    import openai
    return openai.OpenAI(
        api_key=os.getenv("NVIDIA_API_KEY"),
        base_url="https://api.nvidia.com/v1",
        timeout=AI_TIMEOUT,
    )





def _can_call():
    if not AI_ENABLED:
        return False
    if not os.getenv("NVIDIA_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        logger.debug("no AI API keys set, staying on the rule grader")
        return False
    if not breaker.allow():
        logger.warning("circuit is open, using fallback")
        return False
    if get_cost_tracker().get_status()["over_daily"]:
        logger.warning("daily spend limit hit, using fallback")
        return False
    return True


def _get_client():
    """Return (client, api_type) tuple based on available API key."""
    import anthropic
    import openai
    nvidia_key = os.getenv("NVIDIA_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if nvidia_key:
        client = openai.OpenAI(
            api_key=nvidia_key,
            base_url="https://api.nvidia.com/v1",
            timeout=AI_TIMEOUT,
        )
        return client, "nvidia"
    elif anthropic_key:
        client = anthropic.Anthropic(
            api_key=anthropic_key,
            timeout=AI_TIMEOUT,
        )
        return client, "anthropic"
    else:
        return None, None


def _invoke(system_prompt, user_prompt):
    """Single API call. Returns (parsed_json, meta_dict). Raises on failure."""
    client, api_type = _get_client()
    if not client:
        raise RuntimeError("No AI client available")

    started = time.time()

    if api_type == "nvidia":
        resp = client.chat.completions.create(
            model=AI_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # NVIDIA response format
        text = resp.choices[0].message.content
        tokens_in = resp.usage.prompt_tokens
        tokens_out = resp.usage.completion_tokens
    else:
        # anthropic
        resp = client.messages.create(
            model=AI_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = ""
        for block in resp.content:
            if getattr(block, "text", None):
                text = block.text
                break
        tokens_in = resp.usage.input_tokens
        tokens_out = resp.usage.output_tokens

    latency_ms = int((time.time() - started) * 1000)

    result = _extract_json_from_text(text)

    get_cost_tracker().record(AI_MODEL, tokens_in, tokens_out)

    meta = {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms,
        "model": AI_MODEL,
        "prompt_version": PROMPT_VERSION,
        "fallback_reason": None,
    }
    return result, meta


def _extract_json_from_text(text):
    """Pull the text out and strip any ``` fencing."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop the fence lines, keep the middle
        text = "\n".join(lines[1:-1]) if len(lines) >= 3 else text.strip("`")
    return json.loads(text.strip())


def _fallback_grade(role, question, answer, reason="rule_based"):
    feedback, points, breakdown = rule_grade(role, answer, question)
    return {
        "feedback": feedback,
        "points": points,
        "breakdown": breakdown,
        "_meta": {"fallback_reason": reason},
    }


def ai_grade(role, question, answer, meta):
    if not _can_call():
        return _fallback_grade(role, question, answer)

    try:
        result, call_meta = _invoke(
            GRADE_SYSTEM_PROMPT,
            _build_prompt(role, question, answer, meta),
        )
    except Exception as e:
        breaker.record_failure()
        logger.error("AI grading failed: %s", e)
        return _fallback_grade(role, question, answer, reason="api_error")

    # the model usually behaves but we're not trusting it blindly
    if not all(k in result for k in ("feedback", "points", "breakdown")):
        logger.warning("AI grade response missing fields, falling back")
        return _fallback_grade(role, question, answer, reason="bad_schema")
    if not isinstance(result["points"], int) or not 0 <= result["points"] <= 3:
        logger.warning("AI returned out-of-range points: %r", result.get("points"))
        return _fallback_grade(role, question, answer, reason="bad_points")

    breaker.record_success()
    result["_meta"] = call_meta
    logger.info(
        "AI graded role=%s points=%s tokens=%s/%s latency=%sms",
        role, result["points"], call_meta["tokens_in"],
        call_meta["tokens_out"], call_meta["latency_ms"],
    )
    return result


def _fallback_correct(role, question, answer, meta, feedback, reason="rule_based"):
    """Nowhere near as good as the model, but it always returns something
    sensible so the modal never comes up empty."""
    improved = answer.strip()
    changes = []

    if improved and improved[-1] not in ".!?":
        improved += "."
        changes.append({
            "type": "add",
            "original": "",
            "improved": ".",
            "reason": "Close the sentence properly",
        })

    for kw in meta.get("keywords", [])[:3]:
        if kw.lower() not in improved.lower():
            addition = f" Key concept: {kw}."
            improved += addition
            changes.append({
                "type": "add",
                "original": "",
                "improved": addition,
                "reason": f"Include the missing keyword: {kw}",
            })

    transitions = ["first", "second", "finally", "however", "in addition"]
    if not any(t in improved.lower() for t in transitions) and len(improved.split(".")) > 1:
        original_opening = improved[:20]
        improved = "First, " + improved[0].lower() + improved[1:]
        changes.append({
            "type": "replace",
            "original": original_opening,
            "improved": "First, " + original_opening[:14],
            "reason": "Add a structural transition to open the answer",
        })

    if "example" in feedback.lower() and "example" not in improved.lower():
        addition = " For example, consider a practical scenario where this applies."
        improved += addition
        changes.append({
            "type": "add",
            "original": "",
            "improved": addition,
            "reason": "Add a concrete example, as the feedback suggested",
        })

    if " i " in f" {improved.lower()} ":
        improved = improved.replace(" i ", " I ")
        changes.append({
            "type": "replace",
            "original": " i ",
            "improved": " I ",
            "reason": "Capitalise the first-person pronoun",
        })

    changes = changes[:6]
    return {
        "improved_answer": improved,
        "changes": changes,
        "key_improvements": [c["reason"] for c in changes[:4]],
        "_meta": {"fallback_reason": reason},
    }


def ai_correct(role, question, answer, meta, feedback):
    if not _can_call():
        return _fallback_correct(role, question, answer, meta, feedback)

    try:
        result, call_meta = _invoke(
            CORRECT_SYSTEM_PROMPT,
            _build_prompt(role, question, answer, meta, feedback=feedback),
        )
    except Exception as e:
        breaker.record_failure()
        logger.error("AI correction failed: %s", e)
        return _fallback_correct(role, question, answer, meta, feedback, reason="api_error")

    if not all(k in result for k in ("improved_answer", "changes", "key_improvements")):
        logger.warning("AI correct response missing fields, falling back")
        return _fallback_correct(role, question, answer, meta, feedback, reason="bad_schema")

    breaker.record_success()
    result["_meta"] = call_meta
    logger.info(
        "AI corrected role=%s tokens=%s/%s latency=%sms",
        role, call_meta["tokens_in"], call_meta["tokens_out"], call_meta["latency_ms"],
    )
    return result
