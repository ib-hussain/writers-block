(() => {
  let chatMessages, messageForm, userInput, sendBtn;
  let isTyping = false;

  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function addMessage(text, className) {
    const div = document.createElement("div");
    div.className = `message ${className}`;
    div.innerHTML = escapeHtml(text);
    chatMessages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function addTypingIndicator() {
    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.id = "typing-indicator";
    typing.innerHTML = `
      <div class="typing-dots">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
      <div>Typing...</div>
    `;
    chatMessages.appendChild(typing);
    scrollToBottom();
    return typing;
  }

  function removeTypingIndicator() {
    const typing = document.getElementById("typing-indicator");
    if (typing) typing.remove();
  }

  function setInputState(enabled) {
    userInput.disabled = !enabled;
    sendBtn.disabled = !enabled;
  }

  function autoResize() {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 160) + "px";
  }

  async function loadChatHistoryForToday() {
    const today = new Date().toISOString().split("T")[0];
    const typing = addTypingIndicator();

    try {
      const res = await fetch(`/api/profile/history?date=${encodeURIComponent(today)}`);
      const data = await res.json();

      chatMessages.innerHTML = "";

      if (res.ok && data && data.success === true && Array.isArray(data.rows) && data.rows.length > 0) {
        for (const row of data.rows) {
          if (row.userprompt) addMessage(row.userprompt, "user-message");
          if (row.chatresponse) addMessage(row.chatresponse, "bot-message");
        }
      } else {
        // No history (or 404 NO_ROWS_FOR_DATE)
        addMessage("I'm your writing assistant. How can I help you today?", "bot-message");
      }
    } catch (err) {
      console.error("History load failed:", err);
      chatMessages.innerHTML = "";
      addMessage("Error loading chat history. Starting fresh session.", "bot-message");
    } finally {
      typing.remove();
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const msg = userInput.value.trim();
    if (!msg || isTyping) return;

    addMessage(msg, "user-message");
    userInput.value = "";
    autoResize();

    isTyping = true;
    setInputState(false);

    const typing = addTypingIndicator();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg })
      });

      const data = await res.json();

      typing.remove();

      if (!res.ok || !data || data.success !== true) {
        const serverMsg = (data && data.message) ? data.message : `API error: ${res.status}`;
        addMessage(`Server error: ${serverMsg}`, "bot-message");
        return;
      }

      addMessage(data.response || "No response returned.", "bot-message");
    } catch (err) {
      console.error("Send failed:", err);
      typing.remove();
      addMessage("Sorry, I encountered an error. Please try again.", "bot-message");
    } finally {
      isTyping = false;
      setInputState(true);
      userInput.focus();
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    chatMessages = document.getElementById("chat-messages");
    messageForm = document.getElementById("message-form");
    userInput = document.getElementById("user-input");
    sendBtn = document.getElementById("send-btn");

    if (!chatMessages || !messageForm || !userInput || !sendBtn) {
      console.error("Chatbot DOM elements not found. Check chatbot.html IDs.");
      return;
    }

    userInput.addEventListener("input", autoResize);
    messageForm.addEventListener("submit", handleSubmit);

    autoResize();
    userInput.focus();
    loadChatHistoryForToday();
  });
})();
