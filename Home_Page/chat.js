const BACKEND_API = "http://127.0.0.1:5000/api/cinebot";

let chatHistory = [];

document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chatForm");
  const textarea = document.getElementById("userPrompt");

  if (chatForm) {
    chatForm.addEventListener("submit", handleChatSubmit);
  }

  if (textarea) {
    textarea.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
  }

  appendChatMessage(
    "Welcome to CineBot! I am your AI film expert powered by Ollama. Ask me anything about movies: plots, characters, what-if scenarios, predictions, recommendations, or deep analysis.\n\n- What if Thanos won in Endgame?\n- Compare Nolan's Batman trilogy to the MCU\n- What are the hidden themes in Parasite?",
    "bot"
  );
});

async function askOllamaBackend(question, history) {
  const response = await fetch(BACKEND_API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: question,
      movie: null,
      history: history.slice(-20),
    }),
  });
  
  if (!response.ok) {
    throw new Error(`Backend API failed: ${response.status}`);
  }
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  
  return data.reply;
}

async function handleChatSubmit(event) {
  event.preventDefault();

  const textarea = document.getElementById("userPrompt");
  const prompt = textarea.value.trim();
  if (!prompt) return;

  appendChatMessage(prompt, "user");
  textarea.value = "";
  chatHistory.push({ role: "user", content: prompt });

  const typingEl = showTypingIndicator();

  try {
    const reply = await askOllamaBackend(prompt, chatHistory);

    removeTypingIndicator(typingEl);
    appendChatMessage(reply, "bot");
    chatHistory.push({ role: "assistant", content: reply });
  } catch (error) {
    removeTypingIndicator(typingEl);
    console.error("CineBot fetch error:", error);
    appendChatMessage(
      "Could not reach Backend. Please ensure your Python flask server is running on http://127.0.0.1:5000.",
      "bot"
    );
  }
}

function appendChatMessage(text, sender) {
  const container = document.getElementById("chatWindow");
  if (!container) return;

  const message = document.createElement("div");
  message.className = `chat-msg ${sender === "user" ? "user" : "bot"}`;

  if (sender === "bot") {
    message.innerHTML = formatBotMessage(text);
  } else {
    message.textContent = text;
  }

  container.appendChild(message);
  container.scrollTop = container.scrollHeight;
}

function formatBotMessage(text) {
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/\n\n/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");
  html = html.replace(/(?:^|<br>)-\s+(.+?)(?=<br>|<\/p>|$)/g, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
  html = html.replace(/<\/ul>\s*<ul>/g, "");

  return `<p>${html}</p>`;
}

function showTypingIndicator() {
  const container = document.getElementById("chatWindow");
  if (!container) return null;

  const indicator = document.createElement("div");
  indicator.className = "chat-msg bot typing-indicator";
  indicator.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
  container.appendChild(indicator);
  container.scrollTop = container.scrollHeight;
  return indicator;
}

function removeTypingIndicator(indicator) {
  if (indicator && indicator.parentNode) {
    indicator.parentNode.removeChild(indicator);
  }
}
