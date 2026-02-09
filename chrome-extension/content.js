// ============================
// Smart Study Cards - Content Script
// ============================
// Allows creating flashcards from text selected on any webpage.

(() => {
  let tooltip = null;

  // Listen for text selection
  document.addEventListener("mouseup", (e) => {
    const selection = window.getSelection();
    const text = selection?.toString().trim();

    removeTooltip();

    if (!text || text.length < 5) return;

    // Don't show on input elements
    if (
      e.target.tagName === "INPUT" ||
      e.target.tagName === "TEXTAREA" ||
      e.target.isContentEditable
    ) {
      return;
    }

    showTooltip(e.clientX, e.clientY, text);
  });

  // Remove tooltip on click elsewhere
  document.addEventListener("mousedown", (e) => {
    if (tooltip && !tooltip.contains(e.target)) {
      removeTooltip();
    }
  });

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "GET_SELECTION") {
      const text = window.getSelection()?.toString().trim() || "";
      sendResponse({ text });
    }
    return true;
  });

  function showTooltip(x, y, selectedText) {
    tooltip = document.createElement("div");
    tooltip.className = "ssc-tooltip";
    tooltip.innerHTML = `
      <button class="ssc-tooltip-btn ssc-tooltip-card" title="Als Karteikarte speichern">
        📝 Karte erstellen
      </button>
      <button class="ssc-tooltip-btn ssc-tooltip-question" title="Als Frage verwenden">
        ❓ Als Frage
      </button>
    `;

    // Position relative to viewport, then adjust for scroll
    tooltip.style.left = `${x + window.scrollX}px`;
    tooltip.style.top = `${y + window.scrollY - 45}px`;

    document.body.appendChild(tooltip);

    // Ensure tooltip is within viewport
    const rect = tooltip.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      tooltip.style.left = `${window.innerWidth - rect.width - 10 + window.scrollX}px`;
    }
    if (rect.top < 0) {
      tooltip.style.top = `${y + window.scrollY + 20}px`;
    }

    // Card button - save selection as answer, open popup to add question
    tooltip
      .querySelector(".ssc-tooltip-card")
      .addEventListener("click", (e) => {
        e.stopPropagation();
        const pageTitle = document.title;
        const pageUrl = window.location.href;

        chrome.storage.local.set({
          pendingCard: {
            answer: selectedText,
            question: "",
            source: `${pageTitle} (${pageUrl})`,
          },
        });

        chrome.runtime.sendMessage({ type: "OPEN_POPUP" });
        removeTooltip();
      });

    // Question button - save selection as question
    tooltip
      .querySelector(".ssc-tooltip-question")
      .addEventListener("click", (e) => {
        e.stopPropagation();

        chrome.storage.local.set({
          pendingCard: {
            question: selectedText,
            answer: "",
            source: window.location.href,
          },
        });

        chrome.runtime.sendMessage({ type: "OPEN_POPUP" });
        removeTooltip();
      });
  }

  function removeTooltip() {
    if (tooltip) {
      tooltip.remove();
      tooltip = null;
    }
  }
})();
