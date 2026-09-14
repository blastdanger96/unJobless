from flask import Flask, request, jsonify, send_from_directory, Response, g
import random
import json
import os
import uuid
import hashlib
import logging
from functools import wraps
from io import BytesIO
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

import jwt

import ai_teacher
from ai_teacher import ai_grade, ai_correct
from grader import get_meta, get_difficulty, QUESTIONS as GRADER_QUESTIONS
from cost_tracker import get_cost_tracker

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET must be set via .env or SECRET_KEY env var")
TOKEN_EXPIRY_HOURS = 24 * 7  # a week

app = Flask(__name__, static_folder='.')

QUESTION_FILE = os.path.join(os.path.dirname(__file__), 'questions.json')

try:
    with open(QUESTION_FILE, 'r', encoding='utf-8') as f:
        ROLE_DATA = json.load(f)['roles']
except FileNotFoundError:
    raise SystemExit(f"ERROR: {QUESTION_FILE} not found.")
except json.JSONDecodeError as e:
    raise SystemExit(f"ERROR: invalid JSON in {QUESTION_FILE}: {e}")

QUESTIONS = {role: data['questions'] for role, data in ROLE_DATA.items()}

# In-memory stores. Swap for a real DB before this goes anywhere near production.
_users = {}
_sessions = {}      # session_id -> {user_id, role, started_at, questions: []}
_user_scores = {}   # user_id -> {points: [], by_role: {}, sessions: []}


def _now():
    return datetime.now(timezone.utc)


def _hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def _make_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": _now() + timedelta(hours=TOKEN_EXPIRY_HOURS),
        "iat": _now(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _verify_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])["user_id"]
    except jwt.InvalidTokenError:
        # covers expired tokens too, they subclass this
        return None


# --- auth ---------------------------------------------------------------
# One place that figures out who is calling. The client sends either a JWT or
# a session id in the Authorization header (and stats.js uses X-Session-Token),
# so we check both and let the caller decide what it actually needs.

def resolve_identity():
    """Returns (user_id, session). Either can be None."""
    auth = request.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
    else:
        token = ""

    session_header = (request.headers.get("X-Session-Token") or "").strip()

    for candidate in (session_header, token):
        if candidate and candidate in _sessions:
            session = _sessions[candidate]
            g.session_id = candidate
            return session['user_id'], session

    if token:
        user_id = _verify_token(token)
        if user_id:
            return user_id, None

    return None, None


def require_user(fn):
    """Route needs to know who the user is, session optional."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id, session = resolve_identity()
        if not user_id:
            return jsonify({'error': 'not logged in'}), 401
        g.user_id = user_id
        g.session = session
        return fn(*args, **kwargs)
    return wrapper


def require_session(fn):
    """Route needs an active interview session."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id, session = resolve_identity()
        if not session:
            return jsonify({'error': 'invalid or expired session'}), 401
        g.user_id = user_id
        g.session = session
        return fn(*args, **kwargs)
    return wrapper


def _record_points(user_id, role, points):
    record = _user_scores.setdefault(user_id, {'points': [], 'by_role': {}, 'sessions': []})
    record['points'].append(points)
    record['by_role'].setdefault(role, []).append(points)
    return record


# --- static -------------------------------------------------------------
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


# --- auth endpoints -----------------------------------------------------
@app.route('/auth/signup', methods=['POST'])
def signup():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', '').strip()

    if not email or not password:
        return jsonify({'error': 'email and password required'}), 400
    if email in _users:
        return jsonify({'error': 'email already registered'}), 400

    _users[email] = {
        'password': _hash_pw(password),
        'role': role,
        'created_at': _now().isoformat(),
    }
    return jsonify({'token': _make_token(email), 'role': role})


@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = _users.get(email)
    if not user or user['password'] != _hash_pw(password):
        return jsonify({'error': 'invalid credentials'}), 401

    return jsonify({'token': _make_token(email), 'role': user.get('role', '')})


@app.route('/auth/me')
@require_user
def me():
    user = _users.get(g.user_id, {})
    return jsonify({'email': g.user_id, 'role': user.get('role', '')})


# --- session endpoints --------------------------------------------------
@app.route('/session/start', methods=['POST'])
@require_user
def start_session():
    data = request.get_json(silent=True) or {}
    role = data.get('role', '').strip()
    if role not in QUESTIONS:
        return jsonify({'error': 'invalid role'}), 400

    # random id, NOT a JWT - two sessions started in the same second used to
    # produce an identical token and clobber each other
    session_id = uuid.uuid4().hex
    _sessions[session_id] = {
        'user_id': g.user_id,
        'role': role,
        'started_at': _now().isoformat(),
        'questions': [],
    }
    return jsonify({'session_token': session_id, 'role': role})


@app.route('/session/question')
@require_session
def session_question():
    session = g.session
    role = session['role']
    pool = QUESTIONS[role]

    last_q = session['questions'][-1]['question'] if session['questions'] else None
    available = [q for q in pool if q['q'] != last_q] or pool
    chosen = random.choice(available)

    session['questions'].append({
        'question': chosen['q'],
        'asked_at': _now().isoformat(),
    })

    return jsonify({
        'question': chosen['q'],
        'role': role,
        'difficulty': get_difficulty(chosen.get('ideal_length', 80)),
    })


@app.route('/session/submit', methods=['POST'])
@require_session
def session_submit():
    session = g.session
    data = request.get_json(silent=True) or {}
    answer = data.get('answer', '').strip()

    if len(answer) < 20:
        return jsonify({'error': 'Answer too short'}), 400
    if not session['questions']:
        return jsonify({'error': 'No active question. Fetch a question first.'}), 400

    current = session['questions'][-1]
    question = current['question']
    role = session['role']

    result = ai_grade(role, question, answer, get_meta(role, question))
    feedback = result['feedback']
    points = result['points']
    breakdown = result['breakdown']
    grader = 'rule' if result.get('_meta', {}).get('fallback_reason') else 'ai'

    _record_points(session['user_id'], role, points)
    current.update({
        'answer': answer,
        'points': points,
        'feedback': feedback,
        'grader': grader,
    })

    return jsonify({
        'feedback': feedback,
        'points': points,
        'breakdown': breakdown,
        'max_points': 3,
        'grader': grader,
    })


@app.route('/session/correct', methods=['POST'])
@require_session
def session_correct():
    session = g.session
    data = request.get_json(silent=True) or {}
    answer = data.get('answer', '').strip()

    if len(answer) < 20:
        return jsonify({'error': 'Answer too short to improve'}), 400
    if not session['questions']:
        return jsonify({'error': 'No active question.'}), 400

    current = session['questions'][-1]
    question = current['question']
    role = session['role']
    # if they haven't submitted yet there's no feedback to work from, that's fine
    feedback = current.get('feedback', '')

    result = ai_correct(role, question, answer, get_meta(role, question), feedback)
    improvements = result.get('key_improvements', [])

    return jsonify({
        'improved': result['improved_answer'],
        'changes': result.get('changes', []),
        'explanation': ' '.join(improvements) if improvements else 'Suggested improvements below.',
        'source': 'rule' if result.get('_meta', {}).get('fallback_reason') else 'ai',
    })


@app.route('/session/end', methods=['POST'])
@require_session
def end_session():
    session = _sessions.pop(g.session_id)
    total = sum(q.get('points', 0) for q in session['questions'])

    record = _user_scores.setdefault(
        session['user_id'], {'points': [], 'by_role': {}, 'sessions': []}
    )
    record.setdefault('sessions', []).append({
        'role': session['role'],
        'completed_at': _now().isoformat(),
        'questions': session['questions'],
    })

    return jsonify({
        'total_points': total,
        'questions_answered': len(session['questions']),
        'questions': session['questions'],
    })


# --- stats --------------------------------------------------------------
@app.route('/status')
@require_user
def get_status():
    data = _user_scores.get(g.user_id)
    if not data or not data['points']:
        return jsonify({'score': 0, 'answered': 0, 'average': 0, 'by_role': {}})

    total = sum(data['points'])
    answered = len(data['points'])
    return jsonify({
        'score': total,
        'answered': answered,
        'average': round(total / answered, 2),
        'by_role': data['by_role'],
    })


@app.route('/leaderboard')
def leaderboard():
    role = request.args.get('role', '').strip()
    try:
        limit = min(int(request.args.get('limit', 10)), 50)
    except ValueError:
        limit = 10

    if role and role not in QUESTIONS:
        return jsonify({'error': 'Invalid role'}), 400

    rows = []
    for user_id, data in _user_scores.items():
        if role:
            rb = data.get('by_role', {}).get(role, [])
            points = sum(rb) if isinstance(rb, list) else 0
        else:
            points = sum(data.get('points', [])) if isinstance(data.get('points', []), list) else 0
        if points > 0:
            rows.append({'user': user_id, 'score': points})

    rows.sort(key=lambda x: x['score'], reverse=True)
    return jsonify({'leaderboard': rows[:limit], 'role': role or 'all'})


@app.route('/history')
@require_user
def history():
    data = _user_scores.get(g.user_id)
    points = data.get('points', []) if data else []
    if not points:
        return jsonify({'history': [], 'total_score': 0, 'answered': 0, 'average': 0, 'by_role': {}})

    return jsonify({
        'total_score': sum(points),
        'answered': len(points),
        'average': round(sum(points) / len(points), 2),
        'by_role': data.get('by_role', {}),
    })


@app.route('/stats/unlock-status')
@require_user
def stats_unlock():
    answered = len(_user_scores.get(g.user_id, {}).get('points', []))
    return jsonify({
        'unlocked': answered >= 1,
        'answered': answered,
        'required': 1,
    })


@app.route('/stats/summary')
@require_user
def stats_summary():
    data = _user_scores.get(g.user_id, {})
    points = data.get('points', [])
    by_role = data.get('by_role', {})

    total_q = len(points)
    avg = round(sum(points) / total_q, 1) if total_q else 0.0
    best_role = max(by_role, key=lambda r: sum(by_role[r]) / len(by_role[r])) if by_role else '-'

    return jsonify({
        'total_questions': total_q,
        'avg_score': avg,
        'streak': _calc_streak(g.user_id),
        'best_role': best_role,
    })


def _calc_streak(user_id):
    sessions = _user_scores.get(user_id, {}).get('sessions', [])
    dates = set()
    for s in sessions:
        ca = s.get('completed_at')
        if ca:
            dates.add(ca[:10] if isinstance(ca, str) else str(ca)[:10])
    if not dates:
        return 0

    today = _now().date()
    dates_fmt = {d.isoformat() if not isinstance(d, str) else d for d in dates}

    if today.isoformat() in dates_fmt:
        current = today
    elif (today - timedelta(days=1)).isoformat() in dates_fmt:
        current = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while current.isoformat() in dates_fmt:
        streak += 1
        current -= timedelta(days=1)
    return streak


@app.route('/stats/chart-data')
@require_user
def stats_chart_data():
    data = _user_scores.get(g.user_id, {})
    points = data.get('points', [])
    sessions = data.get('sessions', [])

    time_series = []
    by_difficulty = {'easy': [], 'medium': [], 'hard': []}

    for s in sessions:
        role = s.get('role', '')
        for q in s.get('questions', []):
            q_text = q.get('question', '')
            time_series.append({
                'index': len(time_series) + 1,
                'date': s.get('completed_at', '')[:10],
                'score': q.get('points', 0),
                'role': role,
                'question': q_text[:50],
            })
            ideal = get_meta(role, q_text).get('ideal_length', 80)
            by_difficulty[get_difficulty(ideal)].append(q.get('points', 0))

    by_role_avg = {
        role: round(sum(scores) / len(scores), 2)
        for role, scores in data.get('by_role', {}).items() if scores
    }
    by_diff_avg = {
        diff: round(sum(scores) / len(scores), 2)
        for diff, scores in by_difficulty.items() if scores
    }

    dist = {0: 0, 1: 0, 2: 0, 3: 0}
    for p in points:
        if p in dist:
            dist[p] += 1

    return jsonify({
        'time_series': time_series,
        'by_role': by_role_avg,
        'by_difficulty': by_diff_avg,
        'distribution': dist,
    })


@app.route('/stats/export/json')
@require_user
def stats_export_json():
    data = _user_scores.get(g.user_id, {})
    return Response(
        json.dumps(data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=unjobless_history_{g.user_id}.json'},
    )


@app.route('/stats/export/pdf')
@require_user
def stats_export_pdf():
    try:
        from fpdf import FPDF
    except ImportError:
        return jsonify({'error': 'PDF generation not available'}), 503

    user_id = g.user_id
    data = _user_scores.get(user_id, {})
    points = data.get('points', [])
    sessions = data.get('sessions', [])
    total_q = len(points)
    avg = round(sum(points) / total_q, 1) if total_q else 0.0

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 12, 'unJobless - Interview Report', ln=True, align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 7, f'User: {user_id}', ln=True, align='C')
    pdf.cell(0, 7, f'Generated: {_now().strftime("%Y-%m-%d %H:%M UTC")}', ln=True, align='C')
    pdf.ln(8)

    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Summary', ln=True)
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 7, f'Total Sessions: {len(sessions)}', ln=True)
    pdf.cell(0, 7, f'Total Questions: {total_q}', ln=True)
    pdf.cell(0, 7, f'Average Score: {avg}/3.0', ln=True)
    pdf.ln(5)

    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Session History', ln=True)
    for i, s in enumerate(sessions, 1):
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, f'Session {i} - {s.get("role", "Unknown")} - {s.get("completed_at", "")[:10]}', ln=True)
        pdf.set_font('Helvetica', '', 10)
        for j, q in enumerate(s.get('questions', []), 1):
            pdf.cell(0, 6, f'  Q{j}: {q.get("question", "")[:80]}', ln=True)
            pdf.cell(0, 6, f'     Score: {q.get("points", 0)}/3', ln=True)
            if q.get('feedback'):
                pdf.set_font('Helvetica', 'I', 9)
                pdf.multi_cell(0, 5, f'     Feedback: {q["feedback"][:120]}')
                pdf.set_font('Helvetica', '', 10)
        pdf.ln(3)

    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=unjobless_report_{user_id}.pdf'},
    )


# --- meta ---------------------------------------------------------------
@app.route('/health')
def health():
    cost = get_cost_tracker().get_status()
    return jsonify({
        'status': 'running',
        'ai_enabled': ai_teacher.AI_ENABLED,
        'model': ai_teacher.AI_MODEL if ai_teacher.AI_ENABLED else None,
        'prompt_version': ai_teacher.PROMPT_VERSION,
        'grader': 'hybrid (ai + rule fallback)' if ai_teacher.AI_ENABLED else 'rule-based',
        'circuit_status': ai_teacher.breaker.status(),
        'cost_today_usd': cost['daily_usd'],
        'cost_month_usd': cost['monthly_usd'],
        'daily_limit_usd': cost['daily_limit_usd'],
        'monthly_limit_usd': cost['monthly_limit_usd'],
        'roles': list(QUESTIONS.keys()),
        'total_questions': sum(len(v) for v in QUESTIONS.values()),
        'grader_metadata_loaded': bool(GRADER_QUESTIONS),
    })


@app.route('/roles')
def get_roles():
    return jsonify([
        {'name': role, 'emoji': data['emoji'], 'tagline': data['tagline']}
        for role, data in ROLE_DATA.items()
    ])


if __name__ == '__main__':
    total = sum(len(v) for v in QUESTIONS.values())
    logger.info("unJobless on localhost:8000 | %d roles | %d questions", len(QUESTIONS), total)
    app.run(debug=True, port=8000)
