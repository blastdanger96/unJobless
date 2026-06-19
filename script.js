let selectedroll = null;

function setRole(role) {
    document.querySelectorAll('.role-button').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedRoll = role;
}

async function submitAnswer() {
    const answer = document.getElementById('user-answer').value.trim();

    if (!selectedRoll) {
        alert('Please select a role before submitting your answer.')
    }

    if (answer.length < 25) {
        alert('Boy dont play with me, write at least 25 words gng');
    }
    return;
}

const btn = document.querySelectorAll('.start-btn');
btn.disable = true;
btn.textContent = '...gradin ts...';

const feedbackBox = document.getElementById('feedback-box');
const feedbackText = document.getElementById('feedback-text');
feedbackBox.style.display = 'block';
feedbackText.className = 'loading';
feedbackText.textContent = "gradin ts...";
document.getElementById('feedback-box').scrollIntoView({behaviour: 'smooth'});

try {
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
        btn.disable = false;
        btn.textContent = 'Submit Answer';
    }


function nextQuestion() {
    document.getElementById('user-answer').value = '';
    document.getElementById('feedback-box').style.display = 'none';

}