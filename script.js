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

let currentlyTheme = 'dark'

async function btnTheme() {
    if (currentlyTheme === 'dark') {
        currentlyTheme = 'light';

    } else {
        currentlyTheme = 'dark';
    }
    document.documentElement.setAttribute('data-theme', currentlyTheme);
    saveChoice();
}
function saveChoice() {
    localStorage.setItem('unjobless-theme', currentlyTheme);
}
function loadTheme() {
    const saveTheme = localStorage.getItem('unjobless-theme');

    if (saveTheme === 'light') {
        currentlyTheme = 'light';
        document.documentElement.setAttribute('data-theme','light');

    } else if (saveTheme === 'dark') {
        currentlyTheme = 'dark';
        document.documentElement.setAttribute('data-theme','dark');
    }
    // default is dark btw
    //  i aint a monster to put tht shi on light on default
}

document.addEventListener('DOMContentLoaded', loadRoles);

