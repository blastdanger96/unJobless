// these 3 lives at module scope (not inside a function) so every function below can read and update them across the whole session
let role = null;
let score = 0;
let questionsAnswered = 0;
let timeRemaining = 90;
let timerInterval = null;
const timer_sec = 90;
let timerHidden = false;

// correction state
let currentImproved = '';
let currentChanges = [];
// submit state of submittion
let isSubmitting = false;
let submitAbortControl = null;

async function init() {
    const params = new URLSearchParams(window.location.search);
    role = params.get('role');

    document.getElementById('user-answer').addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (!isSubmitting) {
            submitAnswer();
            }
        }
    });

    if (!role) {
        alert('Role not specified. Please provide a role in the URL query parameters.');
        return;
    }

    document.getElementById('role-title').textContent = role.toUpperCase();
    document.getElementById('role-subtitle').textContent = '//' + role + 'Interview //';

    document.getElementById('user-answer').addEventListener('input', () => {
        const text = document.getElementById('user-answer').value.trim();
        const count = text === '' ? 0 : text.split(/\s+/).length;
        const el = document.getElementById('word-count');
        el.textContent = count;
        el.parentElement.className = 'word-count ' + (count >= 50 ? 'good' : '');
    });

    await loadQuestion();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init(); 
}

window.addEventListener('beforeunload', () => {
    stopTimer();
    if (submitAbortControl) {
        submitAbortControl.abort();
    }
});

async function loadQuestion() {
    if (!role) {
        document.getElementById('question-display').innerHTML = 'Error: No role specified';
        return;
    }

    timerHidden = false;
    document.getElementById('timer-box').classList.remove('timer-hidden');
    document.getElementById('hide-timer-btn').textContent = 'HIDE TIMER';
    document.getElementById('hide-timer-btn').onclick = hideTimer;
    try {
        const res = await fetch(`/question?role=${encodeURIComponent(role)}`);
        if (!res.ok) throw new Error(`Failed to load question (${res.status})`);
        const data = await res.json();
        document.getElementById('question-display').innerHTML =
            '> ' + data.question + '<span class="cursor">_</span>';
        document.getElementById('q-counter').textContent = 'Q' + (questionsAnswered + 1);
        startTimer();
        const badge = document.getElementById('difficulty-lvl');

        if (badge && data.difficulty) {
            badge.textContent = data.difficulty.toUpperCase();
            badge.className = data.difficulty;
        }

    } catch (err) {
        console.error('Failed to load question:', err);
        document.getElementById('question-display').innerHTML = 
            'Failed to load question. <button onclick="loadQuestion()">Retry</button>';
    } 
}

async function startTimer() {
    if (timerHidden) return;
    if (timerInterval) clearInterval(timerInterval);
    timeRemaining = timer_sec;
    updateDisplay();

    timerInterval = setInterval(() =>{
        timeRemaining--;
        updateDisplay();

        if (timeRemaining <= 0 ) {
            clearInterval(timerInterval);
            timerInterval = null;
            handleTime();
        }
    }, 1000);
}

function hideTimer() {
    timerHidden = true;
    stopTimer();
    document.getElementById('timer-box').classList.add('timer-hidden');
    const btn = document.getElementById('hide-timer-btn');
    btn.textContent = 'SHOW TIMER';
    btn.onclick = showTimer;
}

function showTimer() {
    timerHidden = false;
    document.getElementById('timer-box').classList.remove('timer-hidden');
    const btn = document.getElementById('hide-timer-btn');
    btn.textContent = 'HIDE TIMER';
    btn.onclick = hideTimer;
    startTimer(); 
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function updateDisplay() {
    const timerEl = document.getElementById('timer-display');
    const timerFillEl = document.getElementById('timer-fill');
    if (!timerEl || !timerFillEl) return;

    const mins = Math.floor(timeRemaining / 60);
    const sec = timeRemaining % 60;
    timerEl.textContent = `${mins}:${sec.toString().padStart(2,'0')}`;

    const pct = (timeRemaining/timer_sec) * 100;
    timerFillEl.style.width = pct + '%';

    timerEl.classList.remove('warning','critical');
    timerFillEl.classList.remove('warning','critical');

    if (timeRemaining <= 10) {
        timerEl.classList.add('critical');
        timerFillEl.classList.add('critical');
    } else if (timeRemaining <= 30) {
        timerEl.classList.add('warning');
        timerFillEl.classList.add('warning');
    }

}

function handleTime () {
    if (isSubmitting) {
        console.log('Manual submit in progress, skipping auto-submit');
        return;
    }
    const answer = document.getElementById('user-answer').value.trim();
    if (answer.length >= 20) {
        submitAnswer();
    } else {
        alert('times up lil bro')
        nextQuestion();
    }
}

async function submitAnswer() {
    if (isSubmitting) {
        console.log('Submit already in progress, ignoring');
        return;
    }
    isSubmitting = true;
    if (!role) {
        alert('Role not specified. Please reload the page with a valid role.');
        return;
    }

    const answer = document.getElementById('user-answer').value.trim();

    if (answer.length < 20) {
        alert('stop being deadass fam and write fr gng');
        return;
    }

    stopTimer();
    submitAbortControl = new AbortController();
    const signal = submitAbortControl.signal;

    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = '...gradin ts...';

    const feedbackBox = document.getElementById('feedback-box');
    const feedbackText = document.getElementById('feedback-text');
    const breakdownText = document.getElementById('feedback-breakdown');

    feedbackBox.classList.remove('hidden');
    feedbackText.classList.add('loading');
    feedbackText.textContent = "gradin ts...";
    breakdownText.textContent = '';
    document.getElementById('score-display').textContent = '';
    document.getElementById('next-btn').style.display = 'none';

    feedbackBox.scrollIntoView({behavior: 'smooth'});

    try {
        const res = await fetch('/submit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({role: role, answer: answer}),
            signal
        });

        if (signal.aborted) {
            console.log('Submit aborted');
            return;
        }

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.error || `grading failed (${res.status})`);
        }
        const data = await res.json();

        feedbackText.classList.remove('loading');
        feedbackText.textContent = data.feedback;
        breakdownText.textContent = data.breakdown;
        
        score += data.points;
        questionsAnswered += 1;
        
        document.getElementById('score').textContent = score;
        document.getElementById('q-count').textContent = questionsAnswered;
        document.getElementById('score-display').textContent = `${data.points}/${data.max_points} PTS`;

        document.getElementById('next-btn').style.display = 'block';
        document.getElementById('improve-btn').style.display = 'block';

    } catch (err) { 
        if (err.name === 'AbortError' || signal.aborted) {
            console.log('Submit aborted');
            return;
        }
        console.error('Submit failed:', err);
        feedbackText.textContent = 'Failed to submit answer. Please try again.';

    } finally {
        if (!signal.aborted) {
        btn.disabled = false;
        btn.textContent = 'SUBMIT YOUR ANSWER. GOOD LUCK. MAY THO PASS';
        }

        isSubmitting = false;
        submitAbortControl = null;
    }
}

async function nextQuestion() {
    if (submitAbortControl) {
        submitAbortControl.abort();
        submitAbortControl = null;
    } 
    isSubmitting = false;

    document.getElementById('user-answer').value = '';
    document.getElementById('word-count').textContent = '0'; 
    document.getElementById('word-count-label').className = '';
    // resets the word count display back to its default (non-"good") styling
    
    const feedbackBox = document.getElementById('feedback-box');
    feedbackBox.classList.add('hidden');
    // hides the old feedback b4 the new question's box
    await loadQuestion();
}

async function skipQuestion() {
    stopTimer();

    if (submitAbortControl) {
        submitAbortControl.abort();
        submitAbortControl = null;
    }
    isSubmitting = false;

    document.getElementById('user-answer').value = '';
    document.getElementById('word-count').textContent = '0';
    document.getElementById('word-count-label').className = '';

    const feedbackBox = document.getElementById('feedback-box');
    feedbackBox.classList.add('hidden');
    loadQuestion();
}

async function improveAnswer() {
    if (!role) {
        alert('Role not specified. Please reload the page.');
        return;
    }

    const answer = document.getElementById('user-answer').value.trim();
    if (answer.length < 20) {
        alert('write more first dawg');
        return;
    } 

    const btn = document.getElementById('improve-btn');
    btn.disabled = true;
    btn.textContent = '...improving...';

    try {
        const res = await fetch('/correct', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({role: role, answer: answer})
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.error || `improvement failed (${res.status})`);
        }
        const data = await res.json();

        currentImproved = data.improved;
        currentChanges = data.changes;
        showCorrection(data.explanation, data.changes);

    } catch (err) {
        console.error('AI correction failed:', err);
        alert(err.message || 'AI correction failed');
    } finally {
        btn.disabled = false;
        btn.textContent = 'AI IMPROVE MY ANSWER';
    }
}

function showCorrection(explanation, changes) {
    const modal = document.getElementById('correction-modal');
    const expEl = document.getElementById('correction-explanation');
    const diffEl = document.getElementById('correction-diff');

    expEl.innerHTML = `<p class="correction-explanation">${explanation}</p>`;

    let diffHtml = '<div class="diff-container">';
    changes.forEach(c => {
        const cls = c.type === 'add' ? 'diff-add' : (c.type === 'remove' ? 'diff-remove' : 'diff-replace');
        diffHtml += `<div class="diff-line ${cls}">`;
        if (c.original) diffHtml += `<span class="diff-original">${escapeHtml(c.original)}</span>`;
        if (c.improved) diffHtml += `<span class="diff-improved">${escapeHtml(c.improved)}</span>`;
        diffHtml += `<span class="diff-reason">${escapeHtml(c.reason)}</span></div>`;
    });
    diffHtml += '</div>';
    diffEl.innerHTML = diffHtml;

    modal.classList.remove('hidden');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function applyCorrection() {
    document.getElementById('user-answer').value = currentImproved;
    document.getElementById('user-answer').dispatchEvent(new Event('input'));
    closeCorrection();
}

function closeCorrection() {
    document.getElementById('correction-modal').classList.add('hidden');
    currentImproved = '';
    currentChanges = [];
}