let role = null;
let score = 0;
let questionsAnswered = 0;

window.addEvenentListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    role = params.get('role');

    if (!role) {
        alert('Role not specified. Please provide a role in the URL query parameters.');
        return;
    }

    document.getElementById('role-title').textContent =  role.toUpperCase();
    document.getElementById('role-subtitle').textContent = '//' + role + 'Interview //';

    document.getElementById('user-answer').addEvenentListener('input', () => {
        const text = document.getElementById('user-answer').value.trim();
        const count = text == '' ? 0 :text.split(/\s+/).length;
        const el = document.getElementById('word-count');
        el.textContent = count;
        el.parentElement.className = 'word-count' + (count >= 50 ? 'good' : '');
    });

    await loadQuestion();
});

async function loadQuestion() {
    try {
        const res = await fetch('/question?role=${encodeURIComponent(role)}');
        if (!res.ok) throw new Error('fah server was voted out gng');
        const data = await res.json();
        document.getElementById('question-display').innerHTML =
            '▶ ' + data.question + '<span class="cursor">_</span>';
        document.getElementById('q-counter').textContent = 'Q' + (questionsAnswered + 1);
    } catch (err) {
        document.getElementById('question-dispay').innerHTML = 
        'ye cant reach testube or flask or smth, fah';
    } 
}

async function submitAnswer() {
    const answer = document.getElementById('user-answer').value.trim();

    if (answer.length < 20) {
        alert('stop being deadass fam and write fr gng');
        return;
    }

    const btn = document.getElementById('submit-btn');
    btn.disable = true;
    btn.textContent = '...gradin ts...';

    const feedbackBox = document.getElementById('feedback-box');
    const feedbackText = document.getElementById('feedback-text');
    const breakdownText = document.getElementById('breakdown-text');

    feedbackBox.className = 'visible';
    feedbackText.className = 'shush, lemme cook...';
    feedbackText.textContent = "gradin ts...";
    breakdownText.textContent = '';
    document.getElementById('score-display').textContent = '';
    document.getElementById('next-btn').style.display = 'none';

    feedbackBox.scrollIntoView({behavior: 'smooth'});

    try {
        const res = await fetch('/submit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({role: role, answer: answer})
        });

        }
    