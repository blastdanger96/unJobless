let selectedRole = null;

/**
 * FIX #1: Changed function name from "setRole" to "selectRole" 
 * to match the onclick="selectRole(...)" in HTML line 25
 */
async function selectRole(btn, role) {
    // Remove 'selected' class from all role buttons
    document.querySelectorAll('.role-btn').forEach(b => b.classList.remove('selected'));
    // Add 'selected' class to the clicked button
    btn.classList.add('selected');
    // Store the selected role globally
    selectedRole = role;
    
    // Load question when role is selected
    await loadQuestion(role);
}

/**
 * Load question from backend
 */
async function loadQuestion(role) {
    try {
        const res = await fetch(`/question?role=${encodeURIComponent(role)}`);
        if (!res.ok) throw new Error('Failed to load question');
        const data = await res.json();
        document.getElementById('question-display').textContent = '▶ ' + data.question;
    } catch (err) {
        document.getElementById('question-display').textContent = '▶ Error loading question. Try again.';
    }
}

/**
 * FIX #2: Wrapped all the loose code that was at top-level
 * inside the submitAnswer() function where it belongs
 */
async function submitAnswer() {
    const answer = document.getElementById('user-answer').value.trim();

    // Check if user selected a role
    if (!selectedRole) {
        alert('Please select a role before submitting your answer.');
        return;
    }

    // Check if answer is long enough
    if (answer.length < 25) {
        alert('Boy dont play with me, write at least 25 words gng');
        return;
    }

    // FIX #3: Moved all this code INSIDE the function, after validation
    const btn = document.querySelector('.start-btn');
    btn.disabled = true;
    btn.textContent = '...gradin ts...';

    const feedbackBox = document.getElementById('feedback-box');
    const feedbackText = document.getElementById('feedback-text');
    feedbackBox.style.display = 'block';
    feedbackText.className = 'loading';
    feedbackText.textContent = "gradin ts...";
    document.getElementById('feedback-box').scrollIntoView({behaviour: 'smooth'});

    try {
        // FIX #4: This await is now INSIDE an async function, so it's valid
        const res = await fetch('/submit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({role: selectedRole, answer: answer})
        });

        if (!res.ok) throw new Error('gradin ts failed');
        const data = await res.json();
        feedbackText.className = '';
        feedbackText.innerHTML = '▶ ' + data.feedback;

    } catch (err) {
        feedbackText.textContent = 'ye cant reach testube or flask or smth, fah';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Submit Answer';
    }
}

/**
 * FIX #5: Wrapped this in async function (already was, just keeping it)
 */
async function nextQuestion() {
    document.getElementById('user-answer').value = '';
    document.getElementById('feedback-box').style.display = 'none';
}