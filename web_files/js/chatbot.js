document.addEventListener("DOMContentLoaded", function() {
    // DOM Elements
    const messageForm = document.getElementById('message-form');
    const userInput = document.getElementById('user-input');
    const DEFAULT_PLACEHOLDER = userInput.placeholder || "Type your message...";
    const sendBtn = document.getElementById('send-btn');
    const chatMessages = document.getElementById('chat-messages');
    // State
    let isTyping = false;
    // Auto-resize functionality for textarea
    function autoResize() {
        userInput.style.height = 'auto';
        userInput.style.height = Math.max(70, Math.min(userInput.scrollHeight, 150)) + 'px';
    }
    // Initialize auto-resize
    userInput.addEventListener('input', autoResize);
    
    // Handle Enter key behavior
    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && e.shiftKey) {
            userInput.value += "";
            autoResize();
        }else if (e.key === 'Enter' ) {
            e.preventDefault();
            messageForm.dispatchEvent(new Event('submit'));
        }
    });
    
    // Events
    messageForm.addEventListener('submit', handleMessageSubmit);

    // ===== Chat History Loader =====
async function loadChatHistory() {

}
// Kick off history load after bootstrapping the page
loadChatHistory();


    // ----- Send text (and maybe image) -----
    async function handleMessageSubmit(e) {
        
    }
    // ----- UI helpers -----
    function showSpinnerOn(btn) {
        btn.disabled = true;
        btn.dataset.prev = btn.innerHTML;
        btn.innerHTML = '<div class="spinner"></div>';
    }
    function hideSpinnerOn(btn) {
        if (!btn.dataset.prev) return;
        btn.disabled = false;
        btn.innerHTML = btn.dataset.prev;
        delete btn.dataset.prev;
    }

    function setInputState(enabled) {
        userInput.disabled = !enabled;
        sendBtn.disabled = !enabled;
        userInput.placeholder = enabled ? "Type your message..." : "Please wait...";
    }

    function addMessage(text, className) {
        if (!text && className !== 'bot-message') return;
        const div = document.createElement('div');
        div.classList.add('message', className);
        div.innerHTML = className === 'bot-message'
            ? parseMarkdown(text || '')
            : (text || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        chatMessages.appendChild(div);
        scrollToBottom();
    }


    function parseMarkdown(md) {
        if (!md) return "";
        md = String(md).replace(/\r\n/g, "\n");

        const lines = md.split("\n");
        let html = "";
        const listStack = []; // stack of {type: 'ul'|'ol', indent: number}
        let inP = false;

        const escapeHtml = s => s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
        const inlineFormat = txt => {
            txt = escapeHtml(txt);
            txt = txt.replace(/`([^`]+)`/g, "<code>$1</code>");
            txt = txt.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
            txt = txt.replace(/(^|[^*])\*(?!\s)([^*]+?)\*(?!\w)/g, "$1<em>$2</em>");
            return txt;
        };
        const closeParagraph = () => { if (inP) { html += "</p>"; inP = false; } };
        const closeListsToIndent = (indent) => {
            while (listStack.length && listStack[listStack.length - 1].indent >= indent) {
                const { type } = listStack.pop();
                html += (type === "ul" ? "</ul>" : "</ol>");
            }
        };
        const openListIfNeeded = (type, indent) => {
            // if same type & indent exists, keep; else open new
            if (!listStack.length || listStack[listStack.length - 1].indent < indent || listStack[listStack.length - 1].type !== type) {
                listStack.push({ type, indent });
                html += (type === "ul" ? "<ul>" : "<ol>");
            }
        };
        const closeAllLists = () => closeListsToIndent(0);

        for (let i = 0; i < lines.length; i++) {
            const raw = lines[i];
            if (raw.trim() === "") {
                closeParagraph();
                closeAllLists();
                continue;
            }

            // Headings: **Title** alone or #, ##, ...
            const boldHeading = raw.trim().match(/^\*\*(.+?)\*\*$/);
            if (boldHeading) {
                closeParagraph(); closeAllLists();
                html += `<h3>${inlineFormat(boldHeading[1])}</h3>`;
                continue;
            }
            const atx = raw.match(/^(\s*)(#{1,6})\s+(.*)$/);
            if (atx) {
                closeParagraph(); closeAllLists();
                const level = Math.min(6, atx[2].length);
                html += `<h${level}>${inlineFormat(atx[3].trim())}</h${level}>`;
                continue;
            }

            // Lists: support *, -, + and numbered (with indentation)
            const liMatch = raw.match(/^(\s*)([*+\-]|\d+\.)\s+(.*)$/);
            if (liMatch) {
                const indent = liMatch[1].length; // number of leading spaces
                const marker = liMatch[2];
                const content = liMatch[3];

                closeParagraph();

                const isOrdered = /^\d+\.$/.test(marker);
                const type = isOrdered ? "ol" : "ul";

                // adjust nesting
                if (!listStack.length || indent > listStack[listStack.length - 1].indent) {
                    openListIfNeeded(type, indent);
                } else if (indent < listStack[listStack.length - 1].indent || listStack[listStack.length - 1].type !== type) {
                    closeListsToIndent(indent + (isOrdered ? 0 : 0));
                    openListIfNeeded(type, indent);
                } else {
                    // same level & type -> nothing to open/close
                }

                html += `<li>${inlineFormat(content.trim())}</li>`;
                continue;
            }

            // Paragraphs (join consecutive lines with <br>)
            closeAllLists();
            if (!inP) { html += "<p>"; inP = true; html += inlineFormat(raw.trim()); }
            else { html += "<br>" + inlineFormat(raw.trim()); }
        }

        // tidy up
        if (inP) html += "</p>";
        closeAllLists();
        return html;
    }


    function addTypingIndicator() {
        const typing = document.createElement('div');
        typing.classList.add('typing-indicator');
        typing.innerHTML = `
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>`;
        chatMessages.appendChild(typing);
        scrollToBottom();
        return typing;
    }

    function scrollToBottom() {
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }
});