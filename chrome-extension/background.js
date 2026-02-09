// ============================
// Smart Study Cards - Background Service Worker
// ============================

// Context menu for right-click -> create flashcard
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "ssc-create-card",
    title: "Als Karteikarte speichern",
    contexts: ["selection"],
  });

  chrome.contextMenus.create({
    id: "ssc-create-question",
    title: "Als Frage verwenden",
    contexts: ["selection"],
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  const selectedText = info.selectionText?.trim();
  if (!selectedText) return;

  if (info.menuItemId === "ssc-create-card") {
    chrome.storage.local.set({
      pendingCard: {
        answer: selectedText,
        question: "",
        source: `${tab.title} (${tab.url})`,
      },
    });
    // Open popup by showing the action popup
    chrome.action.openPopup();
  }

  if (info.menuItemId === "ssc-create-question") {
    chrome.storage.local.set({
      pendingCard: {
        question: selectedText,
        answer: "",
        source: tab.url,
      },
    });
    chrome.action.openPopup();
  }
});

// Handle messages from content script
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "OPEN_POPUP") {
    chrome.action.openPopup();
  }
  return true;
});
