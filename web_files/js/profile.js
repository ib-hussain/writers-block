(function () {
  const overlay = document.getElementById("loadingOverlay");
  const dateInput = document.getElementById("historyDate");
  const loadBtn = document.getElementById("loadBtn");
  const downloadBtn = document.getElementById("downloadBtn");
  const csvBox = document.getElementById("csvBox");
  const rowCount = document.getElementById("rowCount");
  const errorBox = document.getElementById("errorBox");

  function showLoading() {
    overlay.classList.remove("hidden");
    overlay.setAttribute("aria-hidden", "false");
  }
  function hideLoading() {
    overlay.classList.add("hidden");
    overlay.setAttribute("aria-hidden", "true");
  }

  async function fetchJSON(url) {
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || `Request failed: ${res.status}`);
    }
    return res.json();
  }

  function toCsvValue(v) {
    const s = String(v ?? "");
    if (s.includes('"') || s.includes(",") || s.includes("\n") || s.includes("\r")) {
      return `"${s.replaceAll('"', '""')}"`;
    }
    return s;
  }

  function rowsToCSV(rows) {
    const header = ["id", "entry_date", "entry", "Userprompt", "chatResponse"];
    const lines = [header.join(",")];
    for (const r of rows) {
      const line = header.map(h => toCsvValue(r[h])).join(",");
      lines.push(line);
    }
    return lines.join("\n");
  }

  function downloadCSV(filename, csvText) {
    const blob = new Blob([csvText], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function loadHistory() {
    const d = dateInput.value;
    errorBox.classList.add("hidden");
    downloadBtn.disabled = true;

    if (!d) {
      errorBox.textContent = "Please select a date first.";
      errorBox.classList.remove("hidden");
      return;
    }

    showLoading();
    try {
      const payload = await fetchJSON(`/api/profile/history?date=${encodeURIComponent(d)}`);
      const rows = payload.rows || [];
      rowCount.textContent = `${rows.length} rows`;

      const csvText = rowsToCSV(rows);
      csvBox.value = csvText;

      downloadBtn.disabled = rows.length === 0;
      downloadBtn.onclick = () => downloadCSV(`profileHistory_${d}.csv`, csvText);
    } catch (e) {
      errorBox.textContent = e?.message || "Unknown error";
      errorBox.classList.remove("hidden");
    } finally {
      hideLoading();
    }
  }

  // default date: today
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, "0");
  const dd = String(today.getDate()).padStart(2, "0");
  dateInput.value = `${yyyy}-${mm}-${dd}`;

  loadBtn.addEventListener("click", loadHistory);

  // Optional: auto-load on change
  dateInput.addEventListener("change", loadHistory);
})();
