// Interview page state. Don't reset these anywhere except resetAnswerUI().
let role = null;
let score = 0;
let questionsAnswered = 0;
let authToken = null;
let sessionToken = null;

const QUESTION_SECONDS = 90;
const SESSION_LENGTH = 5;

let timeRemaining = QUESTION_SECONDS;
let timerInterval = null;
let timerHidden = false;

// submit state - isSubmitting is only ever cleared in a finally block
let isSubmitting = false;
let isImproving = false;
let submitAbortControl = null;

// AI correction payload for the modal
let currentImproved = '';
let currentChanges = [];


// One fetch wrapper. No internal retries - the caller decides that, otherwise
// you end up firing six requests for a single submit.
async function apiFetch(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const err = new Error(data.error || `request failed (${res.status})`);
        err.status = res.status;
        throw err;
    }
    return res;
}

function $(id) {
    return document.getElementById(id);
}


async function initAuth() {
    const existing = localStorage.getItem('auth_token');
    if (existing) return existing;

    // no login screen yet, so everyone gets an anonymous account
    const email = 'anon_' + Math.random().toString(36).slice(2, 11) + '@unjobless.local';
    try {
        const res = await apiFetch('/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password: 'anonymous', role: '' })
        });
        const data = await res.json();
        localStorage.setItem('auth_token', data.token);
        return data.token;
    } catch (e) {
        console.error('anonymous signup failed', e);
        return null;
    }
}

async function ensureSession() {
    if (sessionToken) return sessionToken;
    if (!authToken || !role) return null;

    try {
        const res = await apiFetch('/session/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + authToken
            },
            body: JSON.stringify({ role })
        });
        const data = await res.json();
        sessionToken = data.session_token;
        localStorage.setItem('session_token', sessionToken);
        return sessionToken;
    } catch (e) {
        console.error('could not start session', e);
        sessionToken = null;
        return null;
    }
}

async function init() {
    const params = new URLSearchParams(window.location.search);
    role = params.get('role');

    if (!role) {
        alert('No role given. Head back and pick one.');
        window.location.href = 'index.html';
        return;
    }

    $('role-title').textContent = role.toUpperCase();
    $('role-subtitle').textContent = '// ' + role + ' INTERVIEW //';

    const answerEl = $('user-answer');

    answerEl.addEventListener('input', updateWordCount);
    answerEl.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            submitAnswer();
        }
    });

    authToken = await initAuth();
    await syncProgress();
    await ensureSession();
    await loadQuestion();

    // Ensure modal is hidden on new session start
    const modal = $('correction-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('visible');
        modal.style.display = 'none';
    }
    currentImproved = '';
    currentChanges = [];
}

function updateWordCount() {
    const text = $('user-answer').value.trim();
    const count = text === '' ? 0 : text.split(/\s+/).length;
    $('word-count').textContent = count;
    $('word-count-label').classList.toggle('good', count >= 50);
}

function updateProgressUI() {
    const current = questionsAnswered + 1;
    const fill = $('progress-fill');
    if (fill) {
        fill.style.width = Math.min((current / SESSION_LENGTH) * 100, 100) + '%';
    }
    $('q-counter').textContent = 'Q' + current;
    $('q-count').textContent = questionsAnswered;
    $('score').textContent = score;
}

async function syncProgress() {
    if (!authToken) return;
    try {
        const headers = { 'Authorization': 'Bearer ' + authToken };
        if (sessionToken) headers['X-Session-Token'] = sessionToken;

        const res = await apiFetch('/stats/unlock-status', { headers });
        const data = await res.json();
        questionsAnswered = data.answered || 0;
        localStorage.setItem('answered_count', questionsAnswered);
    } catch (e) {
        // not worth blocking the page over, we just keep the local count
        console.warn('progress sync failed', e.message);
    }
    updateProgressUI();
}


// --- questions ---------------------------------------------------------

// nextQuestion and skipQuestion used to be the same function copy-pasted twice,
// so they're folded in here. actionType is 'initial' | 'next' | 'skip' | 'retry'
// and only decides how much of the UI we wipe before fetching.
async function loadQuestion(actionType = 'initial') {
    if (!role) return;

    if (actionType === 'next' || actionType === 'skip') {
        stopTimer();
        if (submitAbortControl) {
            submitAbortControl.abort();
            submitAbortControl = null;
        }
        resetAnswerUI();
    }

    const display = $('question-display');
    display.innerHTML = 'LOADING....<span class="cursor">_</span>';

    resetTimerUI();

    if (!(await ensureSession())) {
        display.innerHTML = 'Could not start a session. <button class="retry-btn" onclick="loadQuestion(\'retry\')">RETRY</button>';
        return;
    }

    try {
        const res = await apiFetch('/session/question', {
            headers: { 'Authorization': 'Bearer ' + sessionToken }
        });
        const data = await res.json();

        display.innerHTML = '&gt; ' + escapeHtml(data.question) + '<span class="cursor">_</span>';

        const badge = $('difficulty-lvl');
        if (data.difficulty) {
            badge.textContent = data.difficulty.toUpperCase();
            badge.className = data.difficulty;
        }

        updateProgressUI();
        startTimer();
    } catch (e) {
        // most likely the session expired, so drop it and let retry rebuild one
        if (e.status === 401) sessionToken = null;
        display.innerHTML = 'Unable to load question. <button class="retry-btn" onclick="loadQuestion(\'retry\')">RETRY</button>';
    }
}

// the HTML binds these via onclick, so keep them as thin named wrappers
function nextQuestion() {
    return loadQuestion('next');
}

function skipQuestion() {
    return loadQuestion('skip');
}

function resetAnswerUI() {
    $('user-answer').value = '';
    updateWordCount();

    $('feedback-box').classList.add('hidden');
    $('feedback-text').textContent = '';
    $('feedback-breakdown').textContent = '';
    $('score-display').textContent = '';

    const submitBtn = $('submit-btn');
    submitBtn.disabled = false;
    submitBtn.textContent = 'SUBMIT YOUR ANSWER';

    const improveBtn = $('improve-btn');
    improveBtn.disabled = false;
    improveBtn.textContent = 'AI IMPROVE MY ANSWER';
    improveBtn.classList.add('hidden');
}


// --- timer -------------------------------------------------------------

function resetTimerUI() {
    timerHidden = false;
    $('timer-box').classList.remove('timer-hidden');
    const btn = $('hide-timer-btn');
    btn.textContent = 'HIDE TIMER';
    btn.onclick = hideTimer;
}

function startTimer() {
    stopTimer();
    if (timerHidden) return;

    timeRemaining = QUESTION_SECONDS;
    updateTimerDisplay();

    timerInterval = setInterval(() => {
        timeRemaining--;
        updateTimerDisplay();
        if (timeRemaining <= 0) {
            stopTimer();
            handleTimeUp();
        }
    }, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function hideTimer() {
    timerHidden = true;
    stopTimer();
    $('timer-box').classList.add('timer-hidden');
    const btn = $('hide-timer-btn');
    btn.textContent = 'SHOW TIMER';
    btn.onclick = showTimer;
}

function showTimer() {
    timerHidden = false;
    $('timer-box').classList.remove('timer-hidden');
    const btn = $('hide-timer-btn');
    btn.textContent = 'HIDE TIMER';
    btn.onclick = hideTimer;
    startTimer();
}

function updateTimerDisplay() {
    const timerEl = $('timer-display');
    const fillEl = $('timer-fill');
    if (!timerEl || !fillEl) return;

    const mins = Math.floor(timeRemaining / 60);
    const secs = timeRemaining % 60;
    timerEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
    fillEl.style.width = Math.max((timeRemaining / QUESTION_SECONDS) * 100, 0) + '%';

    timerEl.classList.remove('warning', 'critical');
    fillEl.classList.remove('warning', 'critical');

    if (timeRemaining <= 10) {
        timerEl.classList.add('critical');
        fillEl.classList.add('critical');
    } else if (timeRemaining <= 30) {
        timerEl.classList.add('warning');
        fillEl.classList.add('warning');
    }
}

function handleTimeUp() {
    if (isSubmitting) return;

    stopTimer();  // stop first so interval won't fire submitAgain
    const answer = $('user-answer').value.trim();
    if (answer.length >= 20) {
        submitAnswer();
    } else {
        alert("Time's up on this one. Moving on.");
        nextQuestion();
    }
}


// --- submit ------------------------------------------------------------

async function submitAnswer() {
    // every guard runs BEFORE the lock goes up, otherwise an early return
    // leaves isSubmitting stuck true and the page never accepts input again
    if (isSubmitting) return;
    if (!role) {
        alert('No role set. Reload the page with a valid role.');
        return;
    }

    const answer = $('user-answer').value.trim();
    if (answer.length < 20) {
        alert('That is too short to grade. Write a real answer first.');
        return;
    }

    isSubmitting = true;
    stopTimer();

    submitAbortControl = new AbortController();
    const signal = submitAbortControl.signal;

    const btn = $('submit-btn');
    btn.disabled = true;
    btn.textContent = 'GRADING...';

    const feedbackBox = $('feedback-box');
    const feedbackText = $('feedback-text');
    const breakdownText = $('feedback-breakdown');

    feedbackBox.classList.remove('hidden');
    feedbackText.classList.add('loading');
    feedbackText.textContent = 'Grading your answer...';
    breakdownText.textContent = '';
    $('score-display').textContent = '';
    $('next-btn').classList.add('hidden');
    feedbackBox.scrollIntoView({ behavior: 'smooth' });

    try {
        if (!(await ensureSession())) {
            throw new Error('Could not start a session.');
        }

        const res = await apiFetch('/session/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + sessionToken
            },
            body: JSON.stringify({ answer }),
            signal
        });
        const data = await res.json();

        feedbackText.classList.remove('loading');
        feedbackText.textContent = data.feedback;
        breakdownText.textContent = data.breakdown;
        $('score-display').textContent = `${data.points}/${data.max_points} PTS`;

        score += data.points;
        questionsAnswered += 1;
        await syncProgress();

        $('next-btn').classList.remove('hidden');
        $('improve-btn').classList.remove('hidden');
        addStatsButton();
    } catch (err) {
        if (err.name === 'AbortError') {
            // user hit next/skip mid-request, nothing to report
            feedbackBox.classList.add('hidden');
        } else {
            if (err.status === 401 || err.status === 403) sessionToken = null;
            console.error('submit failed', err);
            feedbackText.classList.remove('loading');
            feedbackText.textContent = 'Grading failed: ' + err.message;
            breakdownText.innerHTML = '<button class="retry-btn" onclick="submitAnswer()">TRY AGAIN</button>';
        }
    } finally {
        // this is the whole point - the UI unlocks no matter how we got here
        isSubmitting = false;
        submitAbortControl = null;
        btn.disabled = false;
        btn.textContent = 'SUBMIT YOUR ANSWER';
    }
}

function addStatsButton() {
    if ($('unblock-stats-btn')) return;

    const footer = document.querySelector('.footer');
    if (!footer) return;

    const statBtn = document.createElement('button');
    statBtn.id = 'unblock-stats-btn';
    statBtn.textContent = 'VIEW PROGRESS ->';
    statBtn.onclick = async () => {
        if (sessionToken) {
            try {
                await fetch('/session/end', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + sessionToken }
                });
            } catch (e) {
                console.warn('session end failed', e);
            }
        }
        window.location.href = 'stats.html';
    };
    footer.appendChild(statBtn);
}


// --- AI improve --------------------------------------------------------

async function improveAnswer() {
    if (isImproving) return;
    if (!role) {
        alert('No role set. Reload the page.');
        return;
    }

    const answer = $('user-answer').value.trim();
    if (answer.length < 20) {
        alert('Write a bit more before asking for an improvement.');
        return;
    }

    isImproving = true;
    const btn = $('improve-btn');
    btn.disabled = true;
    btn.textContent = 'IMPROVING...';

    try {
        if (!(await ensureSession())) {
            throw new Error('Could not start a session.');
        }

        const res = await apiFetch('/session/correct', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + sessionToken
            },
            body: JSON.stringify({ answer })
        });
        const data = await res.json();

        currentImproved = data.improved;
        currentChanges = data.changes || [];
        showCorrection(data.explanation, currentChanges);
    } catch (err) {
        if (err.status === 401 || err.status === 403) sessionToken = null;
        console.error('improve failed', err);
        alert('AI improvement is unavailable right now.');
    } finally {
        isImproving = false;
        btn.disabled = false;
        btn.textContent = 'AI IMPROVE MY ANSWER';
    }
}

function showCorrection(explanation, changes) {
    const modal = $('correction-modal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('visible');
    }

    $('correction-explanation').innerHTML =
        `<p class="correction-explanation">${escapeHtml(explanation)}</p>`;

    const parts = ['<div class="diff-container">'];
    changes.forEach(c => {
        const cls = c.type === 'add' ? 'diff-add'
            : c.type === 'remove' ? 'diff-remove'
            : 'diff-replace';

        parts.push(`<div class="diff-line ${cls}">`);
        if (c.original) parts.push(`<span class="diff-original">${escapeHtml(c.original)}</span>`);
        if (c.improved) parts.push(`<span class="diff-improved">${escapeHtml(c.improved)}</span>`);
        parts.push(`<span class="diff-reason">${escapeHtml(c.reason || '')}</span></div>`);
    });
    parts.push('</div>');

    $('correction-diff').innerHTML = parts.join('');
}

function applyCorrection() {
    const answerEl = $('user-answer');
    answerEl.value = currentImproved;
    updateWordCount();
    closeCorrection();
}

function closeCorrection() {
    const modal = $('correction-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('visible');
        modal.style.display = 'none';
    }
    currentImproved = '';
    currentChanges = [];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : text;
    return div.innerHTML;
}


// --- boot --------------------------------------------------------------

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

window.addEventListener('beforeunload', () => {
    stopTimer();
    if (submitAbortControl) submitAbortControl.abort();
});
