// ===== TEAM STATE =====
let teams = [];
let currentPoints = 0;
let currentTile = null;
let lastChanged = -1;

function saveTeams() {
  localStorage.setItem('jeopardy_teams', JSON.stringify(teams));
}

function loadTeams() {
  try {
    const saved = localStorage.getItem('jeopardy_teams');
    if (saved) teams = JSON.parse(saved);
  } catch(e) { teams = []; }
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ===== SCOREBOARD =====
function renderScoreboard() {
  const sb = document.getElementById('scoreboard');
  if (!teams.length) { sb.innerHTML = ''; return; }
  const max = Math.max.apply(null, teams.map(t => t.score));
  const hasLeader = max > 0 && teams.filter(t => t.score === max).length === 1;
  sb.innerHTML = teams.map((t, i) =>
    `<div class="team-card${hasLeader && t.score === max ? ' leader' : ''}">
      <span class="team-name">${escHtml(t.name)}</span>
      <span class="team-score${i === lastChanged ? ' bump' : ''}" id="score-${i}">${t.score}</span>
      <div class="score-btns">
        <button class="score-adj" type="button" onclick="adjustScore(${i}, -100)" aria-label="100 Punkte abziehen">&minus;100</button>
        <button class="score-adj" type="button" onclick="adjustScore(${i}, 100)" aria-label="100 Punkte addieren">+100</button>
      </div>
    </div>`
  ).join('');
  lastChanged = -1;
}

window.adjustScore = (idx, delta) => {
  teams[idx].score += delta;
  lastChanged = idx;
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

function setModalOpen(open) {
  document.body.classList.toggle('modal-open', open);
}

function buildNameInputs() {
  const n = Math.min(6, Math.max(1, parseInt(teamCountInput.value) || 2));
  teamNameInputs.innerHTML = '';
  for (let i = 0; i < n; i++) {
    const existing = teams[i] ? teams[i].name : `Team ${i + 1}`;
    teamNameInputs.innerHTML +=
      `<input class="team-name-input" type="text" placeholder="Team ${i+1}" value="${escHtml(existing)}" maxlength="24" aria-label="Name Team ${i+1}">`;
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
  setModalOpen(false);
  applyGradeFilter();
});

settingsBtn.addEventListener('click', () => {
  teamCountInput.value = teams.length || 2;
  buildNameInputs();
  setupModal.classList.remove('hidden');
  setModalOpen(true);
});

// ===== GRADE FILTER =====
// Der Filter laeuft serverseitig (/play?grade=7). So werden die Felder des
// Spielbretts direkt aus passenden Fragen gebildet und bleiben nicht leer.
// Einzelklassen ('7') und Bereiche ('7-8') werden vom Server erkannt.
const urlGrade = new URLSearchParams(location.search).get('grade') || '';
gradeFilterSelect.value = urlGrade;

function applyGradeFilter() {
  const grade = gradeFilterSelect.value;
  if (grade === urlGrade) return;
  const params = new URLSearchParams(location.search);
  if (grade) params.set('grade', grade); else params.delete('grade');
  const qs = params.toString();
  location.href = location.pathname + (qs ? '?' + qs : '');
}

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

function buildTeamScoreButtons(points) {
  if (!teams.length) {
    teamScoreButtons.innerHTML = '<em style="opacity:.6">Keine Teams konfiguriert.</em>';
    return;
  }
  teamScoreButtons.innerHTML = teams.map((t, i) =>
    `<button class="btn-team-score" type="button" onclick="awardPoints(${i}, ${points})">
      +${points} &rarr; ${escHtml(t.name)}
    </button>`
  ).join('');
}

window.awardPoints = (teamIdx, points) => {
  teams[teamIdx].score += points;
  lastChanged = teamIdx;
  saveTeams();
  renderScoreboard();
  closeModal();
};

function closeModal() {
  if (currentTile) {
    currentTile.disabled = true;
    currentTile.classList.add('done');
  }
  modal.classList.add('hidden');
  pointsSection.classList.add('hidden');
  modalAnswer.classList.add('hidden');
  showAnswerBtn.classList.remove('hidden');
  currentTile = null;
  currentPoints = 0;
  setModalOpen(!setupModal.classList.contains('hidden'));
}

closeBtn.addEventListener('click', closeModal);
noPointsBtn.addEventListener('click', closeModal);

modal.addEventListener('click', (e) => {
  if (e.target === modal) closeModal();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
});

showAnswerBtn.addEventListener('click', () => {
  modalAnswer.classList.remove('hidden');
  pointsSection.classList.remove('hidden');
  showAnswerBtn.classList.add('hidden');
  buildTeamScoreButtons(currentPoints);
});

// ===== TILE CLICKS =====
document.querySelectorAll('.question-tile').forEach(tile => {
  tile.addEventListener('click', async () => {
    if (currentTile || tile.disabled) return;
    currentTile = tile;
    try {
      const res = await fetch(`/api/question/${tile.dataset.questionId}`);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      currentPoints = data.points;
      modalQuestion.textContent = data.question_text;
      modalAnswer.textContent = data.answer_text;
      modalGradeBadge.textContent = data.grade_level ? `Klasse ${data.grade_level}` : '';
      modalAnswer.classList.add('hidden');
      pointsSection.classList.add('hidden');
      showAnswerBtn.classList.remove('hidden');
      modal.classList.remove('hidden');
      setModalOpen(true);
      showAnswerBtn.focus({ preventScroll: true });
    } catch (err) {
      currentTile = null;
      alert('Die Frage konnte nicht geladen werden. Bitte erneut versuchen.');
    }
  });
});

// ===== INIT =====
loadTeams();
buildNameInputs();
if (!teams.length) {
  setupModal.classList.remove('hidden');
  setModalOpen(true);
} else {
  setupModal.classList.add('hidden');
  renderScoreboard();
}
