// these 3 lives at module scope (not inside a function) so every function below can read and update them across the whole session
let role = null;
let score = 0;
let questionsAnswered = 0;


// DOMContentLoaded fires once the HTML is parsed, b4 images/fonts finish loading. 
//it works out here cuz nthin below needs those to be ready
//marked async because loadQuestion() inside needs to be awaited
window.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    // pulls wtrv after ? in the URL
    role = params.get('role');

    if (!role) {
        // no rle in the URL means the user landed here without going through index.html's role buttons, so there's isn't anything to quiz em on
        alert('Role not specified. Please provide a role in the URL query parameters.');
        return;
        //stops here rather than throwing, since the rest of this listener assumes role is set
    }

    document.getElementById('role-title').textContent =  role.toUpperCase();
    document.getElementById('role-subtitle').textContent = '//' + role + 'Interview //';

    document.getElementById('user-answer').addEventListener('input', () => {
        // fires on every keystroke in the textaea, used to live-update the word counter
        const text = document.getElementById('user-answer').value.trim();
        const count = text == '' ? 0 :text.split(/\s+/).length;
        // splitting on \s+ (one or more white chars) avoids miscounting
        //when tere are double spaces or tabs between words
        const el = document.getElementById('word-count');
        el.textContent = count;
        el.parentElement.className = 'word-count ' + (count >= 50 ? 'good' : '');
    });

    await loadQuestion();
    // waiting here means nothing else in this listener runs until the irst question has actually loaded
});

async function loadQuestion() {
    try {
        const res = await fetch(`/question?role=${encodeURIComponent(role)}`);
        // encodeURIComponent escapes spaces and special characters in role names like "UI Designer" so the query string stays valid 
        if (!res.ok) throw new Error('fah server was voted out gng');
        // fetch only rejects on network failure not on HTTP error codes, so this manual check is wht catches a 400/500 from backend
        const data = await res.json();
        document.getElementById('question-display').innerHTML =
            '▶ ' + data.question + '<span class="cursor">_</span>';
        // innerHTML (not textContent) because the blinking cursor span needs to actually render as an element not literal txt
        document.getElementById('q-counter').textContent = 'Q' + (questionsAnswered + 1);
        // +1 since questionsAnswered only increments after a question being asked now
    } catch (err) {
        document.getElementById('question-display').innerHTML = 
        'ye cant reach testube or flask or smth, fah';
        // generic fallback message covers both network failure and bad response 
    } 
}

async function submitAnswer() {
    const answer = document.getElementById('user-answer').value.trim();

    if (answer.length < 20) {
        // client-side length gate, mirrors the same 20-char minimum enforced server-side in app.py's /submit route
        alert('stop being deadass fam and write fr gng');
        return;
    }

    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = '...gradin ts...';
    // disabling + relabeling the button gives feedback that the click registered and stops a double-submit while the request is in flight

    const feedbackBox = document.getElementById('feedback-box');
    const feedbackText = document.getElementById('feedback-text');
    const breakdownText = document.getElementById('feedback-breakdown');

    feedbackBox.classList.remove('hidden');
    feedbackText.classList.add('loading');
    feedbackText.textContent = "gradin ts...";
    breakdownText.textContent = '';
    document.getElementById('score-display').textContent = '';
    document.getElementById('next-btn').style.display = 'none';
    // resets the whole feedback panel to a loading state b4 the fetch, so old feedback from the previous question doesn't flash on screen

    feedbackBox.scrollIntoView({behavior: 'smooth'});
    // scrolls the feedback panel into view immediately since it may be below the fold on smaller screens

    try {
        const res = await fetch('/submit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({role: role, answer: answer})
        });

        if (!res.ok) throw new Error('gradin ts failed');
        const data = await res.json();

        feedbackText.classList.remove('loading');
        // clears the 'loading' class so the italic/dim loading style goes away
        feedbackText.textContent = data.feedback;
        breakdownText.textContent = data.breakdown;
        
        score += data.points;
        questionsAnswered += 1;
        
        document.getElementById('score').textContent = score;
        document.getElementById('q-count').textContent = questionsAnswered;
        document.getElementById('score-display').textContent = `${data.points}/${data.max_points} PTS`;

        document.getElementById('next-btn').style.display = 'block';
        // only reveal "next question once grading acc succeeded"

    } catch (err) {
        feedbackText.textContent = 'ye cant reach testube or flask or smth, fah';
    } finally {
        // finally block runs whether the try succeeded or failed so the button always gets re-enabled and doesn't stay stuck
        btn.disabled = false;
        btn.textContent = 'SUBMIT YOUR ANSWER. GOOD LUCK. MAY THO PASS';
    }
}

async function nextQuestion() {
    document.getElementById('user-answer').value = '';
    document.getElementById('word-count').textContent = '0';
    document.getElementById('word-count-label').parentElement.className = 'word-count';
    // resets the word count display back to its default (non-"good") styling
    
    const feedbackBox = document.getElementById('feedback-box');
    feedbackBox.classList.add('hidden');
    // hides the old feedback b4 the new question's box
    await loadQuestion();
}

