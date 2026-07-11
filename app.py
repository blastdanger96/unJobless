from flask import Flask, request, jsonify, send_from_directory
#request reads incoming data (query params, JSON Body)
# jsnoify converts python dicts into a proper JSON HTTP response
#send_from directiory lets us serve the frontend files (html/css/js) straight off disk
import random
#used to pick a random question from the pool each time /question is hit
import json
#used to avoid repetitions in the python code for question dict
import os


app = Flask(__name__, static_folder='.')
# static_folder = '.' means the current directory is treated as the static root

QUESTION_FILE = os.path.join(os.path.dirname(__file__), 'questions.json')
#it has the same format for ur grade()/get_question() code except in the json file :)

with open(QUESTION_FILE, 'r', encoding='utf-8') as f:
    ROLE_DATA = json.load(f)['roles']

QUESTIONS = {role: data['questions'] for role, data in ROLE_DATA.items()}
#word/phrases tht suggest the answer acc organized rather than js a wall of txt, used to score "structure" seprately from content
STRUCTURE_MARKERS = [
    "first", "second", "third", "finally", "however",
    "for example", "such as", "because", "therefore",
    "on the other hand", "in contrast", "whereas",
    "for instance", "this means", "which means"
]

EXAMPLE_MARKERS = [
    "for example", "for instance", "e.g.", "such as","in my experience",
    "when i", "at my previous", "one time"
]

# tracks the last question shown per role, so we don't immediately repeat it
_recent: dict = {}
# tracks per-user score history: {user_id: {"points": [...], "by_role": {role: [...]}}}
_user_scores: dict = {}



@app.route('/')
def index():
    # root route js hands back index.html, the role-selector page
    return send_from_directory('.', 'index.html')



@app.route('/<path:filename>')
def static_files(filename):
    # catch-all route so any file requsted by name (script.js, question.css, etc) gets 
    # gets served straight from the project folder instead of needing its own route
    return send_from_directory('.', filename)


@app.route('/question')
def get_question():
    #.strip() guards against a role comin in with stray whitespace, e.g. "?role=Consultant%20"
    role = request.args.get('role', '').strip()

    if role not in QUESTIONS:
        #bail early with a 400 if sm1 passes a role we have no questions for
        return jsonify({'error': f'Unknown role: {role}'}), 400

    pool = QUESTIONS[role]
    last = _recent.get(role)
    # filter out whatever question was shown last time so it doesn't repeat back to back
    # "or pool" is a fallback: if filtering leaves nthin (pool only had 1 question)
    # fall back to a full pool so random.choice nvr gets an empty list
    available = [q for q in pool if q['q'] != last] or pool
    chosen = random.choice(available)
    _recent[role] = chosen['q']
    # remember this one so next call exlcudes it

    return jsonify({'question': chosen['q'], 'role': role})


@app.route('/submit', methods=['POST'])
def submit():
    body = request.get_json(silent=True)
    #silent=true means a missin json body returns none instead of throwing
    if not body:
        return jsonify({'error': 'No data received'}), 400

    role = body.get('role', '').strip()
    answer = body.get('answer', '').strip()
    user_id = body.get('user_id', 'anonymous').strip() or 'anonymous'
    # the "or 'anonymous" catches the case where user_id was sent as an empty string
    question = _recent.get(role, '')
    # pulls whtrv questions we last handed out for this role, so grade () can look up the matching keywords/concepts for it

    if role not in QUESTIONS:
        return jsonify({'error': 'Invalid role'}), 400
    if len(answer) < 20:
        # matches the frontend's own minimum length check, kept here too since the frotnend checks can be bypassed by hittin the api directly
        return jsonify({'error': 'Answer too short'}), 400

    feedback, points, breakdown = grade(role, answer, question)

    user_record = _user_scores.setdefault(user_id, {'points': [], 'by_role': {}})
    # setdefault creates the entry on first submit and js returns it on later ones (it rotates the entries ig)
    user_record['points'].append(points)
    user_record['by_role'].setdefault(role, []).append(points)

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


def grade(role: str, answer: str, question: str) -> tuple:
    # find the metadata dict matching the exact question txt tht was asked so we know wich keywords to check the answer against
    meta = next(
        (q for q in QUESTIONS.get(role, []) if q['q'] == question),
        None
    )
    if not meta:
        # question wasnt found so fall back to a gradin scheme that only looks at length and examples
        return basic_grade(answer)

    answer_lower = answer.lower()
    # lowercased once up front so every keywrod/concept check below is case-insensitive
    words = answer_lower.split()
    word_count = len(words)
    ideal_length = meta.get('ideal_length', 80)
    # 80 as a fallback in case a question entry is missin this field

    # --- length score (0-2) ---
    length_score = 0
    if word_count >= ideal_length:
        length_score = 2
    elif word_count >= ideal_length * 0.6:
        # partial credit for getting reasonably close to the target length
        length_score = 1

    # --- keyword score (0-2) ---
    keywords = meta.get('keywords', [])
    keyword_hits = [k for k in keywords if k.lower() in answer_lower]
    keyword_score = 0
    if keywords:
        ratio = len(keyword_hits) / len(keywords)
        if ratio >= 0.5:
            keyword_score = 2
        elif ratio >= 0.2:
            keyword_score = 1

    # --- concept score (0-2) ---
    concepts = meta.get('concepts', [])
    concept_hits = [c for c in concepts if c.lower() in answer_lower]
    concept_score = 0
    if concepts:
        ratio = len(concept_hits) / len(concepts)
        if ratio >= 0.4:
            concept_score = 2
        elif ratio >= 0.2:
            concept_score = 1


    # --- structure score (0-2) ---
    structure_hits = sum(1 for m in STRUCTURE_MARKERS if m in answer_lower)
    structure_score = 2 if structure_hits >= 2 else (1 if structure_hits == 1 else 0)

    # --- example score (0-2) ---
    has_example = any(m in answer_lower for m in EXAMPLE_MARKERS)
    example_score = 2 if has_example else 0

    # each sub-score is 0-2, weighted and summed into one number out of 2
    # weights add up to 1.0, so raw itself lands somewhere in [0,2]
    raw = (
        length_score * 0.2 +
        keyword_score * 0.3 +
        concept_score * 0.3 +
        structure_score * 0.1 +
        example_score * 0.1
    )
    # raw gets bucketed down into a simple 0-3 point scale for display
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
    # builds the casual, slang-heavy headline feedback shown to the user. branches purely on the points bucket computed in grade()

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
        # [:3] caps the callout list so feedback doesn't turn into a wall of txt
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
        # points == 0
        lines.append("man ts is so wrong, go back and study fr gng or u finna be jobless ash")
        lines.append("start with the definition. explain how it works. give an example and dont fumble gng")
        if keywords:
            lines.append(f"use terms like this lil bru: {', '.join(keywords[:4])}.")

    return " ".join(lines)


def build_breakdown(keyword_hits, keywords,
                     concept_hits, concepts,
                     has_example, word_count, ideal_length,
                     structure_hits) -> str:
    # this is the second more granular feedback block (the +/- lines) shown under the main headline feedback
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

        # joined with real newlines (not spaces like build_feedback) since this renders as a stacked list in the UI rather than a paragraph

    return '\n'.join(lines)


def basic_grade(answer: str) -> tuple:
    """Fallback grading if no question metadata is found. Checks length and presence of an example."""
    has_example = any(m in answer.lower() for m in EXAMPLE_MARKERS)
    words = len(answer.split())

    # much better than the main grade() function: length is the only real
    # signal here since there's no keyword/concept list to check against

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
    # simple status endpoint, useful for confirming the server's up and seeing question counts without digging through the code
    return jsonify({
        'status': 'running',
        'ai_enabled': False,
        'grader': 'rule-based (no external ai calls)',
        'roles': list(QUESTIONS.keys()),
        'total_questions': sum(len(v) for v in QUESTIONS.values())
    })



@app.route('/roles')
def get_roles():
    #sends the frontend everything it needs to build role btns:
    return jsonify([
        {'name': role, 'emoji': data['emoji'], 'tagline': data['tagline']}
        for role, data in ROLE_DATA.items()
    ])
if __name__ == '__main__':
    print("\n" + "=" * 52)
    print(" unJ0bless Backend")
    print("=" * 52)
    print(" URL    -> http://localhost:8000")
    print(" Health -> http://localhost:8000/health")
    print(" Grader -> http://localhost:8000/submit (im sigma enough to not use AI gng)")
    print(f" Roles  -> {', '.join(QUESTIONS.keys())}")
    print(f" Total Questions -> {sum(len(v) for v in QUESTIONS.values())}")
    print("=" * 52 + "\n")
    app.run(debug=True, port=8000)
            # debug = True gives aut-reload on save and a live traceback in-browser on errors
            # fine for local dev, should be off b4 this ever goes near production