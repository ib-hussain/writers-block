(() => {
  let chatMessages, messageForm, userInput, sendBtn;
  let toggleVarsBtn, closeVarsBtn, varsPanel, saveVarsBtn, resetVarsBtn, varsStatus;

  let isTyping = false;

  const VAR_KEYS = [
    "TITLE", "KEYWORDS", "INSERT_INTRO_QUESTION", 
    "INSERT_INTRO_EXAMPLE", "INSERT_CTA_EXAMPLE",
    "INSERT_FAQ_QUESTIONS", "SOURCE", "COMPANY_NAME",
    "CALL_NUMBER", "ADDRESS", "STATE_NAME", "LINK", "COMPANY_EMPLOYEE"
  ];

  const LS_KEY = "wb_prompt_vars_v1";

  function escapeHtml(str) {
    return String(str ?? "")
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

  function todayYYYYMMDD() {
    return new Date().toISOString().split("T")[0];
  }

  function openVars() {
    varsPanel.classList.add("open");
    varsPanel.setAttribute("aria-hidden", "false");
  }

  function closeVars() {
    varsPanel.classList.remove("open");
    varsPanel.setAttribute("aria-hidden", "true");
  }

  function getVarsFromUI() {
    const out = {};
    for (const k of VAR_KEYS) {
      const el = document.getElementById(`VAR_${k}`);
      out[k] = (el ? el.value : "").trim();
    }
    return out;
  }

  function setVarsToUI(varsObj) {
    for (const k of VAR_KEYS) {
      const el = document.getElementById(`VAR_${k}`);
      if (el) el.value = (varsObj?.[k] ?? "");
    }
  }

  function loadVars() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return (parsed && typeof parsed === "object") ? parsed : {};
    } catch {
      return {};
    }
  }

  function saveVars(varsObj) {
    localStorage.setItem(LS_KEY, JSON.stringify(varsObj || {}));
  }

  function setStatus(msg) {
    if (!varsStatus) return;
    varsStatus.textContent = msg || "";
    if (msg) {
      setTimeout(() => { varsStatus.textContent = ""; }, 1800);
    }
  }

  async function loadChatHistoryForToday() {
    const today = todayYYYYMMDD();

    // Keep the initial bot message only until we know we have history
    const typing = addTypingIndicator();

    try {
      const res = await fetch(`/api/profile/history?date=${encodeURIComponent(today)}`);
      const data = await res.json();

      chatMessages.innerHTML = "";

      if (res.ok && data && data.success === true && Array.isArray(data.rows) && data.rows.length > 0) {
        for (const row of data.rows) {
          // userprompt may contain the PROMPT_VARIABLES block; we should show only the final user message line.
          // For now: show full stored prompt so you can verify vars are being applied.
          if (row.userprompt) addMessage(row.userprompt, "user-message");
          if (row.chatresponse) addMessage(row.chatresponse, "bot-message");
        }
      } else {
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

    const varsObj = getVarsFromUI();
    saveVars(varsObj);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, vars: varsObj })
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

    toggleVarsBtn = document.getElementById("toggleVarsBtn");
    closeVarsBtn = document.getElementById("closeVarsBtn");
    varsPanel = document.getElementById("varsPanel");
    saveVarsBtn = document.getElementById("saveVarsBtn");
    resetVarsBtn = document.getElementById("resetVarsBtn");
    varsStatus = document.getElementById("varsStatus");

    if (!chatMessages || !messageForm || !userInput || !sendBtn) {
      console.error("Chatbot DOM elements not found. Check chatbot.html IDs.");
      return;
    }

    userInput.addEventListener("input", autoResize);
    messageForm.addEventListener("submit", handleSubmit);

    if (toggleVarsBtn && varsPanel) {
      toggleVarsBtn.addEventListener("click", () => openVars());
    }
    if (closeVarsBtn) {
      closeVarsBtn.addEventListener("click", () => closeVars());
    }

    if (saveVarsBtn) {
      saveVarsBtn.addEventListener("click", () => {
        const varsObj = getVarsFromUI();
        saveVars(varsObj);
        setStatus("Saved.");
      });
    }

    if (resetVarsBtn) {
      resetVarsBtn.addEventListener("click", () => {
        const empty = {};
        for (const k of VAR_KEYS) empty[k] = "";
        setVarsToUI(empty);
        saveVars(empty);
        setStatus("Reset.");
      });
    }

    // Load vars to UI
    setVarsToUI(loadVars());

    autoResize();
    userInput.focus();

    // Load today's persisted chat
    loadChatHistoryForToday();
  });
})();
