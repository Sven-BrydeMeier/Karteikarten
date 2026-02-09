// ============================
// Smart Study Cards - Options Page JS
// ============================

document.addEventListener("DOMContentLoaded", async () => {
  // Load saved settings
  const stored = await chrome.storage.sync.get([
    "serverUrl",
    "cardsPerSession",
    "userId",
  ]);

  if (stored.serverUrl) {
    document.getElementById("server-url").value = stored.serverUrl;
  }
  if (stored.cardsPerSession) {
    document.getElementById("cards-per-session").value = stored.cardsPerSession;
  }
  if (stored.userId) {
    document.getElementById("user-id").value = stored.userId;
  }

  // Save server settings
  document.getElementById("btn-save").addEventListener("click", async () => {
    const url = document.getElementById("server-url").value.trim();
    if (!url) {
      showStatus("save-status", "Bitte URL eingeben", "error");
      return;
    }

    await chrome.storage.sync.set({ serverUrl: url });
    showStatus("save-status", "Gespeichert!", "success");
  });

  // Test connection
  document.getElementById("btn-test").addEventListener("click", async () => {
    const url = document.getElementById("server-url").value.trim();
    const resultEl = document.getElementById("test-result");

    resultEl.textContent = "Teste Verbindung...";
    resultEl.className = "test-result";

    try {
      const parsed = new URL(url);
      const port = parseInt(parsed.port || "8501", 10);
      parsed.port = String(port + 1);
      parsed.pathname = "/api/health";

      const resp = await fetch(parsed.toString(), {
        signal: AbortSignal.timeout(5000),
      });

      if (resp.ok) {
        const data = await resp.json();
        resultEl.textContent = `Verbunden! Server v${data.version || "?"}`;
        resultEl.className = "test-result test-ok";
      } else {
        resultEl.textContent = `Fehler: HTTP ${resp.status}`;
        resultEl.className = "test-result test-fail";
      }
    } catch (err) {
      resultEl.textContent = `Keine Verbindung: ${err.message}`;
      resultEl.className = "test-result test-fail";
    }
  });

  // Save preferences
  document
    .getElementById("btn-save-prefs")
    .addEventListener("click", async () => {
      const cardsPerSession = parseInt(
        document.getElementById("cards-per-session").value,
        10
      );
      const userId = parseInt(document.getElementById("user-id").value, 10);

      await chrome.storage.sync.set({ cardsPerSession, userId });
      showStatus("prefs-status", "Einstellungen gespeichert!", "success");
    });
});

function showStatus(elementId, message, type) {
  const el = document.getElementById(elementId);
  el.textContent = message;
  el.className = `status-msg ${type}`;
  setTimeout(() => {
    el.className = "status-msg";
  }, 3000);
}
