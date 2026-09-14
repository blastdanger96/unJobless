"""Rule-based grader.

This is the fallback whenever the AI is off, out of budget, or just failing.
It loads questions.json on its own so nothing here has to import app.py
(that used to be a circular import and it broke everything).
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

MAX_POINTS = 3

# phrases that tell us the answer is actually organised, not one big blob
STRUCTURE_MARKERS = [
    "first", "second", "third", "finally", "however",
    "for example", "such as", "because", "therefore",
    "on the other hand", "in contrast", "whereas",
    "for instance", "this means", "which means",
]

EXAMPLE_MARKERS = [
    "for example", "for instance", "e.g.", "such as", "in my experience",
    "when i", "at my previous", "one time",
]

_QUESTION_FILE = os.path.join(os.path.dirname(__file__), "questions.json")


def _load_questions():
    try:
        with open(_QUESTION_FILE, "r", encoding="utf-8") as f:
            roles = json.load(f)["roles"]
        return {role: data["questions"] for role, data in roles.items()}
    except (OSError, json.JSONDecodeError, KeyError) as e:
        # not fatal for the grader itself, we just lose the per-question metadata
        logger.error("could not load %s: %s", _QUESTION_FILE, e)
        return {}


QUESTIONS = _load_questions()


def get_meta(role, question):
    """Metadata for one question. Returns {} when we can't find it."""
    return next((q for q in QUESTIONS.get(role, []) if q["q"] == question), {})


def get_difficulty(ideal_length):
    if ideal_length <= 85:
        return "easy"
    if ideal_length <= 100:
        return "medium"
    return "hard"


def _score(answer, meta):
    """Score the answer against the metadata. Returns a dict so the feedback
    builders below don't have to recompute any of this."""
    lower = answer.lower()
    word_count = len(lower.split())
    ideal_length = meta.get("ideal_length", 80)

    keywords = meta.get("keywords", [])
    concepts = meta.get("concepts", [])

    keyword_hits = [k for k in keywords if k.lower() in lower]
    concept_hits = [c for c in concepts if c.lower() in lower]

    # length, 0-2
    if word_count >= ideal_length:
        length_score = 2
    elif word_count >= ideal_length * 0.6:
        length_score = 1
    else:
        length_score = 0

    # keywords, 0-2. half of them = full marks, a fifth = half marks
    if keywords and len(keyword_hits) >= len(keywords) * 0.5:
        keyword_score = 2
    elif keywords and len(keyword_hits) >= len(keywords) * 0.2:
        keyword_score = 1
    else:
        keyword_score = 0

    # concepts, 0-2. slightly easier bar than keywords since there are more of them
    if concepts and len(concept_hits) >= len(concepts) * 0.4:
        concept_score = 2
    elif concepts and len(concept_hits) >= len(concepts) * 0.2:
        concept_score = 1
    else:
        concept_score = 0

    structure_hits = sum(1 for m in STRUCTURE_MARKERS if m in lower)
    structure_score = min(2, structure_hits)

    has_example = any(m in lower for m in EXAMPLE_MARKERS)
    example_score = 2 if has_example else 0

    # content carries most of the weight, delivery is the rest
    raw = (
        length_score * 0.2
        + keyword_score * 0.3
        + concept_score * 0.3
        + structure_score * 0.1
        + example_score * 0.1
    )

    if raw >= 1.5:
        points = 3
    elif raw >= 1.0:
        points = 2
    elif raw >= 0.5:
        points = 1
    else:
        points = 0

    return {
        "points": points,
        "raw": round(raw, 3),
        "word_count": word_count,
        "ideal_length": ideal_length,
        "keywords": keywords,
        "concepts": concepts,
        "keyword_hits": keyword_hits,
        "concept_hits": concept_hits,
        "structure_hits": structure_hits,
        "has_example": has_example,
    }


def _build_feedback(s):
    points = s["points"]
    lines = []

    if points == 3:
        lines.append(
            "Strong answer. You covered the core idea accurately and explained "
            "your reasoning clearly, which is exactly what an interviewer is listening for."
        )
        if s["keyword_hits"]:
            lines.append(
                "You used the right technical vocabulary: "
                f"{', '.join(s['keyword_hits'][:4])}."
            )
        if not s["has_example"]:
            lines.append(
                "One thing to add next time: a concrete example. Even a full-mark "
                "explanation lands harder when it is grounded in something real."
            )

    elif points == 2:
        lines.append(
            "Good answer overall. The fundamentals are there, but a few gaps are "
            "keeping it from being a top response."
        )
        missed = [k for k in s["keywords"] if k not in s["keyword_hits"]][:3]
        if missed:
            lines.append(
                f"Work these terms into your explanation: {', '.join(missed)}."
            )
        if not s["has_example"]:
            lines.append(
                "Add a concrete example. It shows you can apply the concept, not just define it."
            )
        if s["word_count"] < s["ideal_length"] * 0.7:
            lines.append(
                f"You are also running short at {s['word_count']} words - "
                f"aim for around {s['ideal_length']}."
            )

    elif points == 1:
        lines.append(
            "Partial credit. You are pointed in the right direction, but the "
            "explanation is too thin to be convincing in an interview."
        )
        if s["word_count"] < s["ideal_length"] * 0.5:
            lines.append(
                f"At {s['word_count']} words this is roughly half of what the "
                f"question needs (~{s['ideal_length']})."
            )
        missed_concepts = [c for c in s["concepts"] if c not in s["concept_hits"]][:3]
        if missed_concepts:
            lines.append(
                f"These ideas are missing entirely: {', '.join(missed_concepts)}."
            )
        if not s["has_example"]:
            lines.append("Back it up with an example so the answer has something to stand on.")

    else:
        lines.append(
            "This one missed the mark. The key concepts the question is testing "
            "are not present in your answer."
        )
        lines.append(
            "Try this structure: define the concept, explain how it works, then "
            "give a real-world example of where you would use it."
        )
        if s["keywords"]:
            lines.append(f"Terms to build around: {', '.join(s['keywords'][:4])}.")

    return " ".join(lines)


def _build_breakdown(s):
    lines = []

    if s["keywords"] and len(s["keyword_hits"]) >= len(s["keywords"]) * 0.5:
        lines.append(f"+ Solid technical vocabulary ({', '.join(s['keyword_hits'][:3])})")
    elif s["keyword_hits"]:
        lines.append(f"~ Some technical terms present ({', '.join(s['keyword_hits'][:2])}), needs more")
    else:
        lines.append("- Missing the key technical terminology")

    if s["concepts"] and len(s["concept_hits"]) >= len(s["concepts"]) * 0.4:
        lines.append("+ Core concepts are covered")
    elif s["concept_hits"]:
        lines.append("~ Core concepts touched on but not developed")
    else:
        lines.append(
            f"- Core concepts not explained ({s['word_count']} words vs ~{s['ideal_length']} ideal)"
        )

    if s["has_example"]:
        lines.append("+ Included a concrete example")
    elif s["word_count"] < s["ideal_length"] * 0.6:
        lines.append("- Too short and no example - both hurt the answer")
    else:
        lines.append("- No concrete example to support the explanation")

    if s["structure_hits"] >= 2:
        lines.append("+ Clear structure (first / second / finally) makes it easy to follow")
    else:
        lines.append("- Little structure - use signposting so the answer is easy to follow")

    return "\n".join(lines)


def basic_grade(answer):
    """Used when there is no metadata for the question (custom role, bad match, etc).
    Only length and example presence to go on here."""
    has_example = any(m in answer.lower() for m in EXAMPLE_MARKERS)
    words = len(answer.split())

    if words < 30:
        points = 0
        feedback = (
            "Too short to assess. Expand on the key ideas behind the question "
            "and explain your reasoning."
        )
        breakdown = "- Answer is far too short, add detail and an example"
    elif words < 80:
        points = 1
        feedback = (
            "Reasonable start, but it needs more depth. A couple more points, "
            "each properly explained, would lift this a lot."
        )
        breakdown = "~ Decent attempt, light on detail"
    elif words < 150:
        points = 2
        feedback = (
            "Good length and the reasoning comes through. Tighten it up with "
            "more specifics and it is interview-ready."
        )
        breakdown = "+ Good depth, could use more specificity"
    else:
        points = 3
        feedback = (
            "Thorough and well developed. You clearly know the material - just "
            "keep an eye on staying concise under time pressure."
        )
        breakdown = "+ Thorough answer with strong depth"

    if not has_example:
        breakdown += "\n- No example detected, always back the answer up with one"

    return feedback, points, breakdown


def grade(role, answer, question):
    """Main entry point. Returns (feedback, points, breakdown)."""
    meta = get_meta(role, question)
    if not meta:
        return basic_grade(answer)

    s = _score(answer, meta)
    return _build_feedback(s), s["points"], _build_breakdown(s)
