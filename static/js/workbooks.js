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
    return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
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
    let activeTab = "sheets";
    let approvalTabLoaded = false;
    let sitesTabLoaded = false;
    let currentWorkflowAssignment = null;

    const tabSheets = document.getElementById("tab-sheets");
    const tabSites = document.getElementById("tab-sites");
    const tabApprovalPath = document.getElementById("tab-approval-path");
    const panelSheets = document.getElementById("tab-panel-sheets");
    const panelSites = document.getElementById("tab-panel-sites");
    const panelApprovalPath = document.getElementById("tab-panel-approval-path");
    const approvalPathContent = document.getElementById("approval-path-content");
    const addSiteModal = document.getElementById("modal-add-site");
    const addSiteList = document.getElementById("add-site-list");
    const btnCloseAddSite = document.getElementById("btn-close-add-site");
    const btnCloseAddSiteFooter = document.getElementById("btn-close-add-site-footer");
    const assignPathModal = document.getElementById("modal-assign-path");
    const assignPathSelect = document.getElementById("assign-path-select");
    const assignPathMessage = document.getElementById("assign-path-message");
    const btnCloseAssignPath = document.getElementById("btn-close-assign-path");
    const btnCancelAssignPath = document.getElementById("btn-cancel-assign-path");
    const btnConfirmAssignPath = document.getElementById("btn-confirm-assign-path");
    const btnRemoveAssignedPath = document.getElementById("btn-remove-assigned-path");

    loadSheets();

    const TAB_ACTIVE   = "workbook-detail-tab border-b-2 border-indigo-600 px-1 pb-3 text-xs font-bold uppercase tracking-wider text-indigo-700";
    const TAB_INACTIVE = "workbook-detail-tab border-b-2 border-transparent px-1 pb-3 text-xs font-bold uppercase tracking-wider text-slate-500 hover:text-slate-700";

    function setWorkbookTab(nextTab) {
      activeTab = nextTab;

      if (panelSheets) panelSheets.classList.toggle("hidden", activeTab !== "sheets");
      if (panelSites) panelSites.classList.toggle("hidden", activeTab !== "sites");
      if (panelApprovalPath) panelApprovalPath.classList.toggle("hidden", activeTab !== "approval");

      if (btnAddSheet) btnAddSheet.classList.toggle("hidden", activeTab !== "sheets");
      const btnPreviewWorkbook = document.getElementById("btn-preview-workbook");
      if (btnPreviewWorkbook) btnPreviewWorkbook.classList.toggle("hidden", activeTab !== "sheets");

      if (tabSheets) tabSheets.className = activeTab === "sheets" ? TAB_ACTIVE : TAB_INACTIVE;
      if (tabSites) tabSites.className = activeTab === "sites" ? TAB_ACTIVE : TAB_INACTIVE;
      if (tabApprovalPath) tabApprovalPath.className = activeTab === "approval" ? TAB_ACTIVE : TAB_INACTIVE;

      if (activeTab === "approval" && !approvalTabLoaded) loadApprovalTab();
      if (activeTab === "sites" && !sitesTabLoaded) loadSitesTab();
    }

    if (tabSheets) tabSheets.onclick = () => setWorkbookTab("sheets");
    if (tabSites) tabSites.onclick = () => setWorkbookTab("sites");
    if (tabApprovalPath) tabApprovalPath.onclick = () => setWorkbookTab("approval");

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

        const vStatus = sheet.latest_version_status;
        const statusBadge = vStatus === "Published"
          ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-emerald-50 border border-emerald-200 text-emerald-700">Published</span>`
          : vStatus === "Draft"
            ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-amber-50 border border-amber-200 text-amber-700">Draft</span>`
            : `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-slate-100 text-slate-400">No version</span>`;

        card.innerHTML = `
          <div class="px-5 py-4 space-y-1.5">
            <div class="flex items-center justify-between gap-2">
              <h3 class="font-bold text-slate-800 text-sm leading-snug">${esc(sheet.sheet_label)}</h3>
              ${statusBadge}
            </div>
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

    // ── Approval Path tab ─────────────────────────────────────────────────
    async function loadApprovalTab() {
      approvalTabLoaded = true;
      if (!approvalPathContent) return;
      approvalPathContent.innerHTML = `
        <div class="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm italic text-slate-400 shadow-sm">
          Loading approval path…
        </div>
      `;

      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/workflow`);
        const data = await r.json();
        if (!r.ok || data.error) throw new Error(data.error || "Failed to load approval path.");
        currentWorkflowAssignment = data.workflow_id ? data : null;

        if (!currentWorkflowAssignment) {
          renderNoAssignedPath();
          return;
        }
        renderAssignedPath(currentWorkflowAssignment);
      } catch (err) {
        approvalPathContent.innerHTML = `
          <div class="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm font-semibold text-rose-700 shadow-sm">
            ${esc(err.message || "Failed to load approval path.")}
          </div>
        `;
      }
    }

    function renderNoAssignedPath() {
      approvalPathContent.innerHTML = `
        <div class="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
          <p class="text-sm font-semibold text-slate-700">No approval path configured.</p>
          <p class="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">
            Submitted workbook packages cannot move through review until an approval path is assigned.
          </p>
          <div class="mt-6 flex flex-wrap items-center justify-center gap-3">
            <button id="btn-create-path-from-workbook" type="button"
              class="inline-flex items-center rounded-lg bg-[#1a3a6b] px-4 py-2 text-sm font-semibold text-white shadow hover:bg-[#1e4280]">
              + Create New Path
            </button>
            <button id="btn-open-assign-path-empty" type="button"
              class="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              Assign Existing Path
            </button>
          </div>
        </div>
      `;
      document.getElementById("btn-create-path-from-workbook").onclick = () => {
        window.location.href = `/module/WFLWBLD/?context=workbook&workbook_id=${WORKBOOK_ID}`;
      };
      document.getElementById("btn-open-assign-path-empty").onclick = openAssignPathModal;
    }

    function statusPill(status) {
      if (status === "Published") {
        return '<span class="rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-bold uppercase text-emerald-800">Live</span>';
      }
      return '<span class="rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-bold uppercase text-amber-800">Draft</span>';
    }

    function renderAssignedPath(data) {
      approvalPathContent.innerHTML = `
        <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div class="flex flex-col gap-4 border-b border-slate-100 pb-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Approval Path</div>
              <div class="mt-2 flex flex-wrap items-center gap-2">
                <h2 class="text-lg font-bold text-slate-800">${esc(data.workflow_name)}</h2>
                ${statusPill(data.version_status)}
              </div>
              <p class="mt-1 font-mono text-xs text-slate-400">${esc(data.workflow_code)}</p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <button id="btn-open-assign-path-assigned" type="button"
                class="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                Change
              </button>
              <a href="/module/WFLWBLD/?edit=${encodeURIComponent(data.workflow_id)}&context=workbook&workbook_id=${WORKBOOK_ID}"
                class="font-semibold text-[#1a3a6b] hover:underline text-xs">
                Edit Path
              </a>
            </div>
          </div>

          <div class="mt-5">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 class="text-sm font-semibold text-slate-800">Preview path by site</h3>
                <p class="mt-1 text-xs text-slate-500">Check who reviews workbook packages for a selected site.</p>
              </div>
              <select id="approval-preview-site-select"
                class="h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800 focus:border-indigo-500 focus:ring-indigo-500">
                <option value="">Loading sites…</option>
              </select>
            </div>
            <div id="approval-preview-chain" class="mt-5">
              <div class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm italic text-slate-400">
                Loading path preview…
              </div>
            </div>
          </div>
        </div>
      `;
      document.getElementById("btn-open-assign-path-assigned").onclick = openAssignPathModal;
      loadAssignedPathSites(data.version_id);
    }

    async function loadAssignedPathSites(versionId) {
      const siteSelect = document.getElementById("approval-preview-site-select");
      const chain = document.getElementById("approval-preview-chain");
      if (!siteSelect || !chain) return;

      if (!versionId) {
        siteSelect.innerHTML = '<option value="">No version available</option>';
        chain.innerHTML = `
          <div class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm italic text-slate-400">
            This approval path has no version to preview.
          </div>
        `;
        return;
      }

      try {
        const r = await fetch(`/module/WFLWBLD/api/version/${versionId}`);
        const data = await r.json();
        if (!r.ok || data.error) throw new Error(data.error || "Failed to load path sites.");
        const sites = data.available_sites || [];
        if (!sites.length) {
          siteSelect.innerHTML = '<option value="">No sites available</option>';
          chain.innerHTML = `
            <div class="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm italic text-slate-400">
              No sites are available for preview.
            </div>
          `;
          return;
        }

        siteSelect.innerHTML = sites.map(site => `<option value="${site.id}">${esc(site.name)}</option>`).join("");
        siteSelect.onchange = () => loadApprovalPathPreview(versionId, siteSelect.value);
        loadApprovalPathPreview(versionId, siteSelect.value);
      } catch (err) {
        siteSelect.innerHTML = '<option value="">Unable to load sites</option>';
        chain.innerHTML = `
          <div class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-4 text-sm font-semibold text-rose-700">
            ${esc(err.message || "Failed to load path sites.")}
          </div>
        `;
      }
    }

    async function loadApprovalPathPreview(versionId, siteId) {
      const chain = document.getElementById("approval-preview-chain");
      if (!chain || !siteId) return;
      chain.innerHTML = `
        <div class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm italic text-slate-400">
          Loading path preview…
        </div>
      `;

      try {
        const r = await fetch(`/module/WFLWBLD/api/version/${versionId}/preview?site_id=${encodeURIComponent(siteId)}`);
        const payload = await r.json();
        if (!r.ok || payload.error) throw new Error(payload.error || "Failed to load path preview.");
        renderApprovalPathChain(payload.data || {});
      } catch (err) {
        chain.innerHTML = `
          <div class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-4 text-sm font-semibold text-rose-700">
            ${esc(err.message || "Failed to load path preview.")}
          </div>
        `;
      }
    }

    function renderApprovalPathChain(data) {
      const chain = document.getElementById("approval-preview-chain");
      if (!chain) return;
      const rows = data.rows || [];
      const nodes = [{
        title: "SPOC submits",
        detail: "Workbook package enters review.",
        status: "start"
      }];

      rows.forEach(row => {
        const approverNames = (row.approvers || []).map(approver => approver.name).join(", ");
        nodes.push({
          title: row.level_name,
          detail: row.status === "active"
            ? (approverNames || "Reviewer assigned")
            : row.status === "skipped"
              ? "(skipped)"
              : "No reviewer exists for this site.",
          status: row.status
        });
      });

      if (!data.has_warning) {
        nodes.push({
          title: "Approved & locked",
          detail: "Final approval locks the submitted workbook data.",
          status: "done"
        });
      }

      const nodeHtml = nodes.map((node, index) => {
        const isLast = index === nodes.length - 1;
        const dotClass =
          node.status === "blocked" ? "bg-rose-500" :
          node.status === "skipped" ? "bg-slate-300" :
          node.status === "done" ? "bg-emerald-500" :
          "bg-[#1a3a6b]";
        const boxClass =
          node.status === "blocked" ? "border-rose-200 bg-rose-50" :
          node.status === "skipped" ? "border-slate-200 bg-slate-50" :
          node.status === "done" ? "border-emerald-200 bg-emerald-50" :
          "border-slate-200 bg-white";

        return `
          <li class="relative flex gap-3 ${isLast ? "" : "pb-4"}">
            ${isLast ? "" : '<span class="absolute left-[5px] top-4 h-full w-px bg-slate-200"></span>'}
            <span class="relative mt-3 h-2.5 w-2.5 shrink-0 rounded-full ${dotClass}"></span>
            <div class="min-w-0 flex-1 rounded-lg border px-3 py-2 ${boxClass}">
              <div class="text-sm font-semibold text-slate-800">${esc(node.title)}</div>
              <div class="mt-1 text-xs text-slate-500">${esc(node.detail)}</div>
            </div>
          </li>
        `;
      }).join("");

      chain.innerHTML = `
        ${data.has_warning ? `
          <div class="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-800">
            ${esc(data.message || "This site would block during submission.")}
          </div>
        ` : ""}
        <ol class="space-y-0">${nodeHtml}</ol>
      `;
    }

    async function openAssignPathModal() {
      if (!assignPathModal || !assignPathSelect) return;
      assignPathModal.classList.remove("hidden");
      assignPathModal.classList.add("flex");
      assignPathSelect.disabled = true;
      assignPathSelect.innerHTML = '<option value="">Loading paths…</option>';
      if (assignPathMessage) assignPathMessage.classList.add("hidden");
      if (btnConfirmAssignPath) btnConfirmAssignPath.disabled = true;
      if (btnRemoveAssignedPath) {
        btnRemoveAssignedPath.classList.toggle("hidden", !currentWorkflowAssignment);
      }

      try {
        const r = await fetch("/module/WFLWBLD/api");
        const paths = await r.json();
        if (!r.ok || paths.error) throw new Error(paths.error || "Failed to load approval paths.");
        const publishedPaths = (paths || []).filter(path => path.latest_version_status === "Published");

        if (!publishedPaths.length) {
          assignPathSelect.innerHTML = '<option value="">No published approval paths available</option>';
          if (assignPathMessage) {
            assignPathMessage.textContent = "Publish an approval path before assigning it to a workbook.";
            assignPathMessage.classList.remove("hidden");
          }
          return;
        }

        assignPathSelect.innerHTML = '<option value="">Choose approval path</option>' + publishedPaths.map(path => (
          `<option value="${path.id}" ${currentWorkflowAssignment && parseInt(currentWorkflowAssignment.workflow_id) === parseInt(path.id) ? "selected" : ""}>${esc(path.name)} (${esc(path.code)})</option>`
        )).join("");
        assignPathSelect.disabled = false;
        if (btnConfirmAssignPath) btnConfirmAssignPath.disabled = false;
      } catch (err) {
        assignPathSelect.innerHTML = '<option value="">Unable to load paths</option>';
        if (assignPathMessage) {
          assignPathMessage.textContent = err.message || "Failed to load approval paths.";
          assignPathMessage.classList.remove("hidden");
        }
      }
    }

    function closeAssignPathModal() {
      if (!assignPathModal) return;
      assignPathModal.classList.add("hidden");
      assignPathModal.classList.remove("flex");
    }

    async function assignSelectedPath() {
      const selectedId = assignPathSelect && assignPathSelect.value ? parseInt(assignPathSelect.value) : null;
      if (!selectedId) {
        toast("Choose an approval path to assign.", "warn");
        return;
      }
      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/workflow`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workflow_id: selectedId }),
        });
        const data = await r.json();
        if (!r.ok || data.error) throw new Error(data.error || "Failed to assign approval path.");
        closeAssignPathModal();
        approvalTabLoaded = false;
        await loadApprovalTab();
        toast("Approval path assigned.");
      } catch (err) {
        toast(err.message || "Failed to assign approval path.", "error");
      }
    }

    async function clearAssignedPath() {
      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/workflow`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workflow_id: null }),
        });
        const data = await r.json();
        if (!r.ok || data.error) throw new Error(data.error || "Failed to remove approval path.");
        closeAssignPathModal();
        approvalTabLoaded = false;
        await loadApprovalTab();
        toast("Approval path removed.", "warn");
      } catch (err) {
        toast(err.message || "Failed to remove approval path.", "error");
      }
    }

    if (btnCloseAssignPath) btnCloseAssignPath.onclick = closeAssignPathModal;
    if (btnCancelAssignPath) btnCancelAssignPath.onclick = closeAssignPathModal;
    if (btnConfirmAssignPath) btnConfirmAssignPath.onclick = assignSelectedPath;
    if (btnRemoveAssignedPath) btnRemoveAssignedPath.onclick = clearAssignedPath;

    // ── Sites tab ─────────────────────────────────────────────────────────
    async function loadSitesTab() {
      try {
        const res = await fetch(`/workbooks/api/${WORKBOOK_ID}/sites`);
        const sites = await res.json();
        renderSitesTab(sites);
        sitesTabLoaded = true;
      } catch {
        const content = document.getElementById("sites-tab-content");
        if (content) content.innerHTML = `
          <div class="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
            Failed to load sites. Please refresh.
          </div>`;
      }
    }

    function renderSitesTab(sites) {
      const content = document.getElementById("sites-tab-content");
      if (!content) return;

      if (!sites.length) {
        content.innerHTML = `
          <div class="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center shadow-sm space-y-4">
            <p class="text-sm font-semibold text-slate-600">No sites assigned yet.</p>
            <p class="text-xs text-slate-400">Add the sites/ports that use this workbook format for monthly data entry.</p>
            <button id="btn-add-site-empty"
              class="inline-flex items-center px-4 py-2 bg-[#1a3a6b] hover:bg-[#1e4280] text-white text-sm font-semibold rounded-lg shadow transition">
              + Add Site
            </button>
          </div>`;
        const emptyBtn = document.getElementById("btn-add-site-empty");
        if (emptyBtn) emptyBtn.onclick = openAddSiteModal;
        return;
      }

      const cards = sites.map(site => `
        <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div class="flex items-start justify-between gap-2">
            <span class="font-semibold text-slate-800 text-sm">${esc(site.name)}</span>
            <button class="remove-site-btn text-xs font-semibold text-rose-600 hover:underline shrink-0"
              data-site-id="${site.id}">× Remove</button>
          </div>
          <p class="font-mono text-xs text-slate-400 mt-0.5">${esc(site.code)}</p>
        </div>`).join("");

      content.innerHTML = `
        <div class="space-y-4">
          <div class="flex items-start justify-between gap-4">
            <div>
              <h3 class="text-sm font-bold text-slate-700">Sites using this workbook format</h3>
              <p class="text-xs text-slate-400 mt-1">These sites will receive monthly data entry tasks when a reporting period is opened.</p>
              <p class="text-xs text-slate-400 mt-1">If no sites are configured, SPOCs cannot submit this workbook's data.</p>
            </div>
            <button id="btn-add-site-header"
              class="shrink-0 inline-flex items-center px-4 py-2 bg-[#1a3a6b] hover:bg-[#1e4280] text-white text-sm font-semibold rounded-lg shadow transition">
              + Add Site
            </button>
          </div>
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            ${cards}
          </div>
        </div>`;

      const addBtn = document.getElementById("btn-add-site-header");
      if (addBtn) addBtn.onclick = openAddSiteModal;
      content.querySelectorAll(".remove-site-btn").forEach(btn => {
        btn.onclick = () => removeSiteFromWorkbook(parseInt(btn.dataset.siteId));
      });
    }

    async function openAddSiteModal() {
      if (!addSiteModal) return;
      addSiteModal.classList.remove("hidden");
      addSiteModal.classList.add("flex");
      if (addSiteList) addSiteList.innerHTML = `<p class="text-xs text-slate-400 italic text-center py-6">Loading sites…</p>`;

      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/assignable-sites`);
        const sites = await r.json();
        if (!r.ok) throw new Error(sites.error || "Failed to load sites.");
        renderAssignableSites(sites);
      } catch (err) {
        if (addSiteList) addSiteList.innerHTML = `
          <div class="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            ${esc(err.message || "Failed to load sites.")}
          </div>`;
      }
    }

    function renderAssignableSites(sites) {
      if (!addSiteList) return;
      if (!sites.length) {
        addSiteList.innerHTML = `<p class="text-xs text-slate-400 italic text-center py-6">All sites are already assigned.</p>`;
        return;
      }
      addSiteList.innerHTML = "";
      sites.forEach(site => {
        const btn = document.createElement("button");
        btn.className = "w-full text-left px-4 py-3 rounded-lg hover:bg-indigo-50 border border-transparent hover:border-indigo-200 transition-colors";
        btn.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="font-semibold text-sm text-slate-800">${esc(site.name)}</span>
            <span class="shrink-0 text-xs font-semibold text-[#1a3a6b]">Add →</span>
          </div>
          <span class="font-mono text-[10px] text-slate-400">${esc(site.code)}</span>`;
        btn.onclick = async () => {
          btn.disabled = true;
          btn.classList.add("opacity-50");
          try {
            const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/sites`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ site_id: site.id }),
            });
            const d = await r.json();
            if (!r.ok || d.error) {
              toast(d.error || "Failed to add site.", "error");
              btn.disabled = false;
              btn.classList.remove("opacity-50");
              return;
            }
            btn.remove();
            if (!addSiteList.querySelector("button")) {
              addSiteList.innerHTML = `<p class="text-xs text-slate-400 italic text-center py-6">All sites are already assigned.</p>`;
            }
            renderSitesTab(d.data.sites);
            toast("Site added.");
          } catch {
            toast("Failed to add site.", "error");
            btn.disabled = false;
            btn.classList.remove("opacity-50");
          }
        };
        addSiteList.appendChild(btn);
      });
    }

    function closeAddSiteModal() {
      if (!addSiteModal) return;
      addSiteModal.classList.add("hidden");
      addSiteModal.classList.remove("flex");
    }

    async function removeSiteFromWorkbook(siteId) {
      if (!confirm("Remove this site from the workbook?")) return;
      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/sites/${siteId}`, { method: "DELETE" });
        const d = await r.json();
        if (!r.ok || d.error) {
          toast(d.error || "Failed to remove site.", "error");
          return;
        }
        renderSitesTab(d.data.sites);
        toast("Site removed.", "warn");
      } catch {
        toast("Failed to remove site.", "error");
      }
    }

    if (btnCloseAddSite) btnCloseAddSite.onclick = closeAddSiteModal;
    if (btnCloseAddSiteFooter) btnCloseAddSiteFooter.onclick = closeAddSiteModal;
  }
});
