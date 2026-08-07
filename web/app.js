const config = window.WQU_CHAT_CONFIG;
const chat = document.querySelector("#chat");
const form = document.querySelector("#chat-form");
const questionInput = document.querySelector("#question");
const sendButton = document.querySelector("#send");
const clearChatButton = document.querySelector("#clear-chat");
const HISTORY_STORAGE_KEY = "wqu-chat-history-v1";
const MAX_HISTORY_MESSAGES = 12;
const history = loadHistory();

function loadHistory() {
  try {
    const storedHistory = JSON.parse(window.localStorage.getItem(HISTORY_STORAGE_KEY) || "[]");
    if (!Array.isArray(storedHistory)) return [];
    return storedHistory
      .filter(
        (message) =>
          ["user", "assistant"].includes(message.role) &&
          typeof message.content === "string" &&
          message.content.length > 0 &&
          message.content.length <= 8_000,
      )
      .map((message) => ({
        role: message.role,
        content: message.content,
        sources: message.role === "assistant" ? normalizeSources(message.sources) : [],
      }))
      .slice(-MAX_HISTORY_MESSAGES);
  } catch {
    return [];
  }
}

function normalizeSources(sources) {
  if (!Array.isArray(sources)) return [];
  return sources.flatMap((source) => {
    if (typeof source?.label !== "string" || typeof source.title !== "string" || typeof source.url !== "string") {
      return [];
    }
    try {
      const url = new URL(source.url);
      return ["http:", "https:"].includes(url.protocol)
        ? [{ label: source.label, title: source.title, url: url.href }]
        : [];
    } catch {
      return [];
    }
  });
}

function saveHistory() {
  try {
    window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
  } catch {
    // Chat remains usable if storage is unavailable or full.
  }
}

function addMessage(text, role, sources = [], scroll = true) {
  const message = document.createElement("article");
  message.className = `message ${role}`;
  const content = document.createElement("div");
  content.textContent = text;
  message.append(content);

  if (sources.length) {
    const list = document.createElement("ul");
    list.className = "sources";
    for (const source of sources) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = `[${source.label}] ${source.title}`;
      item.append(link);
      list.append(item);
    }
    message.append(list);
  }
  chat.append(message);
  if (scroll) message.scrollIntoView({ behavior: "smooth", block: "end" });
}

function restoreHistory() {
  for (const message of history) {
    addMessage(message.content, message.role, message.sources, false);
  }
}

function appendExchange(question, answer, sources) {
  history.push(
    { role: "user", content: question, sources: [] },
    { role: "assistant", content: answer, sources: normalizeSources(sources) },
  );
  if (history.length > MAX_HISTORY_MESSAGES) {
    history.splice(0, history.length - MAX_HISTORY_MESSAGES);
  }
  saveHistory();
}

function clearChat() {
  history.splice(0, history.length);
  window.localStorage.removeItem(HISTORY_STORAGE_KEY);
  chat.replaceChildren();
  questionInput.focus();
}

restoreHistory();

clearChatButton.addEventListener("click", clearChat);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;
  if (!config?.apiBaseUrl || config.apiBaseUrl.includes("replace-with-your")) {
    addMessage("The API URL is not configured. Update web/config.js and deploy again.", "error");
    return;
  }

  addMessage(question, "user");
  questionInput.value = "";
  sendButton.disabled = true;
  clearChatButton.disabled = true;
  try {
    const response = await fetch(`${config.apiBaseUrl.replace(/\/$/, "")}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        history: history.map(({ role, content }) => ({ role, content })),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The chat service is unavailable.");
    addMessage(data.answer, "assistant", data.sources);
    appendExchange(question, data.answer, data.sources);
  } catch (error) {
    addMessage(error.message || "Unable to reach the chat service.", "error");
  } finally {
    sendButton.disabled = false;
    clearChatButton.disabled = false;
    questionInput.focus();
  }
});
