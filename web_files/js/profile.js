// web_files/js/profile.js
document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("loadingOverlay");
  const dateInput = document.getElementById("historyDate");
  const loadBtn = document.getElementById("loadBtn");
  const downloadBtn = document.getElementById("downloadBtn");
  const rowCount = document.getElementById("rowCount");
  const errorBox = document.getElementById("errorBox");
  const tbody = document.getElementById("historyTbody");

  let lastRows = [];

  // Default: today (YYYY-MM-DD)
  if (!dateInput.value) {
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, "0");
    const dd = String(now.getDate()).padStart(2, "0");
    dateInput.value = `${yyyy}-${mm}-${dd}`;
  }

  function showLoading(on) {
    overlay.classList.toggle("hidden", !on);
    overlay.setAttribute("aria-hidden", String(!on));
  }

  function showError(msg) {
    if (!msg) {
      errorBox.classList.add("hidden");
      errorBox.textContent = "";
      return;
    }
    errorBox.classList.remove("hidden");
    errorBox.textContent = msg;
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setEmpty(message) {
    tbody.innerHTML = `
      <tr>
        <td class="empty-cell" colspan="5">${escapeHtml(message)}</td>
      </tr>`;
  }

  function renderTable(rows) {
    lastRows = Array.isArray(rows) ? rows : [];
    rowCount.textContent = `${lastRows.length} rows`;
    downloadBtn.disabled = lastRows.length === 0;

    if (lastRows.length === 0) {
      setEmpty("No rows for the selected date.");
      return;
    }

    const html = lastRows.map(r => {
      const id = r.id ?? "";
      const entryTime = r.entry ?? "";         // timestamptz string
      const entryDate = r.entry_date ?? "";    // date string
      const userprompt = r.userprompt ?? "";
      const chatresponse = r.chatresponse ?? "";

      return `
        <tr>
          <td class="col-id">${escapeHtml(id)}</td>
          <td class="col-entrytime">${escapeHtml(entryTime)}</td>
          <td class="col-entrydate">${escapeHtml(entryDate)}</td>
          <td><div class="cell-text max-cell">${escapeHtml(userprompt)}</div></td>
          <td><div class="cell-text max-cell">${escapeHtml(chatresponse)}</div></td>
        </tr>
      `;
    }).join("");

    tbody.innerHTML = html;
  }

  function buildCsv(rows) {
    const headers = ["id", "entry", "entry_date", "userprompt", "chatresponse"];
    const esc = (v) => {
      const s = String(v ?? "");
      const needsQuotes = /[",\n\r]/.test(s);
      const safe = s.replaceAll('"', '""');
      return needsQuotes ? `"${safe}"` : safe;
    };

    const lines = [];
    lines.push(headers.join(","));
    for (const r of rows) {
      lines.push(headers.map(h => esc(r[h])).join(","));
    }
    return lines.join("\n");
  }

  function downloadCsv() {
    if (!lastRows || lastRows.length === 0) return;

    const csv = buildCsv(lastRows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `profileHistory_${dateInput.value}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function loadHistory() {
    showError("");
    setEmpty("Loading…");
    showLoading(true);

    const date = (dateInput.value || "").trim();
    if (!date) {
      showLoading(false);
      setEmpty("Select a date and click Load…");
      showError("Missing date.");
      return;
    }

    try {
      const res = await fetch(`/api/profile/history?date=${encodeURIComponent(date)}`, {
        headers: { "Accept": "application/json" }
      });

      // Always attempt to parse JSON (even on errors)
      let payload = null;
      const text = await res.text();
      try { payload = text ? JSON.parse(text) : null; } catch { payload = null; }

      if (!res.ok) {
        const code = payload?.code ? ` [${payload.code}]` : "";
        const msg = payload?.message || payload?.error || `Request failed with ${res.status}`;
        renderTable([]);
        showError(`${msg}${code}`);
        return;
      }

      // Success payload expected: { success:true, rows:[...] }
      const rows = payload?.rows || [];
      renderTable(rows);

      // Show extra diagnostics if present
      if (payload?.success === false) {
        showError(payload.message || payload.error || "Unknown error.");
      }

    } catch (err) {
      renderTable([]);
      showError(err?.message || "Failed to load history.");
    } finally {
      showLoading(false);
    }
  }

  loadBtn.addEventListener("click", loadHistory);
  downloadBtn.addEventListener("click", downloadCsv);
});

