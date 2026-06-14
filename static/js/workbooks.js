/* workbooks.js — handles both the workbook list page and workbook detail/sheet-manager page */
document.addEventListener("DOMContentLoaded", function () {

  // ── Toast ─────────────────────────────────────────────────────────────────
  function toast(msg, type) {
    let c = document.getElementById("toast-container");
    if (!c) {
      c = document.createElement("div");
      c.id = "toast-container";
      c.className = "fixed top-5 right-5 z-50 space-y-2 pointer-events-none";
      document.body.appendChild(c);
    }
    const t = document.createElement("div");
    t.className = [
      "p-4 rounded-xl shadow-lg border text-xs font-bold flex items-center justify-between pointer-events-auto",
      "transition-all duration-300 transform translate-y-2 opacity-0",
      type === "error"   ? "bg-rose-50 border-rose-200 text-rose-800"
        : type === "warn" ? "bg-amber-50 border-amber-200 text-amber-800"
        : "bg-emerald-50 border-emerald-200 text-emerald-800",
    ].join(" ");
    t.innerHTML = `<span>${msg}</span><button class="ml-4 font-normal text-slate-400 hover:text-slate-600">✕</button>`;
    t.querySelector("button").onclick = () => t.remove();
    c.appendChild(t);
    setTimeout(() => t.classList.remove("translate-y-2", "opacity-0"), 10);
    setTimeout(() => { t.classList.add("translate-y-2", "opacity-0"); setTimeout(() => t.remove(), 300); }, 4000);
  }

  function slugify(s) {
    return (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  }

  function esc(s) {
    return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ══════════════════════════════════════════════════════════════════════════
  // LIST PAGE  (/workbooks/)
  // ══════════════════════════════════════════════════════════════════════════
  const grid      = document.getElementById("workbooks-grid");
  const btnCreate = document.getElementById("btn-create-workbook");
  const modal     = document.getElementById("modal-create-wb");
  const formCW    = document.getElementById("form-create-wb");
  const wbName    = document.getElementById("wb-name");
  const wbDesc    = document.getElementById("wb-description");
  const wbCodePrv = document.getElementById("wb-code-preview");

  if (grid && btnCreate) {
    // List page
    loadWorkbooks();

    btnCreate.onclick = () => {
      wbName.value = "";
      if (wbDesc) wbDesc.value = "";
      if (wbCodePrv) wbCodePrv.textContent = "";
      modal.classList.remove("hidden");
      setTimeout(() => wbName.focus(), 50);
    };

    document.getElementById("btn-close-create-wb").onclick =
    document.getElementById("btn-cancel-create-wb").onclick = () => modal.classList.add("hidden");

    if (wbName && wbCodePrv) {
      wbName.addEventListener("input", () => {
        const code = slugify(wbName.value);
        wbCodePrv.textContent = code ? "Code: " + code : "";
      });
    }

    if (formCW) {
      formCW.onsubmit = async (e) => {
        e.preventDefault();
        const name = wbName.value.trim();
        if (!name) return;
        const code = slugify(name);
        if (!code) { toast("Cannot generate a code from that name.", "error"); return; }
        const submitBtn = formCW.querySelector("button[type=submit]");
        submitBtn.disabled = true;
        submitBtn.textContent = "Creating…";
        try {
          const res = await fetch("/workbooks/api", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, code, description: wbDesc ? wbDesc.value.trim() : "" }),
          });
          const d = await res.json();
          if (d.error) { toast(d.error, "error"); }
          else {
            modal.classList.add("hidden");
            toast("Workbook created.");
            window.location.href = "/workbooks/" + d.data.id;
          }
        } catch { toast("Failed to create workbook.", "error"); }
        finally { submitBtn.disabled = false; submitBtn.textContent = "Create →"; }
      };
    }
  }

  function loadWorkbooks() {
    fetch("/workbooks/api")
      .then(r => r.json())
      .then(renderWorkbooks)
      .catch(() => {
        grid.innerHTML = '<div class="md:col-span-2 xl:col-span-3 text-center text-rose-500 text-sm py-10">Failed to load workbooks.</div>';
      });
  }

  function renderWorkbooks(data) {
    if (!data.length) {
      grid.innerHTML = `
        <div class="md:col-span-2 xl:col-span-3 rounded-xl border border-slate-200 bg-white shadow-sm p-14 text-center space-y-4">
          <svg class="h-12 w-12 text-slate-300 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <p class="text-sm font-semibold text-slate-700">No workbooks yet.</p>
          <p class="text-xs text-slate-400">Create a workbook to start building your data collection template.</p>
          <button id="empty-create-btn"
            class="inline-flex items-center px-4 py-2 bg-[#1a3a6b] hover:bg-[#1e4280] text-white text-sm font-semibold rounded-lg shadow transition">
            + Create Workbook
          </button>
        </div>`;
      const eb = document.getElementById("empty-create-btn");
      if (eb && btnCreate) eb.onclick = () => btnCreate.click();
      return;
    }

    grid.innerHTML = "";
    data.forEach(wb => {
      const statusColor =
        wb.status === "published" ? "bg-emerald-100 text-emerald-700"
          : "bg-amber-100 text-amber-700";
      const card = document.createElement("div");
      card.className = "rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden hover:shadow-md transition-shadow";
      card.innerHTML = `
        <div class="px-5 py-4 space-y-2">
          <div class="flex items-start justify-between gap-2">
            <h3 class="font-bold text-slate-800 text-sm leading-snug">${esc(wb.name)}</h3>
            <span class="shrink-0 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${statusColor}">${esc(wb.status)}</span>
          </div>
          <p class="text-[10px] font-mono text-slate-400">${esc(wb.code)}</p>
          ${wb.description ? `<p class="text-xs text-slate-500 line-clamp-2">${esc(wb.description)}</p>` : ""}
          <div class="flex items-center space-x-4 pt-1">
            <span class="text-xs text-slate-500">Sheets: <strong>${wb.sheet_count}</strong></span>
            <span class="text-xs text-slate-500">Fields: <strong>${wb.field_count}</strong></span>
          </div>
        </div>
        <div class="px-5 py-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
          <a href="/workbooks/${wb.id}"
            class="text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:underline">
            Edit →
          </a>
          <div class="relative group">
            <button class="text-slate-400 hover:text-slate-700 p-1 rounded" title="More options">•••</button>
            <div class="absolute right-0 bottom-8 hidden group-hover:block bg-white border border-slate-200 rounded-lg shadow-lg py-1 min-w-[140px] z-10">
              <button class="deactivate-btn block w-full text-left px-4 py-2 text-xs text-rose-600 hover:bg-rose-50"
                data-id="${wb.id}">Deactivate</button>
            </div>
          </div>
        </div>`;
      card.querySelector(".deactivate-btn").onclick = async (e) => {
        const id = e.currentTarget.dataset.id;
        if (!confirm("Deactivate this workbook? It will be removed from the list.")) return;
        try {
          const r = await fetch(`/workbooks/api/${id}/deactivate`, { method: "POST" });
          const d = await r.json();
          if (d.error) toast(d.error, "error");
          else { toast("Workbook deactivated.", "warn"); loadWorkbooks(); }
        } catch { toast("Failed.", "error"); }
      };
      grid.appendChild(card);
    });
  }


  // ══════════════════════════════════════════════════════════════════════════
  // DETAIL PAGE  (/workbooks/<id>)
  // ══════════════════════════════════════════════════════════════════════════
  const sheetsGrid  = document.getElementById("sheets-grid");
  const btnAddSheet = document.getElementById("btn-add-sheet");

  if (sheetsGrid && typeof WORKBOOK_ID !== "undefined") {
    loadSheets();

    // ── Workbook Preview modal ────────────────────────────────────────────
    const btnPreview      = document.getElementById("btn-preview-workbook");
    const previewModal    = document.getElementById("modal-wb-preview");
    const previewBackdrop = document.getElementById("wb-preview-backdrop");
    const previewClose    = document.getElementById("wb-preview-close");
    const previewTabs     = document.getElementById("wb-preview-tabs");
    const previewEmpty    = document.getElementById("wb-preview-empty");
    const previewTableWrap = document.getElementById("wb-preview-table-wrap");
    const previewHead     = document.getElementById("wb-preview-head");
    const previewBody     = document.getElementById("wb-preview-body");

    function applyTabStyle(tab, active) {
      tab.style.cssText = [
        "font-size:13px",
        "padding:10px 14px",
        "border:none",
        "background:none",
        "cursor:pointer",
        "white-space:nowrap",
        "border-bottom:2px solid " + (active ? "#1a3a6b" : "transparent"),
        "color:"        + (active ? "#1a3a6b" : "#64748b"),
        "font-weight:"  + (active ? "600"     : "400"),
        "transition:color .15s,border-color .15s",
      ].join(";");
    }

    function resetPreview(msg) {
      previewEmpty.textContent = msg || "Loading sheet preview…";
      previewEmpty.classList.remove("hidden");
      previewTableWrap.classList.add("hidden");
      if (previewHead) previewHead.innerHTML = "";
      if (previewBody) previewBody.innerHTML = "";
    }

    function loadSheetPreview(sheet) {
      resetPreview("Loading sheet preview…");
      if (!sheet.latest_version_id) {
        resetPreview("This sheet has no version yet.");
        return;
      }
      fetch(`/module/FORMBLD/forms/${sheet.form_id}/preview-spoc?version_id=${sheet.latest_version_id}`)
        .then(r => { if (!r.ok) throw new Error("Failed to load preview."); return r.json(); })
        .then(ctx => {
          previewEmpty.classList.add("hidden");
          previewTableWrap.classList.remove("hidden");
          if (!window.WorkbookSheet) throw new Error("WorkbookSheet renderer not loaded.");
          window.WorkbookSheet.render({
            mode: "calc_results",
            headEl: previewHead,
            bodyEl: previewBody,
            fields: ctx.fields || [],
            sections: ctx.sections || [],
            workbookValues: ctx.workbook_values || {},
            rows: ctx.rows || [],
            selectedRowKey: null,
          });
        })
        .catch(err => { resetPreview(err.message || "Failed to load sheet preview."); });
    }

    function renderPreviewTabs(sheets) {
      previewTabs.innerHTML = "";
      sheets.forEach((sheet, i) => {
        const tab = document.createElement("button");
        tab.textContent = sheet.sheet_label;
        tab.type = "button";
        applyTabStyle(tab, i === 0);
        tab.onclick = () => {
          previewTabs.querySelectorAll("button").forEach(b => applyTabStyle(b, false));
          applyTabStyle(tab, true);
          loadSheetPreview(sheet);
        };
        previewTabs.appendChild(tab);
      });
    }

    function openPreviewModal() {
      previewModal.classList.remove("hidden");
      resetPreview("Loading sheet preview…");
      previewTabs.innerHTML = "";
      fetch(`/workbooks/api/${WORKBOOK_ID}/preview`)
        .then(r => { if (!r.ok) throw new Error(); return r.json(); })
        .then(sheets => {
          if (!sheets.length) { resetPreview("No sheets in this workbook yet."); return; }
          renderPreviewTabs(sheets);
          loadSheetPreview(sheets[0]);
        })
        .catch(() => resetPreview("Failed to load workbook preview."));
    }

    btnPreview.onclick    = openPreviewModal;
    previewClose.onclick  = () => previewModal.classList.add("hidden");
    previewBackdrop.onclick = () => previewModal.classList.add("hidden");

    // ── Add Sheet panel ───────────────────────────────────────────────────
    const panel         = document.getElementById("panel-add-sheet");
    const backdrop      = document.getElementById("panel-backdrop");
    const btnClosePanel = document.getElementById("btn-close-add-sheet");
    const sheetLabel    = document.getElementById("add-sheet-label");
    const sheetSearch   = document.getElementById("add-sheet-search");
    const formsList     = document.getElementById("addable-forms-list");

    let allAddable = [];

    function openPanel() {
      panel.classList.remove("hidden");
      if (sheetLabel) sheetLabel.value = "";
      if (sheetSearch) sheetSearch.value = "";
      fetch(`/workbooks/api/${WORKBOOK_ID}/addable-forms`)
        .then(r => r.json())
        .then(data => {
          allAddable = data;
          renderAddable(data);
        })
        .catch(() => { formsList.innerHTML = '<p class="text-xs text-rose-500 text-center py-6">Failed to load forms.</p>'; });
    }

    function closePanel() { panel.classList.add("hidden"); }

    btnAddSheet.onclick    = openPanel;
    backdrop.onclick       = closePanel;
    btnClosePanel.onclick  = closePanel;

    if (sheetSearch) {
      sheetSearch.addEventListener("input", () => {
        const q = sheetSearch.value.toLowerCase();
        renderAddable(allAddable.filter(f => f.name.toLowerCase().includes(q) || f.code.toLowerCase().includes(q)));
      });
    }

    function renderAddable(forms) {
      formsList.innerHTML = "";
      if (!forms.length) {
        formsList.innerHTML = '<p class="text-xs text-slate-400 italic text-center py-6">No matching forms.</p>';
        return;
      }
      forms.forEach(f => {
        const statusColor =
          f.latest_version_status === "Published" ? "bg-emerald-100 text-emerald-700"
            : "bg-amber-100 text-amber-700";
        const btn = document.createElement("button");
        btn.className = "w-full text-left px-4 py-3 rounded-lg hover:bg-indigo-50 border border-transparent hover:border-indigo-200 transition-colors";
        btn.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="font-semibold text-sm text-slate-800">${esc(f.name)}</span>
            ${f.latest_version_status ? `<span class="shrink-0 text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${statusColor}">${esc(f.latest_version_status)}</span>` : ""}
          </div>
          <span class="text-[10px] font-mono text-slate-400">${esc(f.code)}</span>`;
        btn.onclick = async () => {
          btn.disabled = true;
          btn.classList.add("opacity-50");
          try {
            const label = sheetLabel ? sheetLabel.value.trim() : "";
            const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/sheets/add`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ form_id: f.id, sheet_label: label || null }),
            });
            const d = await r.json();
            if (d.error) { toast(d.error, "error"); btn.disabled = false; btn.classList.remove("opacity-50"); }
            else { toast("Sheet added."); closePanel(); renderSheets(d.data.sheets); }
          } catch { toast("Failed to add sheet.", "error"); btn.disabled = false; btn.classList.remove("opacity-50"); }
        };
        formsList.appendChild(btn);
      });
    }

    // ── Sheets grid ───────────────────────────────────────────────────────
    function loadSheets() {
      fetch(`/workbooks/api/${WORKBOOK_ID}`)
        .then(r => r.json())
        .then(d => renderSheets(d.sheets))
        .catch(() => {
          sheetsGrid.innerHTML = '<div class="text-center text-rose-500 text-sm py-10">Failed to load sheets.</div>';
        });
    }

    function renderSheets(sheets) {
      sheetsGrid.innerHTML = "";

      if (!sheets.length) {
        sheetsGrid.innerHTML = `
          <div class="md:col-span-2 xl:col-span-3 rounded-xl border border-dashed border-slate-300 bg-white shadow-sm p-12 text-center space-y-3">
            <p class="text-sm font-semibold text-slate-600">No sheets yet.</p>
            <p class="text-xs text-slate-400">Add existing forms as sheets to this workbook.</p>
            <button class="inline-flex items-center px-3.5 py-1.5 bg-[#1a3a6b] hover:bg-[#1e4280] text-white text-xs font-semibold rounded-lg shadow transition"
              onclick="document.getElementById('btn-add-sheet').click()">
              + Add First Sheet
            </button>
          </div>`;
        return;
      }

      sheets.forEach((sheet, idx) => {
        const isFirst = idx === 0;
        const isLast  = idx === sheets.length - 1;

        const card = document.createElement("div");
        card.className = "sheet-card rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden";
        card.dataset.formId = sheet.form_id;
        card.dataset.order  = idx;

        const editUrl = buildEditUrl(sheet);

        card.innerHTML = `
          <div class="px-5 py-4 space-y-1.5">
            <h3 class="font-bold text-slate-800 text-sm">${esc(sheet.sheet_label)}</h3>
            <p class="text-[10px] font-mono text-slate-400">${esc(sheet.form_code)}</p>
            <p class="text-xs text-slate-500">
              <span>${sheet.section_count} section${sheet.section_count !== 1 ? "s" : ""}</span>
              <span class="mx-1 text-slate-300">·</span>
              <span>${sheet.field_count} field${sheet.field_count !== 1 ? "s" : ""}</span>
            </p>
          </div>
          <div class="px-5 py-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between gap-2">
            <a href="${editUrl}"
              class="text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:underline">
              Open Sheet Builder →
            </a>
            <div class="flex items-center space-x-1">
              <button class="move-up-btn text-slate-400 hover:text-[#1a3a6b] text-sm font-bold px-1.5 py-0.5 rounded transition disabled:opacity-30" title="Move up" ${isFirst ? "disabled" : ""}>↑</button>
              <button class="move-down-btn text-slate-400 hover:text-[#1a3a6b] text-sm font-bold px-1.5 py-0.5 rounded transition disabled:opacity-30" title="Move down" ${isLast ? "disabled" : ""}>↓</button>
              <button class="remove-sheet-btn text-slate-300 hover:text-rose-500 text-lg font-bold px-1.5 py-0.5 rounded transition" title="Remove sheet">×</button>
            </div>
          </div>`;

        card.querySelector(".move-up-btn").onclick   = () => moveSheet(sheet.form_id, -1, sheets);
        card.querySelector(".move-down-btn").onclick  = () => moveSheet(sheet.form_id, 1, sheets);
        card.querySelector(".remove-sheet-btn").onclick = () => removeSheet(sheet.form_id, sheet.sheet_label);

        sheetsGrid.appendChild(card);
      });
    }

    function buildEditUrl(sheet) {
      const params = new URLSearchParams();
      params.set("workbook_id", WORKBOOK_ID);
      params.set("workbook_name", WORKBOOK_NAME);
      params.set("sheet_label", sheet.sheet_label);
      if (sheet.latest_version_id) {
        params.set("form_id", sheet.form_id);
        params.set("version_id", sheet.latest_version_id);
      }
      return "/module/FORMBLD/?" + params.toString();
    }

    async function moveSheet(formId, direction, sheets) {
      const idx = sheets.findIndex(s => s.form_id === formId);
      if (idx < 0) return;
      const newIdx = idx + direction;
      if (newIdx < 0 || newIdx >= sheets.length) return;

      // Swap in local array
      [sheets[idx], sheets[newIdx]] = [sheets[newIdx], sheets[idx]];
      renderSheets(sheets);

      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/sheets/reorder`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ordered_form_ids: sheets.map(s => s.form_id) }),
        });
        const d = await r.json();
        if (d.error) { toast(d.error, "error"); loadSheets(); }
      } catch { toast("Failed to save order.", "error"); loadSheets(); }
    }

    async function removeSheet(formId, label) {
      if (!confirm(`Remove "${label}" from this workbook?\n\nThe form itself will not be deleted.`)) return;
      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/sheets/remove`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ form_id: formId }),
        });
        const d = await r.json();
        if (d.error) toast(d.error, "error");
        else { toast("Sheet removed.", "warn"); loadSheets(); }
      } catch { toast("Failed to remove sheet.", "error"); }
    }
  }
});
