// ============================
// Smart Study Cards - Popup JS
// ============================

const API = {
  baseUrl: "http://localhost:8501",

  async init() {
    const stored = await chrome.storage.sync.get(["serverUrl"]);
    if (stored.serverUrl) {
      this.baseUrl = stored.serverUrl.replace(/\/$/, "");
    }
  },

  getApiUrl() {
    // The API runs on a separate port (base + 1)
    const url = new URL(this.baseUrl);
    const port = parseInt(url.port || "8501", 10);
    url.port = String(port + 1);
    url.pathname = "/api";
    return url.toString();
  },

  async request(endpoint, options = {}) {
    const apiUrl = this.getApiUrl();
    const url = `${apiUrl}${endpoint}`;

    const resp = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`API error ${resp.status}: ${text}`);
    }

    return resp.json();
  },

  getDecks() {
    return this.request("/decks");
  },

  getDueCards(deckId = null, maxCards = 10) {
    const params = new URLSearchParams({ max_cards: maxCards });
    if (deckId) params.set("deck_id", deckId);
    return this.request(`/cards/due?${params}`);
  },

  submitAnswer(cardId, result) {
    return this.request(`/cards/${cardId}/answer`, {
      method: "POST",
      body: JSON.stringify({ result }),
    });
  },

  createCard(data) {
    return this.request("/cards", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  createDeck(data) {
    return this.request("/decks", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getStats() {
    return this.request("/stats");
  },

  async checkConnection() {
    try {
      await this.request("/health");
      return true;
    } catch {
      return false;
    }
  },
};

// State
let state = {
  connected: false,
  decks: [],
  currentCards: [],
  currentCardIndex: 0,
  studyDeckId: null,
  totalStudied: 0,
  totalCorrect: 0,
};

// ---- DOM References ----
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ---- Initialization ----
document.addEventListener("DOMContentLoaded", async () => {
  await API.init();
  setupTabs();
  setupEventListeners();
  await checkConnection();

  // Check for pending card from context menu / content script
  const pending = await chrome.storage.local.get(["pendingCard"]);
  if (pending.pendingCard) {
    switchTab("create");
    const card = pending.pendingCard;
    if (card.question) $("#create-question").value = card.question;
    if (card.answer) $("#create-answer").value = card.answer;
    await chrome.storage.local.remove(["pendingCard"]);
  }
});

function setupTabs() {
  $$(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      switchTab(tab.dataset.tab);
    });
  });
}

function switchTab(tabName) {
  $$(".tab").forEach((t) => t.classList.remove("active"));
  $$(".tab-content").forEach((c) => c.classList.add("hidden"));
  $(`.tab[data-tab="${tabName}"]`).classList.add("active");
  $(`#tab-${tabName}`).classList.remove("hidden");
}

function setupEventListeners() {
  $("#btn-check-answer").addEventListener("click", checkFreeTextAnswer);
  $("#btn-correct").addEventListener("click", () => submitResult("correct"));
  $("#btn-hard").addEventListener("click", () => submitResult("hard"));
  $("#btn-wrong").addEventListener("click", () => submitResult("wrong"));
  $("#btn-create-card").addEventListener("click", createCard);
  $("#btn-create-deck").addEventListener("click", createDeck);

  $("#btn-open-app").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: API.baseUrl });
  });

  $("#btn-settings").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });

  // Enter key on answer input
  $("#answer-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      checkFreeTextAnswer();
    }
  });
}

// ---- Connection ----
async function checkConnection() {
  updateConnectionStatus("checking");

  const connected = await API.checkConnection();
  state.connected = connected;

  if (connected) {
    updateConnectionStatus("connected");
    await loadData();
  } else {
    updateConnectionStatus("disconnected");
  }
}

function updateConnectionStatus(status) {
  const bar = $("#connection-status");
  const text = $("#status-text");

  bar.className = "status-bar";

  switch (status) {
    case "connected":
      bar.classList.add("status-connected");
      text.textContent = "Verbunden mit Smart Study Cards";
      break;
    case "disconnected":
      bar.classList.add("status-disconnected");
      text.textContent = "Nicht verbunden — App starten";
      break;
    case "checking":
      bar.classList.add("status-checking");
      text.textContent = "Verbindung wird geprüft...";
      break;
  }
}

// ---- Data Loading ----
async function loadData() {
  try {
    const [decks, stats] = await Promise.all([API.getDecks(), API.getStats()]);

    state.decks = decks;
    renderDecks();
    populateDeckSelect();

    if (stats) {
      $("#xp-badge").textContent = `${stats.total_xp || 0} XP`;
      $("#streak-badge").textContent = `🔥 ${stats.current_streak || 0}`;
    }

    // Auto-load due cards
    await loadDueCards();
  } catch (err) {
    console.error("Failed to load data:", err);
  }
}

async function loadDueCards(deckId = null) {
  try {
    const cards = await API.getDueCards(deckId, 10);
    state.currentCards = cards;
    state.currentCardIndex = 0;
    state.studyDeckId = deckId;
    state.totalStudied = 0;
    state.totalCorrect = 0;

    if (cards.length > 0) {
      showCard(cards[0]);
      updateProgress();
    } else {
      showEmptyState();
    }
  } catch (err) {
    console.error("Failed to load cards:", err);
    showEmptyState();
  }
}

// ---- Study Card Rendering ----
function showCard(card) {
  $("#study-empty").classList.add("hidden");
  $("#study-card").classList.remove("hidden");
  $("#study-progress").classList.remove("hidden");

  $("#card-subject").textContent = card.subject || "Allgemein";
  $("#card-box").textContent = `Box ${card.box || 1}`;
  $("#card-question").textContent = card.question;

  // Reset answer areas
  $("#answer-reveal").classList.add("hidden");
  $("#answer-input-area").classList.add("hidden");
  $("#mc-choices").classList.add("hidden");
  $("#answer-input").value = "";

  if (card.choices && card.choices.length > 0) {
    renderMultipleChoice(card);
  } else {
    $("#answer-input-area").classList.remove("hidden");
    $("#answer-input").focus();
  }
}

function renderMultipleChoice(card) {
  const container = $("#mc-choices");
  container.innerHTML = "";
  container.classList.remove("hidden");

  card.choices.forEach((choice, i) => {
    const btn = document.createElement("button");
    btn.className = "mc-choice";
    btn.textContent = choice;
    btn.addEventListener("click", () => selectMcChoice(btn, i, card));
    container.appendChild(btn);
  });
}

function selectMcChoice(btn, index, card) {
  // Disable further clicks
  $$(".mc-choice").forEach((b) => (b.style.pointerEvents = "none"));

  const correctIndex = card.correct_choice_index;

  if (index === correctIndex) {
    btn.classList.add("correct");
  } else {
    btn.classList.add("wrong");
    $$(".mc-choice")[correctIndex]?.classList.add("correct");
  }

  // Show answer after brief delay
  setTimeout(() => {
    revealAnswer(card, index === correctIndex);
  }, 600);
}

function checkFreeTextAnswer() {
  const card = state.currentCards[state.currentCardIndex];
  if (!card) return;
  revealAnswer(card, null);
}

function revealAnswer(card, autoResult) {
  $("#answer-input-area").classList.add("hidden");
  $("#answer-reveal").classList.remove("hidden");
  $("#card-answer").textContent = card.answer;
  $("#card-explanation").textContent = card.explanation || "";

  if (autoResult === true) {
    // Auto-mark correct for MC
    setTimeout(() => submitResult("correct"), 300);
  }
}

async function submitResult(result) {
  const card = state.currentCards[state.currentCardIndex];
  if (!card) return;

  state.totalStudied++;
  if (result === "correct") state.totalCorrect++;

  try {
    await API.submitAnswer(card.id, result);
  } catch (err) {
    console.error("Failed to submit answer:", err);
  }

  // Next card
  state.currentCardIndex++;
  updateProgress();

  if (state.currentCardIndex < state.currentCards.length) {
    showCard(state.currentCards[state.currentCardIndex]);
  } else {
    showSessionComplete();
  }
}

function showEmptyState() {
  $("#study-empty").classList.remove("hidden");
  $("#study-card").classList.add("hidden");
  $("#study-progress").classList.add("hidden");
}

function showSessionComplete() {
  const pct =
    state.totalStudied > 0
      ? Math.round((state.totalCorrect / state.totalStudied) * 100)
      : 0;

  $("#study-card").innerHTML = `
    <div style="text-align: center; padding: 20px 0;">
      <div style="font-size: 48px; margin-bottom: 12px;">🎉</div>
      <h3 style="margin-bottom: 8px;">Session abgeschlossen!</h3>
      <p style="color: #64748b; margin-bottom: 16px;">
        ${state.totalCorrect} / ${state.totalStudied} richtig (${pct}%)
      </p>
      <button class="btn btn-primary" onclick="location.reload()">
        Weiter lernen
      </button>
    </div>
  `;
}

function updateProgress() {
  const total = state.currentCards.length;
  const current = state.currentCardIndex;
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;

  $("#progress-fill").style.width = `${pct}%`;
  $("#progress-text").textContent = `${current} / ${total}`;
}

// ---- Decks ----
function renderDecks() {
  const container = $("#decks-list");

  if (state.decks.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <p>📦</p>
        <p>Keine Decks vorhanden</p>
        <small>Erstelle Decks in der App oder im Tab "Erstellen"</small>
      </div>`;
    return;
  }

  container.innerHTML = state.decks
    .map(
      (deck) => `
    <div class="deck-item" data-deck-id="${deck.id}">
      <div class="deck-item-header">
        <span class="deck-name">${escapeHtml(deck.name)}</span>
        <span class="deck-count">${deck.card_count || 0} Karten</span>
      </div>
      <div class="deck-subject">${escapeHtml(deck.subject)} — ${escapeHtml(deck.topic)}</div>
      <div class="deck-progress">
        <div class="deck-progress-fill" style="width: ${deck.mastery_pct || 0}%"></div>
      </div>
    </div>`
    )
    .join("");

  // Click handler for decks
  container.querySelectorAll(".deck-item").forEach((el) => {
    el.addEventListener("click", () => {
      const deckId = parseInt(el.dataset.deckId, 10);
      switchTab("study");
      loadDueCards(deckId);
    });
  });
}

function populateDeckSelect() {
  const select = $("#create-deck-select");
  select.innerHTML = '<option value="">Deck wählen...</option>';
  state.decks.forEach((deck) => {
    const opt = document.createElement("option");
    opt.value = deck.id;
    opt.textContent = `${deck.name} (${deck.subject})`;
    select.appendChild(opt);
  });
}

// ---- Create Card ----
async function createCard() {
  const deckId = $("#create-deck-select").value;
  const question = $("#create-question").value.trim();
  const answer = $("#create-answer").value.trim();
  const explanation = $("#create-explanation").value.trim();

  if (!deckId) return showCreateStatus("Bitte Deck wählen", "error");
  if (!question) return showCreateStatus("Bitte Frage eingeben", "error");
  if (!answer) return showCreateStatus("Bitte Antwort eingeben", "error");

  try {
    await API.createCard({
      deck_id: parseInt(deckId, 10),
      question,
      answer,
      explanation,
    });

    showCreateStatus("Karte erstellt!", "success");
    $("#create-question").value = "";
    $("#create-answer").value = "";
    $("#create-explanation").value = "";

    // Reload decks for updated count
    state.decks = await API.getDecks();
    renderDecks();
    populateDeckSelect();
    // Re-select the deck
    $("#create-deck-select").value = deckId;
  } catch (err) {
    showCreateStatus(`Fehler: ${err.message}`, "error");
  }
}

async function createDeck() {
  const name = $("#new-deck-name").value.trim();
  const subject = $("#new-deck-subject").value.trim();
  const topic = $("#new-deck-topic").value.trim();

  if (!name) return showCreateStatus("Bitte Deckname eingeben", "error");

  try {
    await API.createDeck({
      name,
      subject: subject || "Allgemein",
      topic: topic || "Allgemein",
    });

    showCreateStatus("Deck erstellt!", "success");
    $("#new-deck-name").value = "";
    $("#new-deck-subject").value = "";
    $("#new-deck-topic").value = "";

    state.decks = await API.getDecks();
    renderDecks();
    populateDeckSelect();
  } catch (err) {
    showCreateStatus(`Fehler: ${err.message}`, "error");
  }
}

function showCreateStatus(msg, type) {
  const el = $("#create-status");
  el.textContent = msg;
  el.className = `create-status ${type}`;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 3000);
}

// ---- Utilities ----
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
