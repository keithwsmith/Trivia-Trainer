// Trivia Trainer frontend. Vanilla JS, no build step, so it runs from a
// plain static file server on any platform's browser -- including iOS
// Safari, which is the whole point of shipping this as a web app.

const state = {
  currentSubject: null,
  queue: [],
  index: 0,
  correctCount: 0,
  answeredCurrent: false,
};

const el = (id) => document.getElementById(id);

// ---------------- View switching ----------------

function showView(id) {
  for (const v of document.querySelectorAll(".view")) {
    v.hidden = v.id !== id;
  }
}

// ---------------- Home view ----------------

async function loadHome() {
  showView("homeView");
  const subjects = await fetchJSON("/api/subjects");
  renderSubjectGrid(subjects);

  try {
    const weak = await fetchJSON("/api/weak-subjects?limit=5");
    renderFocusList(weak);
  } catch {
    // weak-subjects can be empty early on; not fatal
  }
}

function renderSubjectGrid(subjects) {
  const grid = el("subjectGrid");
  grid.innerHTML = "";

  if (subjects.length === 0) {
    grid.innerHTML = `<p class="page-sub">No subjects loaded yet. Open the admin panel (top right) to pull some in.</p>`;
    return;
  }

  for (const s of subjects) {
    const btn = document.createElement("button");
    btn.className = "subject-tile";
    btn.disabled = s.ClueCount === 0;
    btn.innerHTML = `
      <span class="subject-tile-name">${escapeHTML(s.SubjectName)}</span>
      <span class="subject-tile-count">${s.ClueCount} clue${s.ClueCount === 1 ? "" : "s"}</span>
    `;
    btn.addEventListener("click", () => startQuiz(s.SubjectName));
    grid.appendChild(btn);
  }
}

function renderFocusList(weak) {
  const section = el("focusSection");
  const list = el("focusList");
  list.innerHTML = "";

  if (!weak || weak.length === 0) {
    section.hidden = true;
    return;
  }

  section.hidden = false;
  for (const row of weak) {
    const pct = Math.round((row.Accuracy || 0) * 100);
    const li = document.createElement("li");
    li.className = "focus-row";
    li.innerHTML = `
      <span class="focus-name">${escapeHTML(row.SubjectName)}</span>
      <span class="focus-bar-track"><span class="focus-bar-fill" style="width:${pct}%"></span></span>
      <span class="focus-pct">${pct}%</span>
    `;
    list.appendChild(li);
  }
}

// ---------------- Quiz view ----------------

async function startQuiz(subjectName) {
  const clues = await fetchJSON(`/api/quiz?subject=${encodeURIComponent(subjectName)}&limit=10`);

  if (clues.length === 0) {
    showView("emptyView");
    return;
  }

  state.currentSubject = subjectName;
  state.queue = clues;
  state.index = 0;
  state.correctCount = 0;

  showView("quizView");
  renderCurrentClue();
}

function renderCurrentClue() {
  const clue = state.queue[state.index];
  state.answeredCurrent = false;

  el("quizProgress").textContent = `${state.index + 1} / ${state.queue.length}`;
  el("quizScore").textContent = `${state.correctCount} correct`;

  el("clueCategory").textContent = clue.category_name;
  el("clueDifficulty").textContent = clue.difficulty || "";
  el("clueText").textContent = clue.clue_text;

  const tile = el("clueTile");
  tile.classList.remove("is-correct", "is-incorrect");

  el("answerForm").hidden = false;
  el("answerInput").value = "";
  el("answerInput").disabled = false;
  el("revealPanel").hidden = true;

  el("answerInput").focus({ preventScroll: true });
}

async function submitAnswer(event) {
  event.preventDefault();
  if (state.answeredCurrent) return;

  const clue = state.queue[state.index];
  const userAnswer = el("answerInput").value;

  const result = await fetchJSON("/api/quiz/attempt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clue_id: clue.clue_id, user_answer: userAnswer }),
  });

  state.answeredCurrent = true;
  if (result.is_correct) state.correctCount += 1;

  const tile = el("clueTile");
  tile.classList.add(result.is_correct ? "is-correct" : "is-incorrect");

  el("answerInput").disabled = true;
  el("quizScore").textContent = `${state.correctCount} correct`;

  el("revealVerdict").textContent = result.is_correct ? "Correct" : "Missed";
  el("revealCorrect").textContent = result.correct_response;
  el("revealPanel").hidden = false;

  const isLast = state.index === state.queue.length - 1;
  el("nextButton").textContent = isLast ? "See results \u2192" : "Next clue \u2192";
}

function goToNext() {
  const isLast = state.index === state.queue.length - 1;
  if (isLast) {
    loadHome();
    return;
  }
  state.index += 1;
  renderCurrentClue();
}

// ---------------- Admin drawer ----------------

function toggleAdminDrawer() {
  const drawer = el("adminDrawer");
  drawer.hidden = !drawer.hidden;
}

function getAdminToken() {
  return el("adminToken").value || localStorage.getItem("adminToken") || "";
}

function setAdminStatus(message, isError = false) {
  const status = el("adminStatus");
  status.textContent = message;
  status.style.color = isError ? "var(--incorrect)" : "var(--muted)";
}

async function handlePull() {
  const token = getAdminToken();
  localStorage.setItem("adminToken", token);

  const subject = el("pullSubject").value.trim();
  const categoryIdRaw = el("pullCategoryId").value.trim();
  const count = parseInt(el("pullCount").value, 10) || 50;

  if (!subject) {
    setAdminStatus("Subject name is required.", true);
    return;
  }

  setAdminStatus("Pulling questions\u2026");
  try {
    const result = await fetchJSON("/api/admin/pull-opentdb", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Admin-Token": token },
      body: JSON.stringify({
        subject,
        category_id: categoryIdRaw ? parseInt(categoryIdRaw, 10) : null,
        count,
      }),
    });
    setAdminStatus(`Loaded ${result.loaded} questions.`);
    loadHome();
  } catch (err) {
    setAdminStatus(err.message, true);
  }
}

// ---------------- Helpers ----------------

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json();
}

function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------------- Wiring ----------------

el("adminToggle").addEventListener("click", toggleAdminDrawer);
el("backButton").addEventListener("click", loadHome);
el("emptyBackButton").addEventListener("click", loadHome);
el("answerForm").addEventListener("submit", submitAnswer);
el("nextButton").addEventListener("click", goToNext);
el("pullButton").addEventListener("click", handlePull);

const savedToken = localStorage.getItem("adminToken");
if (savedToken) el("adminToken").value = savedToken;

loadHome().catch((err) => {
  console.error(err);
});
