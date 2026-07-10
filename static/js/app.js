/**
 * app.js — EduSimpli Frontend Logic
 * IBM Watsonx.ai | Course Content Simplification Agent
 */

"use strict";

/* ═══════════════════════════════════════════════════════════
   STATE
═══════════════════════════════════════════════════════════ */
const State = {
  user:          null,
  documents:     [],
  currentView:   "dashboard",
  currentSession: null,
  currentDocId:  null,
  level:         "Beginner",
  quizData:      null,
  quizAnswers:   {},
  quizId:        null,
  darkMode:      false,
};

/* ═══════════════════════════════════════════════════════════
   API HELPERS
═══════════════════════════════════════════════════════════ */
async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  return res.json();
}

async function apiUpload(formData) {
  const res = await fetch("/api/documents/upload", {
    method: "POST",
    body: formData,
    credentials: "same-origin",
  });
  return res.json();
}

/* ═══════════════════════════════════════════════════════════
   TOAST NOTIFICATIONS
═══════════════════════════════════════════════════════════ */
function showToast(message, type = "primary") {
  const toast     = document.getElementById("appToast");
  const toastBody = document.getElementById("toastBody");
  toastBody.textContent = message;
  toast.className = `toast align-items-center text-bg-${type} border-0`;
  const bsToast = bootstrap.Toast.getOrCreateInstance(toast, { delay: 3500 });
  bsToast.show();
}

/* ═══════════════════════════════════════════════════════════
   MARKDOWN RENDERING
═══════════════════════════════════════════════════════════ */
function renderMarkdown(text) {
  if (!text) return "";
  if (typeof marked === "undefined") return escapeHtml(text).replace(/\n/g, "<br>");
  try {
    marked.setOptions({ breaks: true, gfm: true });
    return marked.parse(text);
  } catch { return escapeHtml(text); }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ═══════════════════════════════════════════════════════════
   VIEW NAVIGATION
═══════════════════════════════════════════════════════════ */
function navigateTo(viewName) {
  document.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
  const panel = document.getElementById(`view-${viewName}`);
  if (panel) panel.classList.add("active");

  document.querySelectorAll(".sidebar-link").forEach(l => {
    l.classList.toggle("active", l.dataset.view === viewName);
  });

  const titles = {
    dashboard:  "Dashboard",
    chat:       "AI Tutor Chat",
    upload:     "Upload Content",
    simplify:   "Content Simplification",
    quiz:       "Quiz Generator",
    flashcards: "Flashcards",
    glossary:   "Glossary",
    summary:    "Topic Summaries",
    documents:  "My Documents",
    bookmarks:  "Bookmarks",
    progress:   "Study Progress",
    profile:    "Student Profile",
  };
  document.getElementById("topbarTitle").textContent = titles[viewName] || viewName;
  State.currentView = viewName;

  // Close mobile sidebar
  document.getElementById("sidebar").classList.remove("open");

  // Load data for specific views
  if (viewName === "dashboard")  loadDashboard();
  if (viewName === "documents")  loadDocumentsView();
  if (viewName === "bookmarks")  loadBookmarks();
  if (viewName === "progress")   loadProgress();
  if (viewName === "chat")       loadChatSessions();
  if (viewName === "profile")    loadProfile();
}

/* ═══════════════════════════════════════════════════════════
   AUTH
═══════════════════════════════════════════════════════════ */
async function initAuth() {
  const data = await api("GET", "/api/auth/me").catch(() => null);
  if (data && data.success) {
    State.user = data.user;
    showApp();
  } else {
    showAuthPage();
  }
}

function showAuthPage() {
  document.getElementById("authPage").classList.remove("d-none");
  document.getElementById("mainApp").classList.add("d-none");
}

function showApp() {
  document.getElementById("authPage").classList.add("d-none");
  document.getElementById("mainApp").classList.remove("d-none");
  applyUserSettings();
  navigateTo("dashboard");
  loadDocuments();
}

function applyUserSettings() {
  if (!State.user) return;
  const u = State.user;
  State.level    = u.learning_level || "Beginner";
  State.darkMode = u.dark_mode || false;

  // Sync UI
  document.getElementById("sidebarUserName").textContent = u.username;
  document.getElementById("topbarAvatar").textContent    = (u.full_name || u.username)[0].toUpperCase();
  document.getElementById("topbarAvatar").style.background = u.avatar_color || "#3b82d4";
  document.getElementById("dashWelcomeName").textContent = u.full_name || u.username;
  document.getElementById("globalLevel").value           = State.level;
  document.getElementById("topbarLevel").textContent     = levelEmoji(State.level);
  if (State.darkMode) applyDarkMode(true);
}

function levelEmoji(level) {
  return { Beginner: "🌱 Beginner", Intermediate: "📚 Intermediate", Advanced: "🔬 Advanced", Expert: "🏆 Expert" }[level] || level;
}

/* Login */
document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("loginError");
  errEl.classList.add("d-none");
  const data = await api("POST", "/api/auth/login", {
    username: document.getElementById("loginUsername").value,
    password: document.getElementById("loginPassword").value,
  });
  if (data.success) {
    State.user = data.user;
    showApp();
  } else {
    errEl.textContent = data.error;
    errEl.classList.remove("d-none");
  }
});

/* Register */
document.getElementById("registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("registerError");
  errEl.classList.add("d-none");
  const data = await api("POST", "/api/auth/register", {
    full_name: document.getElementById("regFullName").value,
    username:  document.getElementById("regUsername").value,
    email:     document.getElementById("regEmail").value,
    password:  document.getElementById("regPassword").value,
  });
  if (data.success) {
    State.user = data.user;
    showApp();
  } else {
    errEl.textContent = data.error;
    errEl.classList.remove("d-none");
  }
});

/* Auth Tabs */
document.querySelectorAll("#authTabs .nav-link").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#authTabs .nav-link").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    document.getElementById("loginForm").classList.toggle("d-none",    tab !== "login");
    document.getElementById("registerForm").classList.toggle("d-none", tab !== "register");
  });
});

/* Logout */
document.getElementById("logoutBtn").addEventListener("click", async () => {
  await api("POST", "/api/auth/logout");
  State.user = null;
  showAuthPage();
});

/* ═══════════════════════════════════════════════════════════
   DOCUMENTS
═══════════════════════════════════════════════════════════ */
async function loadDocuments() {
  const data = await api("GET", "/api/documents");
  if (data.success) {
    State.documents = data.documents;
    populateDocSelects();
  }
}

function populateDocSelects() {
  const selects = [
    "chatDocSelect", "simplifyDocSelect", "quizDocSelect",
    "flashcardDocSelect", "glossaryDocSelect", "summaryDocSelect"
  ];
  selects.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const defaultOpt = el.options[0].outerHTML;
    el.innerHTML = defaultOpt;
    State.documents.forEach(doc => {
      const opt = document.createElement("option");
      opt.value       = doc.id;
      opt.textContent = doc.original_name;
      el.appendChild(opt);
    });
  });

  // Dashboard recent docs
  renderRecentDocs();
}

function renderRecentDocs() {
  const el = document.getElementById("recentDocsList");
  if (!State.documents.length) {
    el.innerHTML = '<p class="text-muted text-center py-3 small">No documents yet.</p>';
    return;
  }
  el.innerHTML = State.documents.slice(0, 6).map(doc => `
    <div class="doc-list-item" onclick="quickOpenDoc(${doc.id})">
      <span class="doc-list-icon">${docIcon(doc.file_type)}</span>
      <span class="doc-list-name">${escapeHtml(doc.original_name)}</span>
      <span class="doc-list-type">${doc.file_type.toUpperCase()}</span>
    </div>
  `).join("");
}

function docIcon(type) {
  return { pdf: "📄", docx: "📝", txt: "📋" }[type] || "📎";
}

function quickOpenDoc(docId) {
  document.getElementById("simplifyDocSelect").value = docId;
  navigateTo("simplify");
}

/* ── DOCUMENTS VIEW ─────────────────────────────────────── */
async function loadDocumentsView() {
  await loadDocuments();
  const grid = document.getElementById("documentsGrid");
  if (!State.documents.length) {
    grid.innerHTML = '<p class="text-muted text-center py-5">No documents uploaded yet.</p>';
    return;
  }
  grid.innerHTML = State.documents.map(doc => `
    <div class="doc-card">
      ${doc.is_processed ? '<span class="processed-badge">✓ Processed</span>' : ''}
      <span class="doc-card-icon">${docIcon(doc.file_type)}</span>
      <div class="doc-card-name" title="${escapeHtml(doc.original_name)}">${escapeHtml(doc.original_name)}</div>
      <div class="doc-card-meta">${doc.file_type.toUpperCase()} · ${formatBytes(doc.file_size)}</div>
      <div class="doc-card-actions">
        <button class="btn btn-sm btn-outline-primary" onclick="simplifyDoc(${doc.id})">✨ Simplify</button>
        <button class="btn btn-sm btn-outline-secondary" onclick="quizDoc(${doc.id})">🧪 Quiz</button>
        <button class="btn btn-sm btn-outline-secondary" onclick="bookmarkDoc(${doc.id})">🔖</button>
        <button class="btn btn-sm btn-outline-danger" onclick="deleteDoc(${doc.id})">🗑</button>
      </div>
    </div>
  `).join("");
}

function simplifyDoc(docId) {
  document.getElementById("simplifyDocSelect").value = docId;
  navigateTo("simplify");
}

function quizDoc(docId) {
  document.getElementById("quizDocSelect").value = docId;
  navigateTo("quiz");
}

async function deleteDoc(docId) {
  if (!confirm("Delete this document?")) return;
  const data = await api("DELETE", `/api/documents/${docId}`);
  if (data.success) {
    showToast("Document deleted.", "warning");
    loadDocumentsView();
  } else showToast(data.error, "danger");
}

async function bookmarkDoc(docId) {
  const data = await api("POST", "/api/bookmarks", { document_id: docId });
  showToast(data.success ? "Bookmarked! 🔖" : data.error, data.success ? "success" : "danger");
}

/* ── FILE UPLOAD ─────────────────────────────────────────── */
const dropzone  = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", ()  => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => { if (fileInput.files[0]) uploadFile(fileInput.files[0]); });

async function uploadFile(file) {
  const progress = document.getElementById("uploadProgress");
  const success  = document.getElementById("uploadSuccess");
  const successMsg = document.getElementById("uploadSuccessMsg");
  success.classList.add("d-none");
  progress.classList.remove("d-none");

  const fd = new FormData();
  fd.append("file", file);
  const data = await apiUpload(fd);
  progress.classList.add("d-none");

  if (data.success) {
    successMsg.textContent = `✅ "${file.name}" uploaded successfully!`;
    success.classList.remove("d-none");
    showToast("File uploaded! 🎉", "success");
    await loadDocuments();
  } else {
    showToast(data.error || "Upload failed.", "danger");
  }
}

/* ═══════════════════════════════════════════════════════════
   DASHBOARD
═══════════════════════════════════════════════════════════ */
async function loadDashboard() {
  const progData = await api("GET", "/api/progress");
  if (progData.success) {
    const s = progData.stats;
    document.getElementById("statDocs").textContent    = s.documents;
    document.getElementById("statQuizzes").textContent = s.quizzes_taken;
    document.getElementById("statScore").textContent   = s.avg_quiz_score + "%";
    document.getElementById("statLevel").textContent   = s.learning_level;
  }
  renderRecentDocs();
}

document.getElementById("loadSampleBtn").addEventListener("click", async () => {
  const data = await api("POST", "/api/sample/load");
  if (data.success) {
    showToast(`Loaded: ${data.loaded.join(", ")} 📚`, "success");
    await loadDocuments();
    loadDashboard();
  } else showToast(data.error, "danger");
});

document.getElementById("refreshRecsBtn").addEventListener("click", loadRecommendations);

async function loadRecommendations() {
  const el = document.getElementById("recommendationsList");
  el.innerHTML = '<div class="loading-state"><div class="spinner-dots"><span></span><span></span><span></span></div><p>Getting recommendations…</p></div>';
  const data = await api("GET", "/api/recommendations");
  el.innerHTML = data.success
    ? renderMarkdown(data.recommendations)
    : '<p class="text-muted">Could not load recommendations. Check your API keys.</p>';
}

/* ═══════════════════════════════════════════════════════════
   CHAT
═══════════════════════════════════════════════════════════ */
async function loadChatSessions() {
  const data = await api("GET", "/api/chat/sessions");
  if (!data.success) return;
  const list = document.getElementById("sessionsList");
  list.innerHTML = data.sessions.map(s => `
    <div class="session-item ${s.id === State.currentSession ? 'active' : ''}"
         onclick="loadSession(${s.id})" title="${escapeHtml(s.title)}">
      <i class="bi bi-chat-dots me-1"></i>${escapeHtml(s.title.slice(0, 28))}
    </div>
  `).join("") || '<p class="text-muted small text-center">No sessions yet.</p>';
}

async function loadSession(sessionId) {
  State.currentSession = sessionId;
  loadChatSessions();
  const data = await api("GET", `/api/chat/sessions/${sessionId}/messages`);
  if (!data.success) return;
  const messagesEl = document.getElementById("chatMessages");
  messagesEl.innerHTML = "";
  if (!data.messages.length) {
    appendWelcome();
  } else {
    data.messages.forEach(m => appendBubble(m.role, m.content));
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

document.getElementById("newChatBtn").addEventListener("click", async () => {
  const docId = document.getElementById("chatDocSelect").value || null;
  const data  = await api("POST", "/api/chat/sessions", {
    document_id: docId ? parseInt(docId) : null,
    title: "New Chat",
  });
  if (data.success) {
    State.currentSession = data.session_id;
    loadChatSessions();
    document.getElementById("chatMessages").innerHTML = "";
    appendWelcome();
  }
});

document.getElementById("chatSendBtn").addEventListener("click", sendChatMessage);
document.getElementById("chatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
});

document.querySelectorAll(".chat-hint").forEach(hint => {
  hint.addEventListener("click", () => {
    document.getElementById("chatInput").value = hint.dataset.text;
    document.getElementById("chatInput").focus();
  });
});

async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const msg   = input.value.trim();
  if (!msg) return;

  // Ensure session exists
  if (!State.currentSession) {
    const docId = document.getElementById("chatDocSelect").value || null;
    const s = await api("POST", "/api/chat/sessions", {
      document_id: docId ? parseInt(docId) : null,
      title: msg.slice(0, 60),
    });
    if (!s.success) { showToast("Could not create session.", "danger"); return; }
    State.currentSession = s.session_id;
    loadChatSessions();
    document.getElementById("chatMessages").innerHTML = "";
  }

  input.value = "";
  appendBubble("user", msg);
  const typingId = appendTyping();

  const data = await api("POST", "/api/chat/send", {
    session_id: State.currentSession,
    message: msg,
    level: State.level,
  });

  removeTyping(typingId);
  appendBubble("assistant", data.success ? data.reply : "⚠️ " + (data.error || "Error"));
}

function appendWelcome() {
  document.getElementById("chatMessages").innerHTML = `
    <div class="chat-welcome">
      <div class="chat-welcome-icon">🤖</div>
      <h4>Hi! I'm EduSimpli</h4>
      <p>Upload a document and ask me anything! I can explain concepts, answer questions, and simplify complex material based on your learning level.</p>
    </div>`;
}

function appendBubble(role, content) {
  const messagesEl = document.getElementById("chatMessages");
  // Remove welcome if present
  messagesEl.querySelector(".chat-welcome")?.remove();

  const div = document.createElement("div");
  div.className = `chat-bubble ${role}`;
  const initials = role === "user"
    ? (State.user?.full_name || State.user?.username || "S")[0].toUpperCase()
    : "🤖";
  const avatarClass = role === "user" ? "user-av" : "ai-av";
  const contentHtml = role === "assistant" ? renderMarkdown(content) : escapeHtml(content);

  div.innerHTML = `
    <div class="bubble-avatar ${avatarClass}">${initials}</div>
    <div class="bubble-content">${contentHtml}</div>
  `;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function appendTyping() {
  const messagesEl = document.getElementById("chatMessages");
  const id = "typing_" + Date.now();
  const div = document.createElement("div");
  div.className = "chat-bubble assistant typing-indicator";
  div.id = id;
  div.innerHTML = `
    <div class="bubble-avatar ai-av">🤖</div>
    <div class="bubble-content">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>`;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return id;
}

function removeTyping(id) {
  document.getElementById(id)?.remove();
}

/* ═══════════════════════════════════════════════════════════
   SIMPLIFY
═══════════════════════════════════════════════════════════ */
document.querySelectorAll("#simplifyLevel .level-pill").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#simplifyLevel .level-pill").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
  });
});

document.getElementById("simplifyBtn").addEventListener("click", async () => {
  const docId  = document.getElementById("simplifyDocSelect").value;
  const text   = document.getElementById("simplifyText").value.trim();
  const topic  = document.getElementById("simplifyTopic").value.trim();
  const level  = document.querySelector("#simplifyLevel .level-pill.active")?.dataset.level || State.level;
  const result = document.getElementById("simplifyResult");
  const loading = document.getElementById("simplifyLoading");

  if (!docId && !text) { showToast("Please select a document or paste content.", "warning"); return; }

  result.innerHTML = "";
  result.classList.add("d-none");
  loading.classList.remove("d-none");

  const payload = { level, topic };
  if (docId) payload.document_id = parseInt(docId);
  else       payload.text = text;

  const data = await api("POST", "/api/simplify", payload);
  loading.classList.add("d-none");
  result.classList.remove("d-none");

  if (data.success) {
    result.innerHTML = renderMarkdown(data.result);
    showToast("Content simplified! ✨", "success");
  } else {
    result.innerHTML = `<div class="alert alert-danger">${escapeHtml(data.error)}</div>`;
  }
});

document.getElementById("copySimplifyBtn").addEventListener("click", () => {
  const text = document.getElementById("simplifyResult").innerText;
  navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard! 📋", "success"));
});

/* ═══════════════════════════════════════════════════════════
   QUIZ
═══════════════════════════════════════════════════════════ */
document.getElementById("generateQuizBtn").addEventListener("click", async () => {
  const docId = document.getElementById("quizDocSelect").value;
  if (!docId) { showToast("Please select a document.", "warning"); return; }

  const level  = document.getElementById("quizLevel").value;
  const nQ     = parseInt(document.getElementById("quizNumQuestions").value);
  const loading = document.getElementById("quizLoading");
  const container = document.getElementById("quizContainer");
  const resultEl  = document.getElementById("quizResult");

  container.classList.add("d-none");
  resultEl.classList.add("d-none");
  loading.classList.remove("d-none");
  State.quizAnswers = {};

  const data = await api("POST", "/api/quiz/generate", {
    document_id: parseInt(docId),
    level, num_questions: nQ,
  });
  loading.classList.add("d-none");

  if (!data.success) { showToast(data.error, "danger"); return; }

  State.quizData = data.questions;
  State.quizId   = data.quiz_id;
  renderQuiz(data.questions);
  container.classList.remove("d-none");
});

function renderQuiz(questions) {
  const container = document.getElementById("quizContainer");
  container.innerHTML = questions.map((q, i) => `
    <div class="quiz-question-card" id="qcard_${i}">
      <div class="quiz-q-num">Question ${i + 1} of ${questions.length}</div>
      <div class="quiz-q-text">${escapeHtml(q.question)}</div>
      ${q.options.map(opt => `
        <div class="quiz-option" data-q="${i}" data-val="${opt[0]}" onclick="selectAnswer(${i}, '${opt[0]}')">
          ${escapeHtml(opt)}
        </div>
      `).join("")}
      <div class="quiz-explanation" id="exp_${i}">💡 ${escapeHtml(q.explanation || "")}</div>
    </div>
  `).join("") + `
    <button class="btn btn-primary mt-2" onclick="submitQuiz()">
      <i class="bi bi-check2-circle me-2"></i>Submit Answers
    </button>`;
}

function selectAnswer(qIdx, value) {
  document.querySelectorAll(`.quiz-option[data-q="${qIdx}"]`)
    .forEach(o => o.classList.remove("selected"));
  const chosen = document.querySelector(`.quiz-option[data-q="${qIdx}"][data-val="${value}"]`);
  if (chosen) chosen.classList.add("selected");
  State.quizAnswers[qIdx] = value;
}

async function submitQuiz() {
  if (!State.quizId) return;
  const data = await api("POST", `/api/quiz/${State.quizId}/submit`, { answers: State.quizAnswers });
  if (!data.success) { showToast(data.error, "danger"); return; }

  // Show correct/wrong highlighting
  State.quizData.forEach((q, i) => {
    const correct = q.answer;
    document.querySelectorAll(`.quiz-option[data-q="${i}"]`).forEach(opt => {
      if (opt.dataset.val === correct)        opt.classList.add("correct");
      else if (State.quizAnswers[i] === opt.dataset.val) opt.classList.add("wrong");
    });
    document.getElementById(`exp_${i}`)?.classList.add("show");
  });

  // Show score
  const score = data.score;
  document.getElementById("scorePercent").textContent = Math.round(score) + "%";
  document.getElementById("scoreMessage").textContent =
    score >= 80 ? "🏆 Excellent work!" :
    score >= 60 ? "📚 Good effort! Review the highlighted answers." :
    "🌱 Keep studying — you'll get there!";
  document.getElementById("quizResult").classList.remove("d-none");
  document.getElementById("quizResult").scrollIntoView({ behavior: "smooth" });
  showToast(`Quiz scored: ${Math.round(score)}% 🎯`, score >= 60 ? "success" : "warning");
}

document.getElementById("retakeQuizBtn").addEventListener("click", () => {
  document.getElementById("quizResult").classList.add("d-none");
  document.getElementById("quizContainer").classList.add("d-none");
  document.getElementById("quizContainer").innerHTML = "";
  State.quizAnswers = {};
  State.quizData    = null;
  State.quizId      = null;
});

/* ═══════════════════════════════════════════════════════════
   FLASHCARDS
═══════════════════════════════════════════════════════════ */
document.getElementById("generateFlashcardsBtn").addEventListener("click", async () => {
  const docId = document.getElementById("flashcardDocSelect").value;
  if (!docId) { showToast("Please select a document.", "warning"); return; }

  const loading = document.getElementById("flashcardsLoading");
  const grid    = document.getElementById("flashcardsGrid");
  loading.classList.remove("d-none");
  grid.innerHTML = "";

  const data = await api("POST", "/api/flashcards/generate", {
    document_id: parseInt(docId),
    level: State.level,
  });
  loading.classList.add("d-none");

  if (!data.success) { showToast(data.error, "danger"); return; }

  if (!data.flashcards.length) {
    grid.innerHTML = '<p class="text-muted">No flashcards generated.</p>';
    return;
  }
  grid.innerHTML = data.flashcards.map(card => `
    <div class="flashcard" title="Hover to flip">
      <div class="flashcard-inner">
        <div class="flashcard-front">
          <span class="flashcard-term">${escapeHtml(card.term)}</span>
          <span>Hover to reveal definition</span>
        </div>
        <div class="flashcard-back">
          <p class="flashcard-definition">${escapeHtml(card.definition)}</p>
          ${card.example ? `<p class="flashcard-example">📌 ${escapeHtml(card.example)}</p>` : ""}
        </div>
      </div>
    </div>
  `).join("");
  showToast(`Generated ${data.flashcards.length} flashcards! 🃏`, "success");
});

/* ═══════════════════════════════════════════════════════════
   GLOSSARY
═══════════════════════════════════════════════════════════ */
document.getElementById("generateGlossaryBtn").addEventListener("click", async () => {
  const docId = document.getElementById("glossaryDocSelect").value;
  if (!docId) { showToast("Please select a document.", "warning"); return; }

  const loading   = document.getElementById("glossaryLoading");
  const container = document.getElementById("glossaryContainer");
  loading.classList.remove("d-none");
  container.innerHTML = "";

  const data = await api("POST", "/api/glossary/generate", {
    document_id: parseInt(docId),
    level: State.level,
  });
  loading.classList.add("d-none");

  if (!data.success) { showToast(data.error, "danger"); return; }

  const entries = Object.entries(data.glossary);
  if (!entries.length) { container.innerHTML = '<p class="text-muted">No terms found.</p>'; return; }

  container.innerHTML = entries.map(([term, def]) => `
    <div class="glossary-term-card">
      <div class="glossary-term">📌 ${escapeHtml(term)}</div>
      <div class="glossary-def">${escapeHtml(String(def))}</div>
    </div>
  `).join("");
  showToast(`Generated ${entries.length} glossary terms! 📖`, "success");
});

/* ═══════════════════════════════════════════════════════════
   SUMMARY
═══════════════════════════════════════════════════════════ */
document.getElementById("generateSummaryBtn").addEventListener("click", async () => {
  const docId = document.getElementById("summaryDocSelect").value;
  if (!docId) { showToast("Please select a document.", "warning"); return; }

  const loading = document.getElementById("summaryLoading");
  const result  = document.getElementById("summaryResult");
  loading.classList.remove("d-none");

  const data = await api("POST", "/api/summary/generate", {
    document_id: parseInt(docId),
    level: State.level,
  });
  loading.classList.add("d-none");

  if (data.success) {
    result.innerHTML = renderMarkdown(data.summary);
    showToast("Summary generated! 📋", "success");
  } else {
    result.innerHTML = `<div class="alert alert-danger">${escapeHtml(data.error)}</div>`;
  }
});

/* ═══════════════════════════════════════════════════════════
   BOOKMARKS
═══════════════════════════════════════════════════════════ */
async function loadBookmarks() {
  const data = await api("GET", "/api/bookmarks");
  const list = document.getElementById("bookmarksList");
  if (!data.success || !data.bookmarks.length) {
    list.innerHTML = '<p class="text-muted text-center py-5">No bookmarks yet.</p>';
    return;
  }
  list.innerHTML = data.bookmarks.map(b => `
    <div class="doc-card">
      <span class="doc-card-icon">🔖</span>
      <div class="doc-card-name">${escapeHtml(b.document_name)}</div>
      <div class="doc-card-meta">${new Date(b.created_at).toLocaleDateString()}</div>
      ${b.note ? `<p class="small text-muted mt-1">${escapeHtml(b.note)}</p>` : ""}
      <div class="doc-card-actions">
        <button class="btn btn-sm btn-outline-primary" onclick="simplifyDoc(${b.document_id})">✨ Open</button>
        <button class="btn btn-sm btn-outline-danger" onclick="removeBookmark(${b.id})">Remove</button>
      </div>
    </div>
  `).join("");
}

async function removeBookmark(bmId) {
  const data = await api("DELETE", `/api/bookmarks/${bmId}`);
  if (data.success) { showToast("Bookmark removed.", "warning"); loadBookmarks(); }
  else showToast(data.error, "danger");
}

/* ═══════════════════════════════════════════════════════════
   PROGRESS
═══════════════════════════════════════════════════════════ */
async function loadProgress() {
  const data = await api("GET", "/api/progress");
  if (!data.success) return;

  const statsEl = document.getElementById("progressStats");
  const s = data.stats;
  statsEl.innerHTML = `
    <div class="col-6 col-lg-3">
      <div class="stat-card" style="--accent:#3b82d4">
        <div class="stat-icon"><i class="bi bi-file-earmark-richtext-fill"></i></div>
        <div class="stat-value">${s.documents}</div>
        <div class="stat-label">Documents</div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="stat-card" style="--accent:#7c5cd8">
        <div class="stat-icon"><i class="bi bi-patch-check-fill"></i></div>
        <div class="stat-value">${s.quizzes_taken}</div>
        <div class="stat-label">Quizzes Taken</div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="stat-card" style="--accent:#16a34a">
        <div class="stat-icon"><i class="bi bi-graph-up"></i></div>
        <div class="stat-value">${s.avg_quiz_score}%</div>
        <div class="stat-label">Avg Score</div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="stat-card" style="--accent:#ea580c">
        <div class="stat-icon"><i class="bi bi-mortarboard-fill"></i></div>
        <div class="stat-value">${s.learning_level}</div>
        <div class="stat-label">Level</div>
      </div>
    </div>`;

  const listEl = document.getElementById("progressList");
  if (!data.progress.length) {
    listEl.innerHTML = '<p class="text-muted text-center py-4">No progress tracked yet. Simplify a document to start!</p>';
    return;
  }
  listEl.innerHTML = data.progress.map(p => `
    <div class="progress-topic-row">
      <span class="progress-topic-name">${escapeHtml(p.topic)}</span>
      <div class="progress-bar-wrap">
        <div class="progress" style="height:8px">
          <div class="progress-bar" style="width:${p.percent_done}%"></div>
        </div>
      </div>
      <span class="progress-pct">${Math.round(p.percent_done)}%</span>
    </div>
  `).join("");
}

/* ═══════════════════════════════════════════════════════════
   PROFILE
═══════════════════════════════════════════════════════════ */
function loadProfile() {
  if (!State.user) return;
  const u = State.user;
  document.getElementById("profileFullName").textContent    = u.full_name || u.username;
  document.getElementById("profileUsername").textContent    = "@" + u.username;
  document.getElementById("profileLevelBadge").textContent  = levelEmoji(u.learning_level);
  document.getElementById("profileAvatarLarge").textContent = (u.full_name || u.username)[0].toUpperCase();
  document.getElementById("profileAvatarLarge").style.background = u.avatar_color || "#3b82d4";
  document.getElementById("profileFullNameInput").value = u.full_name || "";
  document.getElementById("profileEmailInput").value    = u.email || "";
  document.getElementById("profileLevelSelect").value   = u.learning_level || "Beginner";
  document.getElementById("profileDomainSelect").value  = u.preferred_domain || "General Education";
  document.getElementById("profileDarkMode").checked    = u.dark_mode || false;
  document.getElementById("avatarColorPicker").value    = u.avatar_color || "#3b82d4";
}

document.getElementById("profileForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = await api("PUT", "/api/profile", {
    full_name:        document.getElementById("profileFullNameInput").value,
    learning_level:   document.getElementById("profileLevelSelect").value,
    preferred_domain: document.getElementById("profileDomainSelect").value,
    dark_mode:        document.getElementById("profileDarkMode").checked,
    avatar_color:     document.getElementById("avatarColorPicker").value,
  });
  if (data.success) {
    State.user = data.user;
    applyUserSettings();
    loadProfile();
    showToast("Profile saved! ✅", "success");
  } else showToast(data.error, "danger");
});

/* ═══════════════════════════════════════════════════════════
   GLOBAL LEVEL SELECTOR
═══════════════════════════════════════════════════════════ */
document.getElementById("globalLevel").addEventListener("change", async (e) => {
  State.level = e.target.value;
  document.getElementById("topbarLevel").textContent = levelEmoji(State.level);
  if (State.user) {
    await api("PUT", "/api/profile", { learning_level: State.level });
    State.user.learning_level = State.level;
  }
  // Sync quiz/simplify level selects
  const ql = document.getElementById("quizLevel");
  if (ql) ql.value = State.level;
});

/* ═══════════════════════════════════════════════════════════
   DARK MODE
═══════════════════════════════════════════════════════════ */
function applyDarkMode(dark) {
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  const icon = document.getElementById("darkModeToggle").querySelector("i");
  if (icon) { icon.className = dark ? "bi bi-sun-fill" : "bi bi-moon-stars-fill"; }
  State.darkMode = dark;
}

document.getElementById("darkModeToggle").addEventListener("click", () => {
  applyDarkMode(!State.darkMode);
  if (State.user) {
    api("PUT", "/api/profile", { dark_mode: State.darkMode });
    State.user.dark_mode = State.darkMode;
  }
});

/* ═══════════════════════════════════════════════════════════
   SIDEBAR TOGGLE (Mobile)
═══════════════════════════════════════════════════════════ */
document.getElementById("sidebarToggle").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});
document.getElementById("sidebarClose").addEventListener("click", () => {
  document.getElementById("sidebar").classList.remove("open");
});

/* ═══════════════════════════════════════════════════════════
   DELEGATE: sidebar links + quick cards
═══════════════════════════════════════════════════════════ */
document.addEventListener("click", (e) => {
  const link = e.target.closest("[data-view]");
  if (link) {
    e.preventDefault();
    navigateTo(link.dataset.view);
  }
});

/* ═══════════════════════════════════════════════════════════
   UTILITIES
═══════════════════════════════════════════════════════════ */
function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const k = 1024, sizes = ["B", "KB", "MB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + " " + sizes[i];
}

/* ═══════════════════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════════════════ */
document.addEventListener("DOMContentLoaded", initAuth);
