// Technik-Jeopardy – Praesentations-/Beamermodus
let teams = [];
let currentPoints = 0;
let currentTile = null;
let lastChanged = -1;

const scoreboard = document.getElementById('scoreboard');
const modal = document.getElementById('question-modal');
const modalQuestion = document.getElementById('modal-question');
const modalAnswer = document.getElementById('modal-answer');
const modalPoints = document.getElementById('modal-points');
const showAnswerBtn = document.getElementById('show-answer');
const closeBtn = document.getElementById('close-modal');
const noPointsBtn = document.getElementById('no-points-btn');
const teamScoreButtons = document.getElementById('team-score-buttons');
const pointsSection = document.getElementById('points-section');
const fullscreenBtn = document.getElementById('fullscreen-btn');

function escHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function loadTeams() {
  try {
    const saved = localStorage.getItem('jeopardy_teams');
    if (saved) teams = JSON.parse(saved);
  } catch (e) {
    teams = [];
  }
  if (!Array.isArray(teams) || !teams.length) {
    teams = [{ name: 'Team 1', score: 0 }, { name: 'Team 2', score: 0 }];
    saveTeams();
  }
}

function saveTeams() {
  localStorage.setItem('jeopardy_teams', JSON.stringify(teams));
}

function renderScoreboard() {
  const max = Math.max(...teams.map(t => t.score));
  const hasLeader = max > 0 && teams.filter(t => t.score === max).length === 1;

  scoreboard.innerHTML = teams.map((team, index) => `
    <div class="team-card${hasLeader && team.score === max ? ' leader' : ''}">
      <span class="team-name">${escHtml(team.name)}</span>
      <span class="team-score${index === lastChanged ? ' bump' : ''}">${team.score}</span>
      <div class="score-btns">
        <button class="score-adj" type="button" data-team="${index}" data-delta="-100">&minus;100</button>
        <button class="score-adj" type="button" data-team="${index}" data-delta="100">+100</button>
      </div>
    </div>
  `).join('');

  lastChanged = -1;
}

scoreboard.addEventListener('click', (event) => {
  const button = event.target.closest('.score-adj');
  if (!button) return;
  const index = Number(button.dataset.team);
  const delta = Number(button.dataset.delta);
  if (!teams[index]) return;
  teams[index].score += delta;
  lastChanged = index;
  saveTeams();
  renderScoreboard();
});

function buildTeamScoreButtons(points) {
  teamScoreButtons.innerHTML = teams.map((team, index) => `
    <button class="btn-team-score" type="button" data-team="${index}" data-points="${points}">
      +${points} &rarr; ${escHtml(team.name)}
    </button>
  `).join('');
}

teamScoreButtons.addEventListener('click', (event) => {
  const button = event.target.closest('.btn-team-score');
  if (!button) return;
  const index = Number(button.dataset.team);
  const points = Number(button.dataset.points);
  if (!teams[index]) return;
  teams[index].score += points;
  lastChanged = index;
  saveTeams();
  renderScoreboard();
  closeModal();
});

function closeModal() {
  if (currentTile) {
    currentTile.disabled = true;
  }
  modal.classList.add('hidden');
  pointsSection.classList.add('hidden');
  modalAnswer.classList.add('hidden');
  showAnswerBtn.classList.remove('hidden');
  currentTile = null;
  currentPoints = 0;
}

closeBtn.addEventListener('click', closeModal);
noPointsBtn.addEventListener('click', closeModal);

modal.addEventListener('click', (event) => {
  if (event.target === modal) closeModal();
});

showAnswerBtn.addEventListener('click', () => {
  modalAnswer.classList.remove('hidden');
  pointsSection.classList.remove('hidden');
  showAnswerBtn.classList.add('hidden');
  buildTeamScoreButtons(currentPoints);
});

document.querySelectorAll('.present-tile').forEach((tile) => {
  tile.addEventListener('click', async () => {
    if (currentTile || tile.disabled) return;
    currentTile = tile;

    try {
      const response = await fetch(`/api/question/${tile.dataset.questionId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      currentPoints = data.points;
      modalQuestion.textContent = data.question_text;
      modalAnswer.textContent = data.answer_text;
      modalPoints.textContent = `${data.points} Punkte`;
      modalAnswer.classList.add('hidden');
      pointsSection.classList.add('hidden');
      showAnswerBtn.classList.remove('hidden');
      modal.classList.remove('hidden');
      showAnswerBtn.focus({ preventScroll: true });
    } catch (error) {
      currentTile = null;
      alert('Die Frage konnte nicht geladen werden. Bitte erneut versuchen.');
    }
  });
});

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

fullscreenBtn.addEventListener('click', toggleFullscreen);

document.addEventListener('keydown', (event) => {
  if (event.key.toLowerCase() === 'f' && !event.ctrlKey && !event.metaKey && !event.altKey) {
    toggleFullscreen();
  }
  if (event.key === 'Escape' && !modal.classList.contains('hidden')) {
    closeModal();
  }
});

loadTeams();
renderScoreboard();
