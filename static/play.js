// ===== TEAM STATE =====
let teams = [];
let currentPoints = 0;
let currentTile = null;

function saveTeams() {
  localStorage.setItem('jeopardy_teams', JSON.stringify(teams));
}

function loadTeams() {
  try {
    const saved = localStorage.getItem('jeopardy_teams');
    if (saved) teams = JSON.parse(saved);
  } catch(e) { teams = []; }
}

// ===== SCOREBOARD =====
function renderScoreboard() {
  const sb = document.getElementById('scoreboard');
  if (!teams.length) { sb.innerHTML = ''; return; }
  sb.innerHTML = teams.map((t, i) =>
    `<div class="team-card">
      <span class="team-name">${escHtml(t.name)}</span>
      <span class="team-score" id="score-${i}">${t.score}</span>
      <div class="score-btns">
        <button class="score-adj" onclick="adjustScore(${i}, 100)">+100</button>
        <button class="score-adj" onclick="adjustScore(${i}, -100)">-100</button>
      </div>
    </div>`
  ).join('');
}

window.adjustScore = (idx, delta) => {
  teams[idx].score += delta;
  saveTeams();
  renderScoreboard();
};

// ===== SETUP MODAL =====
const setupModal = document.getElementById('setup-modal');
const teamCountInput = document.getElementById('team-count');
const teamNameInputs = document.getElementById('team-name-inputs');
const startBtn = document.getElementById('start-game');
const settingsBtn = document.getElementById('settings-btn');
const gradeFilterSelect = document.getElementById('grade-filter');

function buildNameInputs() {
  const n = parseInt(teamCountInput.value) || 2;
  teamNameInputs.innerHTML = '';
  for (let i = 0; i < n; i++) {
    const existing = teams[i] ? teams[i].name : `Team ${i + 1}`;
    teamNameInputs.innerHTML +=
      `<input class="team-name-input" type="text" placeholder="Team ${i+1}" value="${escHtml(existing)}" maxlength="24">`;
  }
}

teamCountInput.addEventListener('input', buildNameInputs);

startBtn.addEventListener('click', () => {
  const inputs = document.querySelectorAll('.team-name-input');
  teams = Array.from(inputs).map((inp, i) => ({
    name: inp.value.trim() || `Team ${i+1}`,
    score: teams[i] ? teams[i].score : 0
  }));
  saveTeams();
  renderScoreboard();
  setupModal.classList.add('hidden');
  applyGradeFilter();
});

settingsBtn.addEventListener('click', () => {
  teamCountInput.value = teams.length || 2;
  buildNameInputs();
  setupModal.classList.remove('hidden');
});

// ===== GRADE FILTER =====
// Konsistente Filterlogik: unterstuetzt sowohl Einzelklassen ('7')
// als auch historische Bereiche ('7-8', '8-9', '9-10') im gleichen Datenbestand.
function gradeMatches(gradeLevel, selectedGrade) {
  if (!selectedGrade) return true;
  if (!gradeLevel) return false;
  return gradeLevel.split('-').map(p => p.trim()).includes(selectedGrade);
}

function applyGradeFilter() {
  const grade = gradeFilterSelect.value;
  document.querySelectorAll('.question-tile').forEach(tile => {
    if (tile.disabled) return;
    const tileGrade = tile.dataset.gradeLevel || '';
    tile.style.display = gradeMatches(tileGrade, grade) ? '' : 'none';
  });
}

gradeFilterSelect.addEventListener('change', applyGradeFilter);

// ===== QUESTION MODAL =====
const modal = document.getElementById('question-modal');
const modalQuestion = document.getElementById('modal-question');
const modalAnswer = document.getElementById('modal-answer');
const modalGradeBadge = document.getElementById('modal-grade-badge');
const showAnswerBtn = document.getElementById('show-answer');
const closeBtn = document.getElementById('close-modal');
const noPointsBtn = document.getElementById('no-points-btn');
const teamScoreButtons = document.getElementById('team-score-buttons');
const pointsSection = document.getElementById('points-section');

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function buildTeamScoreButtons(points) {
  if (!teams.length) {
    teamScoreButtons.innerHTML = '<em style="opacity:.6">Keine Teams konfiguriert.</em>';
    return;
  }
  teamScoreButtons.innerHTML = teams.map((t, i) =>
    `<button class="btn-team-score" onclick="awardPoints(${i}, ${points})">
      +${points} &rarr; ${escHtml(t.name)}
    </button>`
  ).join('');
}

window.awardPoints = (teamIdx, points) => {
  teams[teamIdx].score += points;
  saveTeams();
  renderScoreboard();
  closeModal();
};

function closeModal() {
  if (currentTile) {
    currentTile.disabled = true;
    currentTile.style.opacity = '0.25';
  }
  modal.classList.add('hidden');
  pointsSection.classList.add('hidden');
  modalAnswer.classList.add('hidden');
  currentTile = null;
  currentPoints = 0;
}

closeBtn.addEventListener('click', closeModal);
noPointsBtn.addEventListener('click', closeModal);

showAnswerBtn.addEventListener('click', () => {
  modalAnswer.classList.remove('hidden');
  pointsSection.classList.remove('hidden');
  buildTeamScoreButtons(currentPoints);
});

// ===== TILE CLICKS =====
document.querySelectorAll('.question-tile').forEach(tile => {
  tile.addEventListener('click', async () => {
    currentTile = tile;
    const id = tile.dataset.questionId;
    const res = await fetch(`/api/question/${id}`);
    if (!res.ok) return;
    const data = await res.json();
    currentPoints = data.points;
    modalQuestion.textContent = data.question_text;
    modalAnswer.textContent = data.answer_text;
    modalGradeBadge.textContent = data.grade_level ? `Klasse ${data.grade_level}` : '';
    modalAnswer.classList.add('hidden');
    pointsSection.classList.add('hidden');
    modal.classList.remove('hidden');
  });
});

// ===== INIT =====
loadTeams();
buildNameInputs();
if (!teams.length) {
  setupModal.classList.remove('hidden');
} else {
  setupModal.classList.add('hidden');
  renderScoreboard();
}