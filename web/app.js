const config = window.WQU_CHAT_CONFIG;
const chat = document.querySelector("#chat");
const form = document.querySelector("#chat-form");
const questionInput = document.querySelector("#question");
const sendButton = document.querySelector("#send");
const history = [];

function addMessage(text, role, sources = []) {
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
  message.scrollIntoView({ behavior: "smooth", block: "end" });
}

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
  try {
    const response = await fetch(`${config.apiBaseUrl.replace(/\/$/, "")}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The chat service is unavailable.");
    addMessage(data.answer, "assistant", data.sources);
    history.push({ role: "user", content: question }, { role: "assistant", content: data.answer });
  } catch (error) {
    addMessage(error.message || "Unable to reach the chat service.", "error");
  } finally {
    sendButton.disabled = false;
    questionInput.focus();
  }
});
