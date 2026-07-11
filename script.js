// module-lvl variable, holds whichever role button the user last clicked
let selectedRole = null;


// btn is passed in so we can toggle the "selected" class on the exact
// btn tht was clicked, rather than re-querrying the DOM for it
async function selectRole(btn, role) {
    // Remove 'selected' class from all role buttons
    document.querySelectorAll('.role-btn').forEach(b => b.classList.remove('selected'));
    // Add 'selected' class to the clicked button 
    // clears any previously selected button first, since only one should ever be highlighted at a time
    btn.classList.add('selected');
    // Store the selected role globally
    selectedRole = role;
    
    // Load question when role is selected
    await loadQuestion(role);
}

// Ctrl+Enter shortcut key for submitting the answer without clicking the button
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('user-answer').addEventListener('keydown', (e)=> {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            submitAnswer();
        }
    });

});

/**
 * Impliments the code for buttons on frontend in case of expanding roles
 */
async function loadRoles() {
    const res = await fetch('/roles');
    const roles = await res.json();
    const grid = document.getElementById('role-grid');

    grid.innerHTML = roles.map(r => `
        <button class="role-btn" onclick="selectRole(this, '${r.name}')">
            ${r.emoji} ${r.name}
            <span>${r.tagline}</span>
        </button>
    `).join('');
}

document.addEventListener('DOMContentLoaded', loadRoles);

/**
 * Load question from backend
 */
async function loadQuestion(role) {
    try {
        const res = await fetch(`/question?role=${encodeURIComponent(role)}`);
        // encodeURIComponent handles role names with space, like "data analyst"
        if (!res.ok) throw new Error('Failed to load question');
        // fetch resolves normally even on a 4xx/5xx so this check is what actually catches the backend returning an error status
        const data = await res.json();
        document.getElementById('question-display').textContent = '▶ ' + data.question;
        // textContent here (not innerHTML) since there's no markup being inserted just plain text
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
        // guard against submitting b4 clicking any role btn since the bckend needs a role to grade against
        alert('Please select a role before submitting your answer.');
        return;
    }

    // Check if answer is long enough
    if (answer.length < 20) {
        // this pg uses a 25-character min while questions.js
        //uses 20 worth aligning the two if the intenet is one consistent rule
        alert('Boy dont play with me, write at least 25 words gng');
        return;
    }

    // FIX #3: Moved all this code INSIDE the function, after validation
    const btn = document.querySelector('.start-btn');
    // queried by class here rather than id since index.html's submit btn uses class="start-btn" instead of id
    btn.disabled = true;
    btn.textContent = '...gradin ts...';

    const feedbackBox = document.getElementById('feedback-box');
    const feedbackText = document.getElementById('feedback-text');
    feedbackBox.style.display = 'block';
    // toggles visibility directly via inline style, rather than swapping a CSS class the way question.js does with 'hidden'/'visible'
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
        // innerHTML here even thought data.feedback is plain text from the server
        // textContent would be the safer choice since there's no actual markup being inserted

    } catch (err) {
        feedbackText.textContent = 'ye cant reach testube or flask or smth, fah';
    } finally {
        // always restores the btn regardless of success/failure so a failed request doesn't leave it stuck disabled
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
    await loadQuestion(selectRole);
    //NOTE: this doesn't call loadQuestion() again, so clicking "next" on
    // this pg clears the ans box but leaves the old question on screen
}