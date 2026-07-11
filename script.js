// defining the functions for loading roles
async function loadRoles() {
    const res = await fetch('/roles');
    const roles = await res.json()
    // classifying them to be able to be recognizable by HTML file
    const grid = document.getElementById('role-grid');

    grid.innerHTML = roles.map(r => `
        <button class="role-btn" onclick="selectRole('${r.name}')">
            ${r.emoji} ${r.name}
            <span>${r.tagline}</span>
        </button>
    `).join(''); // format of the role names, done to avoid repetitions
}

//calling function defined above
function selectRole(role) {
    window.location.href = `questions.html?role=${encodeURIComponent(role)}`;
}

document.addEventListener('DOMContentLoaded', loadRoles);