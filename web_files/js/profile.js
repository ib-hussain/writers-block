// web_files/js/profile.js
document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("loadingOverlay");
  const dateInput = document.getElementById("historyDate");
  const loadBtn = document.getElementById("loadBtn");
  const downloadBtn = document.getElementById("downloadBtn");
  const rowCount = document.getElementById("rowCount");
  const errorBox = document.getElementById("errorBox");

  const thead = document.getElementById("historyThead");
  const tbody = document.getElementById("historyTbody");

  let lastRows = [];

  // default to today
  if (!dateInput.value) {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, "0");
    const dd = String(today.getDate()).padStart(2, "0");
    dateInput.value = `${yyyy}-${mm}-${dd}`;
  }

  function showLoading(isOn) {
    overlay.classList.toggle("hidden", !isOn);
    overlay.setAttribute("aria-hidden", String(!isOn));
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

  function setRowCount(n) {
    rowCount.textContent = `${n} row${n === 1 ? "" : "s"}`;
  }

  function escapeCSV(val) {
    if (val === null || val === undefined) return "";
    const s = String(val);
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  }

  function rowsToCSV(rows, columns) {
    const header = columns.join(",");
    const body = rows.map(r => columns.map(c => escapeCSV(r[c])).join(",")).join("\n");
    return `${header}\n${body}\n`;
  }

  function renderTable(rows) {
    tbody.innerHTML = "";
    thead.innerHTML = "";

    lastRows = rows || [];
    setRowCount(lastRows.length);

    if (!lastRows.length) {
      downloadBtn.disabled = true;
      tbody.innerHTML = `<tr><td class="empty-cell">No rows for this date.</td></tr>`;
      return;
    }

    downloadBtn.disabled = false;

    // Use keys from first row (RealDictCursor order is stable)
    const columns = Object.keys(lastRows[0]);

    // THEAD
    const trh = document.createElement("tr");
    columns.forEach(col => {
      const th = document.createElement("th");
      th.textContent = col;
      trh.appendChild(th);
    });
    thead.appendChild(trh);

    // TBODY
    lastRows.forEach(r => {
      const tr = document.createElement("tr");
      columns.forEach(col => {
        const td = document.createElement("td");
        const v = r[col];

        // Render long text as readable
        td.textContent = (v === null || v === undefined) ? "" : String(v);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  async function loadHistory() {
    const d = (dateInput.value || "").trim();
    showError("");

    if (!d) {
      showError("Please pick a date.");
      return;
    }

    showLoading(true);
    try {
      const res = await fetch(`/api/profile/history?date=${encodeURIComponent(d)}`);
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || `Request failed (${res.status})`);
      }
      const data = await res.json();
      renderTable(data.rows || []);
    } catch (err) {
      renderTable([]);
      showError(err.message || "Failed to load history.");
    } finally {
      showLoading(false);
    }
  }


  loadBtn.addEventListener("click", loadHistory);
});
