from flask import Flask, request, jsonify, send_from_directory
import random
import json
import os
#os is a lib for interaction withj file explorer

app = Flask(__name__, static_folder='.')

QUESTION_FILE = os.path.join(os.path.dirname(__file__), 'questions.json')

with open(QUESTION_FILE, 'r', encoding='utf-8') as f:
    ROLE_DATA = json.load(f)['roles']

QUESTIONS = {role: data['questions'] for role, data in ROLE_DATA.items()}

# Words/phrases that signal structured answers — scored separately from content
STRUCTURE_MARKERS = [
    "first", "second", "third", "finally", "however",
    "for example", "such as", "because", "therefore",
    "on the other hand", "in contrast", "whereas",
    "for instance", "this means", "which means"
]

EXAMPLE_MARKERS = [
    "for example", "for instance", "e.g.", "such as", "in my experience",
    "when i", "at my previous", "one time"
]

# Tracks last question shown per role to avoid immediate repeats
_recent: dict = {}

# Per-user score history: {user_id: {"points": [...], "by_role": {role: [...]}}}
_user_scores: dict = {}


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

def get_difficulty(ideal_length: int) -> str:
    if ideal_length <= 85:
        return 'easy'
    elif ideal_length <= 100:
        return 'medium'
    else:
        return 'hard'

@app.route('/question')
def get_question():
    role = request.args.get('role', '').strip()

    if role not in QUESTIONS:
        return jsonify({'error': f'Unknown role: {role}'}), 400

    pool = QUESTIONS[role]
    last = _recent.get(role)

    # Exclude last question to avoid immediate repeats
    # Fallback to full pool if only 1 question exists
    available = [q for q in pool if q['q'] != last] or pool
    chosen = random.choice(available)
    _recent[role] = chosen['q']

    difficulty = get_difficulty(chosen.get('ideal_length', 80))

    return jsonify({'question': chosen['q'], 'role': role, 'difficulty': difficulty})


@app.route('/submit', methods=['POST'])
def submit():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'error': 'No data received'}), 400

    role = body.get('role', '').strip()
    answer = body.get('answer', '').strip()
    user_id = body.get('user_id', 'anonymous').strip() or 'anonymous'
    question = _recent.get(role, '')
    # measuring the length of the answer to grasp it's worthyness
    if role not in QUESTIONS:
        return jsonify({'error': 'Invalid role'}), 400
    if len(answer) < 20:
        return jsonify({'error': 'Answer too short'}), 400

    feedback, points, breakdown = grade(role, answer, question)

    user_record = _user_scores.setdefault(user_id, {'points': [], 'by_role': {}})
    user_record['points'].append(points)
    user_record['by_role'].setdefault(role, []).append(points)
    # returns the graded answer to the frontend
    return jsonify({
        'feedback': feedback,
        'points': points,
        'breakdown': breakdown,
        'max_points': 3
    })


@app.route('/status')
def get_status():
    user_id = request.args.get('user', 'anonymous')
    score_data = _user_scores.get(user_id)
    if not score_data or not score_data['points']:
        return jsonify({'score': 0, 'answered': 0, 'average': 0, 'by_role': {}})

    total = sum(score_data['points'])
    answered = len(score_data['points'])
    avg = total / answered

    return jsonify({
        'score': total,
        'answered': answered,
        'average': round(avg, 2),
        'by_role': score_data['by_role']
    })
def score_ratio(hits, total, high, low):
    if not total:
        return 0
    
    ratio = len(hits) / total
    if ratio >= high:
        return 2
    elif ratio >= low:
        return 1
    else:
        return 0


def grade(role: str, answer: str, question: str) -> tuple:
    # Find question metadata to get keywords/concepts for this specific question
    meta = next(
        (q for q in QUESTIONS.get(role, []) if q['q'] == question),
        None
    )
    if not meta:
        return basic_grade(answer)

    answer_lower = answer.lower()
    words = answer_lower.split()
    word_count = len(words)
    ideal_length = meta.get('ideal_length', 80)

    # <--- Length score (0-2) --->
    length_score = 0
    if word_count >= ideal_length:
        length_score = 2
    elif word_count >= ideal_length * 0.6:
        length_score = 1

    # <--- Keyword score (0-2) --->
    keywords = meta.get('keywords', [])
    keyword_hits = [k for k in keywords if k.lower() in answer_lower]
    keyword_score = score_ratio(keyword_hits, len(keywords), 0.5, 0.2)

    # <--- Concept score (0-2) --->
    concepts = meta.get('concepts', [])
    concept_hits = [c for c in concepts if c.lower() in answer_lower]
    concept_score = score_ratio(concept_hits, len(concepts), 0.4, 0.2)
    # <--- Structure score (0-2) --->
    structure_hits = sum(1 for m in STRUCTURE_MARKERS if m in answer_lower)
    structure_score = 2 if structure_hits >= 2 else (1 if structure_hits == 1 else 0)

    # <--- Example score (0-2) --->
    has_example = any(m in answer_lower for m in EXAMPLE_MARKERS)
    example_score = 2 if has_example else 0

    # Weighted composite: keywords/concepts matters 50%, length matters 30%, structure/examples matters 20% 
    raw = (
        length_score * 0.2 +
        keyword_score * 0.3 +
        concept_score * 0.3 +
        structure_score * 0.1 +
        example_score * 0.1
    )

    # Bucket into 0-3 display points
    if raw >= 1.5:
        points = 3
    elif raw >= 1.0:
        points = 2
    elif raw >= 0.5:
        points = 1
    else:
        points = 0

    feedback = build_feedback(
        points, word_count, ideal_length,
        keyword_hits, keywords,
        concept_hits, concepts,
        has_example
    )

    breakdown = build_breakdown(
        keyword_hits, keywords,
        concept_hits, concepts,
        has_example, word_count, ideal_length,
        structure_hits
    )

    return feedback, points, breakdown


def build_feedback(points, word_count, ideal_length,
                    keyword_hits, keywords,
                    concept_hits, concepts,
                    has_example) -> str:
    lines = []

    if points == 3:
        lines.append("Well done smartass, you sound like you know your shi and you got the examples to back it up, gg gng")
        if keyword_hits:
            lines.append(f"Good job for using key terms like: {', '.join(keyword_hits)}.")
        if not has_example:
            lines.append("aint no way dawg, gj but it could be better icl, missing an example")

    elif points == 2:
        lines.append("yeah u could do sm better, put in sm effort for god's sake, its for ur own job")
        missed_keywords = [k for k in keywords if k not in keyword_hits][:3]
        if missed_keywords:
            lines.append(f"u missed sm key terms icl, so improve here or else ur cooked dawg: {', '.join(missed_keywords)}.")
        if not has_example:
            lines.append("dont keep yappin bru its givin needy, give sm examples to make this answer more goated")
        if word_count < ideal_length * 0.7:
            lines.append("yap a lil more dawg or else the interviewer will kick u out as fast as u finished tht answer")

    elif points == 1:
        lines.append("ye study harder this aint js it bru")
        if word_count < ideal_length * 0.5:
            lines.append("yap a lil more dawg or else the interviewer will kick u out as fast as u finished tht answer")
        missed_concepts = [c for c in concepts if c not in concept_hits][:3]
        if missed_concepts:
            lines.append(f"u had many key ideas missin, tht aint finna gibbu a job unless u yap abt em: {', '.join(missed_concepts)}.")
        if not has_example:
            lines.append("use examples bru or else they aint finna let u slide")

    else:
        lines.append("man ts is so wrong, go back and study fr gng or u finna be jobless ash")
        lines.append("start with the definition. explain how it works. give an example and dont fumble gng")
        if keywords:
            lines.append(f"use terms like this lil bru: {', '.join(keywords[:4])}.")

    return " ".join(lines)


def build_breakdown(keyword_hits, keywords,
                     concept_hits, concepts,
                     has_example, word_count, ideal_length,
                     structure_hits) -> str:
    lines = []

    if keywords and len(keyword_hits) >= len(keywords) * 0.5:
        lines.append(f"+ used key technical terms like ({', '.join(keyword_hits[:3])})")
    elif keyword_hits:
        lines.append(f"~ some technical terms present but need more emphasis ({', '.join(keyword_hits[:2])})")
    else:
        lines.append("- missing key technical terminology")

    if concepts and len(concept_hits) >= len(concepts) * 0.4:
        lines.append("+ gg gng ur pretty good on the core concepts")
    elif concept_hits:
        lines.append("~ core concepts touched on but u need to yap on more")
    else:
        lines.append(f"- ye bru u gotta yap more ({word_count} vs ~{ideal_length} ideal) or else u finna be cooked ash icl")

    if has_example:
        lines.append("+ included an example, good job dawg")
    elif word_count < ideal_length * 0.6:
        lines.append("- answer is too short AND missing an example, add one to make it convincing")
    else:
        lines.append("- touch grass and put in a real example")

    if structure_hits >= 2:
        lines.append("+ g00d structure markers (first, second, finally) to organize your answer, bru finally bothered lockin in on ts")
    else:
        lines.append("- yea bru u need to start lockin in on structure, ts aint tuff icl")

    return '\n'.join(lines)


def basic_grade(answer: str) -> tuple:
    #Fallback grading when no question metadata exists. Scores on length + example presence only. (can use """ for comments too but keep it simple)
    has_example = any(m in answer.lower() for m in EXAMPLE_MARKERS)
    words = len(answer.split())

    if words < 30:
        feedback = "u are absolutely jobless fam try to yap more and give examples or else u finna be homeless ash"
        points = 0
        breakdown = "- answer is too short, add more detail and examples"
    elif words < 80:
        feedback = "bro u gotta yap more to get a job, add more detail and examples or else u finna be homeless ash"
        points = 1
        breakdown = "~ decent attempt but light on detail, add more substance"
    elif words < 150:
        feedback = "ye no ts fr gng, on ur way to landin on a hot bag, keep cookin"
        points = 2
        breakdown = "+ decent shi ngl\n~ could use more specificity to really seal it"
    else:
        feedback = "ma goat man u finally locked in on ts and u sound like u know ur shi, gg gng"
        points = 3
        breakdown = "+ thorough answer with good depth, gg gng"

    if not has_example:
        breakdown += "\n- no example detected, always back up your answer with one"

    return feedback, points, breakdown


@app.route('/health')
def health():
    return jsonify({
        'status': 'running',
        'ai_enabled': False,
        'grader': 'rule-based (no external ai calls)',
        'roles': list(QUESTIONS.keys()),
        'total_questions': sum(len(v) for v in QUESTIONS.values())
    })


@app.route('/roles')
def get_roles():
    return jsonify([
        {'name': role, 'emoji': data['emoji'], 'tagline': data['tagline']}
        for role, data in ROLE_DATA.items()
    ])
if __name__ == '__main__':

    print("unst.J0e_bless running on localhost:8000", {len(QUESTIONS)}, "roles", {sum(len(v) for v in QUESTIONS.values())}, "questions fetched")
    app.run(debug=True, port=8000)

