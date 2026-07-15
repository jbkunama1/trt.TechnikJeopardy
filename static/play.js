document.addEventListener("DOMContentLoaded", () => {
  const tiles = document.querySelectorAll(".question-tile");
  const modal = document.getElementById("question-modal");
  const modalQuestion = document.getElementById("modal-question");
  const modalAnswer = document.getElementById("modal-answer");
  const showAnswerBtn = document.getElementById("show-answer");
  const closeBtn = document.getElementById("close-modal");

  tiles.forEach((tile) => {
    tile.addEventListener("click", async () => {
      const id = tile.dataset.questionId;
      const res = await fetch(`/api/question/${id}`);
      if (!res.ok) return;
      const data = await res.json();
      modalQuestion.textContent = data.question_text;
      modalAnswer.textContent = data.answer_text;
      modalAnswer.classList.add("hidden");
      modal.classList.remove("hidden");
    });
  });

  showAnswerBtn.addEventListener("click", () => {
    modalAnswer.classList.remove("hidden");
  });

  closeBtn.addEventListener("click", () => {
    modal.classList.add("hidden");
    tiles.forEach((t) => {
      if (t.dataset.questionId === modal.dataset.currentId) {
        t.disabled = true;
        t.style.opacity = "0.3";
      }
    });
  });
});
