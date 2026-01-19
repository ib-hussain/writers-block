(() => {
  let chatMessages, messageForm, userInput, sendBtn;
  let varsPanel, varsToggleHeader, saveVarsBtn, resetVarsBtn, varsStatus;

  let isTyping = false;

  const VAR_KEYS = [
    "TITLE", "KEYWORDS", "INSERT_INTRO_QUESTION", 
    "INSERT_INTRO_EXAMPLE", "INSERT_CTA_EXAMPLE",
    "INSERT_FAQ_QUESTIONS", "SOURCE", "COMPANY_NAME",
    "CALL_NUMBER", "ADDRESS", "STATE_NAME", "LINK", "COMPANY_EMPLOYEE"
  ];

  // Default values for variables
  const DEFAULT_VALUES = {
    "KEYWORDS": "lawyer, attorney, consultation, claim, accident, case, insurance, insurance company, evidence, police report, medical records, witness statements, compensation, damages, liability, settlement, legal process, statute limitations, comparative negligence, policy limits, contingency fee, trial, litigation, negotiation, expert witnesses, accident reconstruction, dashcam footage, surveillance footage, medical bills, total loss, gap"
  };

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
    userInput.style.height = Math.min(userInput.scrollHeight, 140) + "px";
  }

  function todayYYYYMMDD() {
    return new Date().toISOString().split("T")[0];
  }

  function toggleVarsPanel() {
    varsPanel.classList.toggle("collapsed");
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
      if (el) {
        // Priority: saved value > default value > empty
        const value = varsObj?.[k] !== undefined && varsObj?.[k] !== "" 
          ? varsObj[k] 
          : (DEFAULT_VALUES[k] || "");
        el.value = value;
      }
    }
  }

  function loadVars() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return null; // Return null if nothing saved yet
      const parsed = JSON.parse(raw);
      return (parsed && typeof parsed === "object") ? parsed : null;
    } catch {
      return null;
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
    const typing = addTypingIndicator();

    try {
      const res = await fetch(`/api/profile/history?date=${encodeURIComponent(today)}`);
      const data = await res.json();

      chatMessages.innerHTML = "";

      if (res.ok && data && data.success === true && Array.isArray(data.rows) && data.rows.length > 0) {
        for (const row of data.rows) {
          if (row.userprompt) {
            const userMsg = extractUserMessage(row.userprompt);
            addMessage(userMsg, "user-message");
          }
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

  function extractUserMessage(fullPrompt) {
    // Extract just the user message, removing PROMPT_VARIABLES block
    const lines = fullPrompt.split('\n');
    const varStartIndex = lines.findIndex(line => line.trim() === 'PROMPT_VARIABLES:');
    
    if (varStartIndex === -1) {
      return fullPrompt.trim();
    }
    
    // Find where variables end (look for line that doesn't contain ":")
    let messageStartIndex = varStartIndex + 1;
    for (let i = varStartIndex + 1; i < lines.length; i++) {
      const line = lines[i].trim();
      // Empty line or line without ":" indicates end of variables
      if (line === "" || (!line.includes(':') && line.length > 0)) {
        messageStartIndex = i;
        break;
      }
    }
    
    return lines.slice(messageStartIndex).join('\n').trim();
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

    varsPanel = document.getElementById("varsPanel");
    varsToggleHeader = document.getElementById("varsToggleHeader");
    saveVarsBtn = document.getElementById("saveVarsBtn");
    resetVarsBtn = document.getElementById("resetVarsBtn");
    varsStatus = document.getElementById("varsStatus");

    if (!chatMessages || !messageForm || !userInput || !sendBtn) {
      console.error("Chatbot DOM elements not found. Check chatbot.html IDs.");
      return;
    }

    userInput.addEventListener("input", autoResize);
    messageForm.addEventListener("submit", handleSubmit);

    // Toggle panel on header click
    if (varsToggleHeader && varsPanel) {
      varsToggleHeader.addEventListener("click", toggleVarsPanel);
    }

    if (saveVarsBtn) {
      saveVarsBtn.addEventListener("click", () => {
        const varsObj = getVarsFromUI();
        saveVars(varsObj);
        setStatus("✓ Saved");
      });
    }

    if (resetVarsBtn) {
      resetVarsBtn.addEventListener("click", () => {
        if (confirm("Are you sure you want to reset all variables to default values?")) {
          const defaults = {};
          for (const k of VAR_KEYS) {
            defaults[k] = DEFAULT_VALUES[k] || "";
          }
          setVarsToUI(defaults);
          saveVars(defaults);
          setStatus("✓ Reset to defaults");
        }
      });
    }

    // Load saved vars OR set defaults if first time
    const savedVars = loadVars();
    if (savedVars === null) {
      // First time - use defaults
      setVarsToUI(DEFAULT_VALUES);
      // Save defaults to localStorage so keywords persist
      saveVars(DEFAULT_VALUES);
    } else {
      // Load saved values (will use defaults for any missing values)
      setVarsToUI(savedVars);
    }

    autoResize();
    userInput.focus();

    // Load today's persisted chat
    loadChatHistoryForToday();
  });
})();