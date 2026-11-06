const config = window.WQU_CHAT_CONFIG;
const chat = document.querySelector("#chat");
const form = document.querySelector("#chat-form");
const questionInput = document.querySelector("#question");
const sendButton = document.querySelector("#send");
const clearChatButton = document.querySelector("#clear-chat");
const thinking = document.querySelector("#thinking");
const sampleQuestions = document.querySelector(".sample-questions");
const HISTORY_STORAGE_KEY = "wqu-chat-history-v1";
const CONVERSATION_STORAGE_KEY = "wqu-chat-conversation-v1";
let conversationId = loadConversationId();

function loadConversationId(reset = false) {
  let id;
  try {
    id = reset ? null : window.localStorage.getItem(CONVERSATION_STORAGE_KEY);
  } catch {
    /* Storage may be unavailable. */
  }
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      id || "",
    )
  ) {
    id = crypto.randomUUID();
  }
  try {
    window.localStorage.setItem(CONVERSATION_STORAGE_KEY, id);
  } catch {
    /* Keep the ID in memory for this page. */
  }
  return id;
}

const MAX_HISTORY_MESSAGES = 12;
const INLINE_MARKDOWN =
  /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*)/g;
const history = loadHistory();

function loadHistory() {
  try {
    const storedHistory = JSON.parse(
      window.localStorage.getItem(HISTORY_STORAGE_KEY) || "[]",
    );
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
        sources:
          message.role === "assistant" ? normalizeSources(message.sources) : [],
      }))
      .slice(-MAX_HISTORY_MESSAGES);
  } catch {
    return [];
  }
}

function normalizeSources(sources) {
  if (!Array.isArray(sources)) return [];
  return sources.flatMap((source) => {
    if (
      typeof source?.label !== "string" ||
      typeof source.title !== "string" ||
      typeof source.url !== "string"
    ) {
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

function citedSources(text, sources) {
  const labels = new Set(
    [...text.matchAll(/\[(S\d+)\]/g)].map((match) => match[1]),
  );
  return normalizeSources(sources).filter((source) => labels.has(source.label));
}

function saveHistory() {
  try {
    window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
  } catch {
    // Chat remains usable if storage is unavailable or full.
  }
}

function appendInlineMarkdown(container, text) {
  let lastIndex = 0;
  for (const match of text.matchAll(INLINE_MARKDOWN)) {
    container.append(
      document.createTextNode(text.slice(lastIndex, match.index)),
    );
    if (match[2]) {
      const link = document.createElement("a");
      link.href = match[3];
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = match[2];
      container.append(link);
    } else if (match[4]) {
      const strong = document.createElement("strong");
      strong.textContent = match[4];
      container.append(strong);
    } else if (match[5]) {
      const code = document.createElement("code");
      code.textContent = match[5];
      container.append(code);
    } else {
      const emphasis = document.createElement("em");
      emphasis.textContent = match[6];
      container.append(emphasis);
    }
    lastIndex = match.index + match[0].length;
  }
  container.append(document.createTextNode(text.slice(lastIndex)));
}

function renderMarkdown(text) {
  const container = document.createElement("div");
  container.className = "markdown";
  let paragraphLines = [];
  let list = null;
  let codeLines = null;

  const flushParagraph = () => {
    if (!paragraphLines.length) return;
    const paragraph = document.createElement("p");
    appendInlineMarkdown(paragraph, paragraphLines.join(" "));
    container.append(paragraph);
    paragraphLines = [];
  };
  const flushList = () => {
    if (!list) return;
    container.append(list);
    list = null;
  };

  for (const line of text.split("\n")) {
    if (line.trim().startsWith("```")) {
      flushParagraph();
      flushList();
      if (codeLines === null) {
        codeLines = [];
      } else {
        const pre = document.createElement("pre");
        const code = document.createElement("code");
        code.textContent = codeLines.join("\n");
        pre.append(code);
        container.append(pre);
        codeLines = null;
      }
      continue;
    }
    if (codeLines !== null) {
      codeLines.push(line);
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    const listItem =
      line.match(/^(\d+)\.\s+(.+)$/) || line.match(/^[-*]\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const element = document.createElement(`h${heading[1].length}`);
      appendInlineMarkdown(element, heading[2]);
      container.append(element);
    } else if (listItem) {
      flushParagraph();
      const isOrdered = /^\d+\./.test(line);
      const tagName = isOrdered ? "OL" : "UL";
      if (!list || list.tagName !== tagName) {
        flushList();
        list = document.createElement(tagName.toLowerCase());
      }
      const item = document.createElement("li");
      appendInlineMarkdown(item, listItem[isOrdered ? 2 : 1]);
      list.append(item);
    } else if (!line.trim()) {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraphLines.push(line.trim());
    }
  }

  if (codeLines !== null) {
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = codeLines.join("\n");
    pre.append(code);
    container.append(pre);
  }
  flushParagraph();
  flushList();
  return container;
}

function addMessage(text, role, sources = [], scroll = true) {
  const message = document.createElement("article");
  message.className = `message ${role}`;
  const content = document.createElement("div");
  content.append(renderMarkdown(text));
  if (role === "assistant") {
    const label = document.createElement("div");
    label.className = "message-label";
    label.textContent = "STUDY COMPANION";
    message.append(label);
  }
  message.append(content);

  const displayedSources =
    role === "assistant"
      ? citedSources(text, sources)
      : normalizeSources(sources);
  if (displayedSources.length) {
    const list = document.createElement("ul");
    list.className = "sources";
    for (const source of displayedSources) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = `[${source.label}] ${source.title}`;
      item.append(link);
      list.append(item);
    }
    const details = document.createElement("details");
    details.className = "sources-details";
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = `${displayedSources.length} source${displayedSources.length === 1 ? "" : "s"} · Explore the references`;
    details.append(summary, list);
    message.append(details);
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
    {
      role: "assistant",
      content: answer,
      sources: citedSources(answer, sources),
    },
  );
  if (history.length > MAX_HISTORY_MESSAGES) {
    history.splice(0, history.length - MAX_HISTORY_MESSAGES);
  }
  saveHistory();
}

function clearChat() {
  history.splice(0, history.length);
  conversationId = loadConversationId(true);
  try {
    window.localStorage.removeItem(HISTORY_STORAGE_KEY);
  } catch {
    /* Optional storage. */
  }
  chat.replaceChildren();
  sampleQuestions.hidden = false;
  questionInput.value = "";
  resizeInput();
  questionInput.focus();
}

restoreHistory();
sampleQuestions.hidden = history.length > 0;

clearChatButton.addEventListener("click", clearChat);

for (const button of document.querySelectorAll(".sample-question")) {
  button.addEventListener("click", () => {
    questionInput.value = button.dataset.question || "";
    resizeInput();
    questionInput.focus();
  });
}

function resizeInput() {
  questionInput.style.height = "auto";
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 160)}px`;
}
questionInput.addEventListener("input", resizeInput);
questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    if (!sendButton.disabled) form.requestSubmit();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question || sendButton.disabled) return;
  if (!config?.apiBaseUrl || config.apiBaseUrl.includes("replace-with-your")) {
    addMessage(
      "The API URL is not configured. Update web/config.js and deploy again.",
      "error",
    );
    return;
  }

  addMessage(question, "user");
  sampleQuestions.hidden = true;
  questionInput.value = "";
  resizeInput();
  thinking.hidden = false;
  chat.setAttribute("aria-busy", "true");
  thinking.scrollIntoView({ behavior: "smooth", block: "end" });
  sendButton.disabled = true;
  clearChatButton.disabled = true;
  try {
    const response = await fetch(
      `${config.apiBaseUrl.replace(/\/$/, "")}/chat`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          conversation_id: conversationId,
          history: history.map(({ role, content }) => ({ role, content })),
        }),
      },
    );
    const data = await response.json();
    if (!response.ok)
      throw new Error(data.detail || "The chat service is unavailable.");
    addMessage(data.answer, "assistant", data.sources);
    appendExchange(question, data.answer, data.sources);
  } catch (error) {
    addMessage(error.message || "Unable to reach the chat service.", "error");
  } finally {
    thinking.hidden = true;
    chat.setAttribute("aria-busy", "false");
    sendButton.disabled = false;
    clearChatButton.disabled = false;
    questionInput.focus();
  }
});
