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

  // NOTE: You asked to keep the SAME keywords for legal + health: unchanged.
  const DEFAULT_VALUES = {
    "KEYWORDS": "lawyer, attorney, consultation, claim, accident, case, insurance, insurance company, evidence, police report, medical records, witness statements, compensation, damages, liability, settlement, legal process, statute limitations, comparative negligence, policy limits, contingency fee, trial, litigation, negotiation, expert witnesses, accident reconstruction, dashcam footage, surveillance footage, medical bills, total loss, gap",
    "BLOGTYPE": "Legal",
    "TEMPERATURE": "0.70",
    "BLOGFOREXAMPLE": [],
    "BLOGPART_INTRO": [],
    "BLOGPART_FINALCTA": [],
    "BLOGPART_FAQS": [],
    "BLOGPART_BUSINESSDESC": [],
    "BLOGPART_SHORTCTA": [],
    "PROMPT_FULLBLOG": `We are writing a clear, SEO-optimised article titled "{TITLE}". This article must directly answer each header in the very first sentence of each relevant section. Then, it should go into specific, well-researched, and helpful details.

You MUST use all of the following keywords naturally throughout the article:
"{KEYWORDS}"

* Use these keywords even when paraphrasing.
* Do not skip any keyword throughout the entire article.
* Use an active voice, and avoid passive voice unless absolutely necessary.
* Always keep sentences short or split them when needed.
* Use strong transitions.
* Support points with real-world facts, examples, or data.
* Each paragraph must begin with a direct, clear answer.
* The tone should be informative, direct, and easy to follow.

I have given the headers (outline sections). You will expand them with strong content, following these rules for the entire article.

This should be the example format: {BLOGFOREXAMPLE}`,
    "PROMPT_INTRO": `Write intro answering the question: {INSERT_INTRO_QUESTION}. Provide two paragraphs, each 60 words. The first paragraph must give a direct and relevant answer to the question, using short, active sentences, smooth transitions, and easy-to-follow language. The second paragraph must be a strong call to action, connected naturally to the topic. Write in the second person. Keep every sentence under 15 words for readability. Use a Flesch Reading Score–friendly style.

This should be the format: {BLOGPART_INTRO}`,
    "PROMPT_FINALCTA": `Write a two-paragraph call to action. Each paragraph must have 70 words. The first paragraph should explain the problems the reader faces based on the topic. The second paragraph should explain how we can help resolve those problems. In the second paragraph, you must use the name, phone number, and location given in the reference. Write in the second person, keep every sentence under 15 words, and use transition words for smooth flow. Keep the tone clear, active, and easy to follow for a high Flesch Reading Score.

This should be the format: {BLOGPART_FINALCTA}`,
    "PROMPT_FULLFAQS": `Answer the following FAQs clearly and directly, using the following formatting and content rules:
{INSERT_FAQ_QUESTIONS}

Each question should be formatted as an H4 with bold text and Title Case.
Seamlessly integrate the following keywords wherever relevant and natural: {KEYWORDS}

* Answer length should be between 60 to 70 words.
* Begin with a direct answer (e.g., "Yes," or "No," if applicable), followed by a clear explanation.
* Use an active voice throughout.
* Use strong transitions between ideas and connect sentences smoothly.
* If a sentence becomes long, break it using a short, clear transition or supporting sentence.
* Do not include fluff or filler. Every sentence must add value and connect logically.
* Make the tone informative and easy to follow without oversimplifying medical or legal terms.
* Avoid sudden info dumps; flow should be natural and progressive.
* Make sure no sentence or idea feels out of place or rushed.
* Use real medical and legal insight where needed, and avoid vague or generic statements.
* Do not overuse any keyword or repeat the same idea unnecessarily.
* All the sentences should only answer the question, no other irrelevant info.

This should be the format: {BLOGPART_FAQS}`,
    "PROMPT_BUSINESSDESC": `Write a business description based on the title: {TITLE}. Start with a direct 70-word opening paragraph that answers the question clearly. Then, include six bullet points in the middle, each 15 words long, highlighting symptoms, risks, steps, legal options or key details connected to the topic. After the bullets, write a closing 70-word paragraph explaining how we can help. Use second person, active voice, and short sentences under 15 words. Add smooth transitions for flow and ensure a high Flesch Reading Score.

This is an example: {BLOGPART_BUSINESSDESC}`,
    "PROMPT_REFERENCES": `When integrating references, only use credible, trustworthy sources such as government sites, universities, medical journals, legal journals, or recognized organizations. Do not use competitors or promotional sources. Introduce the reference naturally with phrases like 'According to {SOURCE}' or 'A study by {SOURCE} found…'. Keep sentences short, active, and easy to follow. Use references to support key points, not overwhelm the reader. Include at least 3–4 references throughout the blog, but use more if needed for accuracy. At the end, provide the full source in a consistent format.

This should be the format:
For Legal Blogs:
1. According to NIH research, anxiety and traumatic stress symptoms are common after a car crash. In a study of 62 hospitalized patients, 55% reported moderate to severe anxiety.
2. For instance, a case study on NCBI revealed that a 27-year-old woman developed severe neurological problems after a side-impact car accident. Despite regular CT scans, an MRI later showed severe C1/C2 joint damage.

For Health Blogs:
1. According to NIH, vibration therapy (VT) improves neuromuscular performance by increasing strength, power, and kinesthetic awareness. According to PubMed, smoking increases the risk of cartilage loss. By avoiding smoking, you protect your cartilage, allowing tissues to heal better and respond more effectively to exercises.
2. According to the NIH, a review of 26 studies showed that past lower extremity injuries raise the risk of reinjury. These studies showed that previous anterior cruciate ligament tears often lead to repeated ACL injuries or other leg problems.`,
    "PROMPT_SHORTCTA": `Write a short 2–3 line call to action that directly connects to the problems discussed in the section. Emphasize how our doctors or lawyers can help the reader manage those challenges. Keep sentences short, active, and easy to follow. Avoid using our name, phone number, or location. Only use phrases like contact us or reach out to us naturally within the text.

This should be the format: {BLOGPART_SHORTCTA}`
  };

  // Version the localstorage key so you can invalidate older broken saved state if needed
  const LS_KEY = "wb_prompt_vars_v2";

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

  function initBlogForExampleCheckboxes() {
    const blogType = document.querySelector('input[name="blogType"]:checked')?.value || "Legal";
    const container = document.getElementById("blogForExampleContainer");
    container.innerHTML = "";

    const start = blogType === "Legal" ? 11 : 1;
    const end = blogType === "Legal" ? 20 : 10;

    for (let i = start; i <= end; i++) {
      const label = document.createElement("label");
      label.className = "checkbox-label";
      label.innerHTML = `
        <input type="checkbox" name="blogForExample" value="${i}" />
        <span>Blog ${i}</span>
      `;
      container.appendChild(label);

      const checkbox = label.querySelector('input');
      checkbox.addEventListener('change', () => {
        handleCheckboxLimit('blogForExample', 10);
        updateCheckboxStyles('blogForExample');
      });
    }

    const saved = loadVars();
    if (saved && saved.BLOGFOREXAMPLE) {
      saved.BLOGFOREXAMPLE.forEach(val => {
        const cb = container.querySelector(`input[value="${val}"]`);
        if (cb) cb.checked = true;
      });
    }
    updateCheckboxStyles('blogForExample');
  }

  function initBlogPartCheckboxes() {
    const blogType = document.querySelector('input[name="blogType"]:checked')?.value || "Legal";
    const sections = ['Intro', 'FinalCTA', 'FAQs', 'BusinessDesc', 'ShortCTA'];

    const start = blogType === "Legal" ? 11 : 1;
    const end = blogType === "Legal" ? 20 : 10;

    sections.forEach(section => {
      const container = document.getElementById(`example${section}`);
      if (!container) return;

      container.innerHTML = "";

      for (let i = start; i <= end; i++) {
        const label = document.createElement("label");
        label.className = "checkbox-label";
        label.innerHTML = `
          <input type="checkbox" name="blogPart${section}" value="${i}" />
          <span>${i}</span>
        `;
        container.appendChild(label);

        const checkbox = label.querySelector('input');
        checkbox.addEventListener('change', () => {
          handleCheckboxLimit(`blogPart${section}`, 10);
          updateCheckboxStyles(`blogPart${section}`);
        });
      }
    });

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

  function handleCheckboxLimit(name, max) {
    const checkboxes = document.querySelectorAll(`input[name="${name}"]`);
    const checked = Array.from(checkboxes).filter(cb => cb.checked);

    if (checked.length > max) {
      checked[checked.length - 1].checked = false;
    }
  }

  function updateCheckboxStyles(name) {
    const checkboxes = document.querySelectorAll(`input[name="${name}"]`);
    checkboxes.forEach(cb => {
      const label = cb.closest('.checkbox-label');
      if (cb.checked) label.classList.add('checked');
      else label.classList.remove('checked');
    });
  }

  function initTemperatureSlider() {
    const slider = document.getElementById('VAR_TEMPERATURE');
    const valueDisplay = document.getElementById('temperatureValue');
    if (!slider || !valueDisplay) return;

    slider.addEventListener('input', (e) => {
      const value = (parseInt(e.target.value) / 100).toFixed(2);
      valueDisplay.textContent = value;
    });

    const saved = loadVars();
    if (saved && saved.TEMPERATURE) {
      const percent = Math.round(parseFloat(saved.TEMPERATURE) * 100);
      slider.value = percent;
      valueDisplay.textContent = saved.TEMPERATURE;
    }
  }

  function getVarsFromUI() {
    const out = {};
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

    const blogTypeRadio = document.querySelector('input[name="blogType"]:checked');
    out.BLOGTYPE = blogTypeRadio ? blogTypeRadio.value : "Legal";

    const tempSlider = document.getElementById('VAR_TEMPERATURE');
    if (tempSlider) out.TEMPERATURE = (parseInt(tempSlider.value) / 100).toFixed(2);

    out.BLOGFOREXAMPLE = Array.from(document.querySelectorAll('input[name="blogForExample"]:checked'))
      .map(cb => cb.value);

    const sections = ['Intro', 'FinalCTA', 'FAQs', 'BusinessDesc', 'ShortCTA'];
    sections.forEach(section => {
      const checked = Array.from(document.querySelectorAll(`input[name="blogPart${section}"]:checked`))
        .map(cb => cb.value);
      out[`BLOGPART_${section.toUpperCase()}`] = checked;
    });

    return out;
  }

  function setVarsToUI(varsObj) {
    const simpleKeys = [
      "TITLE", "KEYWORDS", "INSERT_INTRO_QUESTION",
      "INSERT_FAQ_QUESTIONS", "SOURCE", "COMPANY_NAME",
      "CALL_NUMBER", "ADDRESS", "STATE_NAME", "LINK", "COMPANY_EMPLOYEE",
      "PROMPT_FULLBLOG", "PROMPT_INTRO", "PROMPT_FINALCTA",
      "PROMPT_FULLFAQS", "PROMPT_BUSINESSDESC", "PROMPT_REFERENCES", "PROMPT_SHORTCTA"
    ];

    simpleKeys.forEach(k => {
      const el = document.getElementById(`VAR_${k}`);
      if (!el) return;
      const value = varsObj?.[k] !== undefined && varsObj?.[k] !== ""
        ? varsObj[k]
        : (DEFAULT_VALUES[k] || "");
      el.value = value;
    });

    const blogType = varsObj?.BLOGTYPE || DEFAULT_VALUES.BLOGTYPE;
    const radioEl = blogType === "Health"
      ? document.getElementById('VAR_BLOGTYPE_HEALTH')
      : document.getElementById('VAR_BLOGTYPE_LEGAL');
    if (radioEl) radioEl.checked = true;

    initBlogForExampleCheckboxes();
    initBlogPartCheckboxes();

    const temp = varsObj?.TEMPERATURE || DEFAULT_VALUES.TEMPERATURE;
    const tempSlider = document.getElementById('VAR_TEMPERATURE');
    const tempValue = document.getElementById('temperatureValue');
    if (tempSlider) tempSlider.value = Math.round(parseFloat(temp) * 100);
    if (tempValue) tempValue.textContent = temp;
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
    if (msg) setTimeout(() => { varsStatus.textContent = ""; }, 1800);
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
      hideLoading();
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

    // Debug summary (client-side)
    console.log("[chatbot.js] sending /api/chat", {
      messageChars: msg.length,
      blogType: varsObj.BLOGTYPE,
      temperature: varsObj.TEMPERATURE,
      examples: {
        full: (varsObj.BLOGFOREXAMPLE || []).length,
        intro: (varsObj.BLOGPART_INTRO || []).length,
        faqs: (varsObj.BLOGPART_FAQS || []).length
      }
    });

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

    if (varsToggleHeader && varsPanel) varsToggleHeader.addEventListener("click", () => toggleVarsPanel());

    document.querySelectorAll('input[name="blogType"]').forEach(radio => {
      radio.addEventListener('change', () => {
        initBlogForExampleCheckboxes();
        initBlogPartCheckboxes();
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

    initBlogForExampleCheckboxes();
    initBlogPartCheckboxes();
    initTemperatureSlider();

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
