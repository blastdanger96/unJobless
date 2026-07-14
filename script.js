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

// typerwritr effect
function runTypewriting() {
    const el = document.getElementById('typewriter-text');
    if (!el) return;

    const text = 'no fluff. no filler. just interview prep.';
    let i = 0;

    function type() {
        if (i< text.length) {
            el.innerHTML = text.slice(0,i+1) + '<span class="typewriter-cursor">_</span>';
            i++;
            setTimeout(type,55);

        } else {
            el.innerHTML = text + '<span class="typewriter-cursor">_</span>';
        }
    }
    setTimeout(type, 750);
}

function initReveal () {
    const elemnts = document.querySelectorAll('.reveal:not(.visible)');
    const observer = new IntersectionObserver((entries)=> {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12});

    elemnts.forEach(el => observer.observe(el));
}

// --boot---
function init() {
    loadRoles();
    runTypewriting();
    initReveal();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}