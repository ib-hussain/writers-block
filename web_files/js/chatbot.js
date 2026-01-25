(() => {
  const overlay = document.getElementById("loadingOverlay");
  const reloadBtn = document.getElementById("reloadBtn");

  let chatMessages, messageForm, userInput, sendBtn;
  let varsPanel, varsToggleHeader, saveVarsBtn, resetVarsBtn, varsStatus;

  let isTyping = false;

  const VAR_KEYS = [
    "TITLE", "KEYWORDS", "INSERT_INTRO_QUESTION", 
    "INSERT_FAQ_QUESTIONS", "SOURCE", "COMPANY_NAME",
    "CALL_NUMBER", "ADDRESS", "STATE_NAME", "LINK", "COMPANY_EMPLOYEE",
    "BLOGTYPE", "BLOGFOREXAMPLE", "TEMPERATURE",
    "BLOGPART_INTRO", "BLOGPART_FINALCTA", "BLOGPART_FAQS", 
    "BLOGPART_BUSINESSDESC", "BLOGPART_SHORTCTA",
    "PROMPT_FULLBLOG", "PROMPT_INTRO", "PROMPT_FINALCTA",
    "PROMPT_FULLFAQS", "PROMPT_BUSINESSDESC", "PROMPT_REFERENCES", "PROMPT_SHORTCTA"
  ];

  // Default values for variables
  const DEFAULT_VALUES = {
    "KEYWORDS": "lawyer, attorney, consultation, claim, accident, case, insurance, insurance company, evidence, police report, medical records, witness statements, compensation, damages, liability, settlement, legal process, statute limitations, comparative negligence, policy limits, contingency fee, trial, litigation, negotiation, expert witnesses, accident reconstruction, dashcam footage, surveillance footage, medical bills, total loss, gap",
    "BLOGTYPE": "Legal",
    "TEMPERATURE": "0.70",
    "BLOGFOREXAMPLE": [],
    "BLOGPART_INTRO": [],
    "BLOGPART_FINALCTA": [],
    "BLOGPART_FAQS": [],
    "BLOGPART_BUSINESSDESC": [],
    "BLOGPART_SHORTCTA": []
  };

  const LS_KEY = "wb_prompt_vars_v1";

  function showLoading() {
    overlay.classList.remove("hidden");
    overlay.setAttribute("aria-hidden", "false");
  }
  
  function hideLoading() {
    overlay.classList.add("hidden");
    overlay.setAttribute("aria-hidden", "true");
  }

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

  // Initialize checkboxes based on blog type
  function initBlogForExampleCheckboxes() {
    const blogType = document.querySelector('input[name="blogType"]:checked')?.value || "Legal";
    const container = document.getElementById("blogForExampleContainer");
    container.innerHTML = "";

    const start = blogType === "Legal" ? 1 : 11;
    const end = blogType === "Legal" ? 10 : 20;

    for (let i = start; i <= end; i++) {
      const label = document.createElement("label");
      label.className = "checkbox-label";
      label.innerHTML = `
        <input type="checkbox" name="blogForExample" value="${i}" />
        <span>Blog ${i}</span>
      `;
      container.appendChild(label);

      // Add change listener to enforce 10 max
      const checkbox = label.querySelector('input');
      checkbox.addEventListener('change', () => {
        handleCheckboxLimit('blogForExample', 10);
        updateCheckboxStyles('blogForExample');
      });
    }

    // Restore saved values
    const saved = loadVars();
    if (saved && saved.BLOGFOREXAMPLE) {
      saved.BLOGFOREXAMPLE.forEach(val => {
        const cb = container.querySelector(`input[value="${val}"]`);
        if (cb) cb.checked = true;
      });
    }
    updateCheckboxStyles('blogForExample');
  }

  // Initialize blog part checkboxes
  function initBlogPartCheckboxes() {
    const sections = ['Intro', 'FinalCTA', 'FAQs', 'BusinessDesc', 'ShortCTA'];
    
    sections.forEach(section => {
      const container = document.getElementById(`example${section}`);
      if (!container) return;
      
      container.innerHTML = "";

      for (let i = 1; i <= 10; i++) {
        const label = document.createElement("label");
        label.className = "checkbox-label";
        label.innerHTML = `
          <input type="checkbox" name="blogPart${section}" value="${i}" />
          <span>${i}</span>
        `;
        container.appendChild(label);

        // Add change listener to enforce 10 max
        const checkbox = label.querySelector('input');
        checkbox.addEventListener('change', () => {
          handleCheckboxLimit(`blogPart${section}`, 10);
          updateCheckboxStyles(`blogPart${section}`);
        });
      }
    });

    // Restore saved values
    const saved = loadVars();
    if (saved) {
      sections.forEach(section => {
        const key = `BLOGPART_${section.toUpperCase()}`;
        if (saved[key]) {
          saved[key].forEach(val => {
            const cb = document.querySelector(`input[name="blogPart${section}"][value="${val}"]`);
            if (cb) cb.checked = true;
          });
        }
        updateCheckboxStyles(`blogPart${section}`);
      });
    }
  }

  // Handle checkbox limit (max selections)
  function handleCheckboxLimit(name, max) {
    const checkboxes = document.querySelectorAll(`input[name="${name}"]`);
    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    
    if (checked.length > max) {
      // Uncheck the last checked one
      checked[checked.length - 1].checked = false;
    }
  }

  // Update checkbox visual styles
  function updateCheckboxStyles(name) {
    const checkboxes = document.querySelectorAll(`input[name="${name}"]`);
    checkboxes.forEach(cb => {
      const label = cb.closest('.checkbox-label');
      if (cb.checked) {
        label.classList.add('checked');
      } else {
        label.classList.remove('checked');
      }
    });
  }

  // Temperature slider
  function initTemperatureSlider() {
    const slider = document.getElementById('VAR_TEMPERATURE');
    const valueDisplay = document.getElementById('temperatureValue');
    
    if (!slider || !valueDisplay) return;

    slider.addEventListener('input', (e) => {
      const value = (parseInt(e.target.value) / 100).toFixed(2);
      valueDisplay.textContent = value;
    });

    // Set initial value
    const saved = loadVars();
    if (saved && saved.TEMPERATURE) {
      const percent = Math.round(parseFloat(saved.TEMPERATURE) * 100);
      slider.value = percent;
      valueDisplay.textContent = saved.TEMPERATURE;
    }
  }

  function getVarsFromUI() {
    const out = {};
    
    // Text inputs and textareas
    const simpleKeys = [
      "TITLE", "KEYWORDS", "INSERT_INTRO_QUESTION", 
      "INSERT_FAQ_QUESTIONS", "SOURCE", "COMPANY_NAME",
      "CALL_NUMBER", "ADDRESS", "STATE_NAME", "LINK", "COMPANY_EMPLOYEE",
      "PROMPT_FULLBLOG", "PROMPT_INTRO", "PROMPT_FINALCTA",
      "PROMPT_FULLFAQS", "PROMPT_BUSINESSDESC", "PROMPT_REFERENCES", "PROMPT_SHORTCTA"
    ];
    
    simpleKeys.forEach(k => {
      const el = document.getElementById(`VAR_${k}`);
      out[k] = (el ? el.value : "").trim();
    });

    // Blog type (radio)
    const blogTypeRadio = document.querySelector('input[name="blogType"]:checked');
    out.BLOGTYPE = blogTypeRadio ? blogTypeRadio.value : "Legal";

    // Temperature
    const tempSlider = document.getElementById('VAR_TEMPERATURE');
    if (tempSlider) {
      out.TEMPERATURE = (parseInt(tempSlider.value) / 100).toFixed(2);
    }

    // Blog for example (checkboxes)
    const blogForExample = Array.from(document.querySelectorAll('input[name="blogForExample"]:checked'))
      .map(cb => cb.value);
    out.BLOGFOREXAMPLE = blogForExample;

    // Blog part checkboxes
    const sections = ['Intro', 'FinalCTA', 'FAQs', 'BusinessDesc', 'ShortCTA'];
    sections.forEach(section => {
      const checked = Array.from(document.querySelectorAll(`input[name="blogPart${section}"]:checked`))
        .map(cb => cb.value);
      out[`BLOGPART_${section.toUpperCase()}`] = checked;
    });

    return out;
  }

  function setVarsToUI(varsObj) {
    // Text inputs and textareas
    const simpleKeys = [
      "TITLE", "KEYWORDS", "INSERT_INTRO_QUESTION", 
      "INSERT_FAQ_QUESTIONS", "SOURCE", "COMPANY_NAME",
      "CALL_NUMBER", "ADDRESS", "STATE_NAME", "LINK", "COMPANY_EMPLOYEE",
      "PROMPT_FULLBLOG", "PROMPT_INTRO", "PROMPT_FINALCTA",
      "PROMPT_FULLFAQS", "PROMPT_BUSINESSDESC", "PROMPT_REFERENCES", "PROMPT_SHORTCTA"
    ];
    
    simpleKeys.forEach(k => {
      const el = document.getElementById(`VAR_${k}`);
      if (el) {
        const value = varsObj?.[k] !== undefined && varsObj?.[k] !== "" 
          ? varsObj[k] 
          : (DEFAULT_VALUES[k] || "");
        el.value = value;
      }
    });

    // Blog type
    const blogType = varsObj?.BLOGTYPE || DEFAULT_VALUES.BLOGTYPE;
    const radioEl = blogType === "Health" 
      ? document.getElementById('VAR_BLOGTYPE_HEALTH')
      : document.getElementById('VAR_BLOGTYPE_LEGAL');
    if (radioEl) radioEl.checked = true;

    // Reinitialize checkboxes based on blog type
    initBlogForExampleCheckboxes();
    initBlogPartCheckboxes();

    // Temperature
    const temp = varsObj?.TEMPERATURE || DEFAULT_VALUES.TEMPERATURE;
    const tempSlider = document.getElementById('VAR_TEMPERATURE');
    const tempValue = document.getElementById('temperatureValue');
    if (tempSlider) {
      tempSlider.value = Math.round(parseFloat(temp) * 100);
    }
    if (tempValue) {
      tempValue.textContent = temp;
    }
  }

  function loadVars() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return null;
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
    showLoading();
    const today = todayYYYYMMDD();

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
      hideLoading();
    }
  }

  function extractUserMessage(fullPrompt) {
    const lines = fullPrompt.split('\n');
    const varStartIndex = lines.findIndex(line => line.trim() === 'PROMPT_VARIABLES:');
    
    if (varStartIndex === -1) {
      return fullPrompt.trim();
    }
    
    let messageStartIndex = varStartIndex + 1;
    for (let i = varStartIndex + 1; i < lines.length; i++) {
      const line = lines[i].trim();
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
      hideLoading();
      return;
    }

    userInput.addEventListener("input", autoResize);
    messageForm.addEventListener("submit", handleSubmit);

    if (varsToggleHeader && varsPanel) {
      varsToggleHeader.addEventListener("click", toggleVarsPanel);
    }

    // Blog type change handler
    document.querySelectorAll('input[name="blogType"]').forEach(radio => {
      radio.addEventListener('change', () => {
        initBlogForExampleCheckboxes();
      });
    });

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
          setVarsToUI(DEFAULT_VALUES);
          saveVars(DEFAULT_VALUES);
          setStatus("✓ Reset to defaults");
        }
      });
    }

    // Initialize all components
    initBlogForExampleCheckboxes();
    initBlogPartCheckboxes();
    initTemperatureSlider();

    // Load saved vars OR set defaults if first time
    const savedVars = loadVars();
    if (savedVars === null) {
      setVarsToUI(DEFAULT_VALUES);
      saveVars(DEFAULT_VALUES);
    } else {
      setVarsToUI(savedVars);
    }

    autoResize();
    userInput.focus();

    loadChatHistoryForToday();
  });
})();