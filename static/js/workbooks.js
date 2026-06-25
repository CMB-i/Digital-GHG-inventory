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

  // ── Workbook Rename Modal Logic ──
  const renameModal    = document.getElementById("modal-rename-wb");
  const formRW         = document.getElementById("form-rename-wb");
  const renameWbId     = document.getElementById("rename-wb-id");
  const renameWbName   = document.getElementById("rename-wb-name");

  if (renameModal) {
    const btnCloseRename = document.getElementById("btn-close-rename-wb");
    const btnCancelRename = document.getElementById("btn-cancel-rename-wb");
    if (btnCloseRename) btnCloseRename.onclick = () => renameModal.classList.add("hidden");
    if (btnCancelRename) btnCancelRename.onclick = () => renameModal.classList.add("hidden");

    if (formRW) {
      formRW.onsubmit = async (e) => {
        e.preventDefault();
        const id = renameWbId && renameWbId.value ? renameWbId.value : (typeof WORKBOOK_ID !== "undefined" ? WORKBOOK_ID : null);
        const name = renameWbName ? renameWbName.value.trim() : "";
        if (!id || !name) return;
        const submitBtn = document.getElementById("btn-submit-rename-wb");
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = "Saving…";
        }
        try {
          const res = await fetch(`/workbooks/api/${id}/rename`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
          });
          const d = await res.json();
          if (d.error) {
            toast(d.error, "error");
          } else {
            renameModal.classList.add("hidden");
            toast("Workbook renamed.");
            if (grid) {
              loadWorkbooks();
            } else {
              const wbTitle = document.getElementById("wb-title");
              const wbBreadcrumb = document.getElementById("wb-breadcrumb");
              if (wbTitle) wbTitle.textContent = d.data.name;
              if (wbBreadcrumb) wbBreadcrumb.textContent = d.data.name;
            }
          }
        } catch {
          toast("Failed to rename workbook.", "error");
        } finally {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = "Save Changes";
          }
        }
      };
    }
  }

  // Workbook Rename Button (Detail Page)
  const btnRenameWbDetail = document.getElementById("btn-rename-workbook");
  if (btnRenameWbDetail) {
    btnRenameWbDetail.onclick = () => {
      const wbTitle = document.getElementById("wb-title");
      if (renameWbId) renameWbId.value = WORKBOOK_ID;
      if (renameWbName) renameWbName.value = wbTitle ? wbTitle.textContent.trim() : "";
      renameModal.classList.remove("hidden");
      setTimeout(() => renameWbName.focus(), 50);
    };
  }

  // ── Sheet Rename Modal Logic (Detail Page Only) ──
  const renameSheetModal  = document.getElementById("modal-rename-sheet");
  const formRS            = document.getElementById("form-rename-sheet");
  const renameSheetFormId = document.getElementById("rename-sheet-form-id");
  const renameSheetLabel  = document.getElementById("rename-sheet-label");

  if (renameSheetModal) {
    const btnCloseRS = document.getElementById("btn-close-rename-sheet");
    const btnCancelRS = document.getElementById("btn-cancel-rename-sheet");
    if (btnCloseRS) btnCloseRS.onclick = () => renameSheetModal.classList.add("hidden");
    if (btnCancelRS) btnCancelRS.onclick = () => renameSheetModal.classList.add("hidden");

    if (formRS) {
      formRS.onsubmit = async (e) => {
        e.preventDefault();
        const formId = renameSheetFormId ? renameSheetFormId.value : null;
        const sheetLabelVal = renameSheetLabel ? renameSheetLabel.value.trim() : "";
        if (!formId) return;

        const submitBtn = document.getElementById("btn-submit-rename-sheet");
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = "Saving…";
        }
        try {
          const res = await fetch(`/workbooks/api/${WORKBOOK_ID}/sheets/${formId}/rename`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sheet_label: sheetLabelVal }),
          });
          const d = await res.json();
          if (d.error) {
            toast(d.error, "error");
          } else {
            renameSheetModal.classList.add("hidden");
            toast("Sheet renamed.");
            renderSheets(d.data.sheets);
            loadReadiness();
          }
        } catch {
          toast("Failed to rename sheet.", "error");
        } finally {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = "Save Changes";
          }
        }
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
      const isLive = wb.status === "published";
      const statusLabel = isLive ? "Live" : "Draft";
      const statusColor = isLive ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700";
      const card = document.createElement("div");
      card.className = "rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden hover:shadow-md transition-shadow";
      card.innerHTML = `
        <div class="px-5 py-4 space-y-2">
          <div class="flex items-start justify-between gap-2">
            <h3 class="font-bold text-slate-800 text-sm leading-snug">${esc(wb.name)}</h3>
            <span class="shrink-0 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${statusColor}">${statusLabel}</span>
          </div>
          <p class="text-[10px] font-mono text-slate-400">${esc(wb.code)}</p>
          ${wb.description ? `<p class="text-xs text-slate-500 line-clamp-2">${esc(wb.description)}</p>` : ""}
          <div class="flex items-center space-x-4 pt-1">
            <span class="text-xs text-slate-500">Sheets: <strong>${wb.sheet_count}</strong></span>
            <span class="text-xs text-slate-500">Fields: <strong>${wb.field_count}</strong></span>
          </div>
        </div>
        <div class="px-5 py-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between gap-2">
          <a href="/workbooks/${wb.id}"
            class="inline-flex items-center rounded-lg bg-[#1a3a6b] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1e4280] transition-colors">
            ${isLive ? "Open Workbook →" : "Continue Setup →"}
          </a>
          <div class="flex items-center gap-3">
            <button class="rename-wb-btn text-xs font-semibold text-slate-400 hover:text-[#1a3a6b] transition-colors"
              data-id="${wb.id}" data-name="${esc(wb.name)}">Rename</button>
            <button class="deactivate-btn text-xs font-semibold text-slate-400 hover:text-rose-500 transition-colors"
              data-id="${wb.id}">Deactivate</button>
          </div>
        </div>`;
      card.querySelector(".rename-wb-btn").onclick = (e) => {
        const id = e.currentTarget.dataset.id;
        const name = e.currentTarget.dataset.name;
        if (renameWbId) renameWbId.value = id;
        if (renameWbName) renameWbName.value = name;
        renameModal.classList.remove("hidden");
        setTimeout(() => renameWbName.focus(), 50);
      };
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
  const btnReuseExistingSheet = document.getElementById("btn-reuse-existing-sheet");

  if (sheetsGrid && typeof WORKBOOK_ID !== "undefined") {
    let activeTab = "sheets";
    let approvalTabLoaded = false;
    let sitesTabLoaded = false;
    let activeSiteIdForSubmitters = null;
    let chainData = null;

    const tabSheets = document.getElementById("tab-sheets");
    const tabApprovalPath = document.getElementById("tab-approval-path");
    const panelSheets = document.getElementById("tab-panel-sheets");
    const panelApprovalPath = document.getElementById("tab-panel-approval-path");
    const tabSites = document.getElementById("tab-sites");
    const panelSites = document.getElementById("tab-panel-sites");
    const addSiteModal = document.getElementById("modal-add-site");
    const addSiteList = document.getElementById("add-site-list");
    const btnCloseAddSite = document.getElementById("btn-close-add-site");
    const btnCloseAddSiteFooter = document.getElementById("btn-close-add-site-footer");

    loadSheets();
    loadReadiness();

    const TAB_ACTIVE   = "workbook-detail-tab border-b-2 border-indigo-600 px-1 pb-3 text-xs font-bold uppercase tracking-wider text-indigo-700";
    const TAB_INACTIVE = "workbook-detail-tab border-b-2 border-transparent px-1 pb-3 text-xs font-bold uppercase tracking-wider text-slate-500 hover:text-slate-700";

    function setWorkbookTab(nextTab) {
      activeTab = nextTab;
      if (panelSheets) panelSheets.classList.toggle("hidden", activeTab !== "sheets");
      if (panelSites) panelSites.classList.toggle("hidden", activeTab !== "sites");
      if (panelApprovalPath) panelApprovalPath.classList.toggle("hidden", activeTab !== "approval");
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
    const previewResultsOverflow = document.getElementById("wb-preview-results-overflow");

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
      if (previewResultsOverflow) {
        previewResultsOverflow.classList.add("hidden");
        previewResultsOverflow.innerHTML = "";
      }
    }

    function renderPreviewResultsOverflow(sheetResults) {
      if (!previewResultsOverflow) return;
      if (!window.WorkbookSheet || typeof window.WorkbookSheet.renderSheetResultsOverflowHtml !== "function") {
        previewResultsOverflow.classList.add("hidden");
        previewResultsOverflow.innerHTML = "";
        return;
      }
      const html = window.WorkbookSheet.renderSheetResultsOverflowHtml(sheetResults || []);
      if (!html) {
        previewResultsOverflow.classList.add("hidden");
        previewResultsOverflow.innerHTML = "";
        return;
      }
      previewResultsOverflow.innerHTML = html;
      previewResultsOverflow.classList.remove("hidden");
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
            sheetResults: ctx.sheet_results || [],
            selectedRowKey: null,
          });
          renderPreviewResultsOverflow(ctx.sheet_results || []);
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

    // ── Publish Workbook ──────────────────────────────────────────────────
    const btnPublishWorkbook = document.getElementById("btn-publish-workbook");
    if (btnPublishWorkbook) {
      btnPublishWorkbook.addEventListener("click", async () => {
        btnPublishWorkbook.disabled = true;
        btnPublishWorkbook.textContent = "Publishing…";
        try {
          const res = await fetch(`/workbooks/api/${WORKBOOK_ID}/publish`, { method: "POST" });
          const data = await res.json();
          if (!res.ok) {
            toast(data.error || "Failed to publish workbook.", "error");
            if (data.checklist) renderReadiness({ workbook_status: "draft", checklist: data.checklist });
            else await loadReadiness();
            return;
          }
          toast("Workbook published — it is now Live.");
          renderReadiness({ workbook_status: data.data.status, checklist: data.data.checklist });
        } catch {
          toast("Failed to publish workbook.", "error");
          await loadReadiness();
        }
      });
    }

    // ── Add Sheet panel ───────────────────────────────────────────────────
    const panel         = document.getElementById("panel-add-sheet");
    const backdrop      = document.getElementById("panel-backdrop");
    const btnClosePanel = document.getElementById("btn-close-add-sheet");
    const sheetLabel    = document.getElementById("add-sheet-label");
    const sheetSearch   = document.getElementById("add-sheet-search");
    const formsList     = document.getElementById("addable-forms-list");

    let allAddable = [];

    function goToCreateSheet() {
      const params = new URLSearchParams();
      params.set("workbook_id", WORKBOOK_ID);
      params.set("workbook_name", WORKBOOK_NAME);
      window.location.href = "/module/FORMBLD/?" + params.toString();
    }

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
        .catch(() => { formsList.innerHTML = '<p class="text-xs text-rose-500 text-center py-6">Failed to load sheets.</p>'; });
    }

    function closePanel() { panel.classList.add("hidden"); }

    btnAddSheet.onclick    = goToCreateSheet;
    if (btnReuseExistingSheet) btnReuseExistingSheet.onclick = openPanel;
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
        if (!sheetSearch.value.trim()) {
          formsList.innerHTML =
            '<p class="text-xs text-slate-400 italic text-center py-4">' +
            'All published sheets are already in this workbook.<br>' +
            '<span class="text-[#1a3a6b] font-semibold">' +
            'Use "Add Sheet" to create a new one.</span>' +
            '</p>';
        } else {
          formsList.innerHTML =
            '<p class="text-xs text-slate-400 italic text-center py-4">' +
            'No matching sheets found.' +
            '</p>';
        }
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
            else { toast("Sheet added."); closePanel(); renderSheets(d.data.sheets); loadReadiness(); }
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
            <p class="text-xs text-slate-400">Create a sheet or reuse an existing published sheet.</p>
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
              <div class="flex items-center gap-1.5 min-w-0">
                <h3 class="font-bold text-slate-800 text-sm leading-snug truncate" title="${esc(sheet.sheet_label)}">${esc(sheet.sheet_label)}</h3>
                <button class="rename-sheet-btn text-slate-400 hover:text-[#1a3a6b] shrink-0 transition-colors" title="Rename sheet">
                  <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
              </div>
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

        card.querySelector(".rename-sheet-btn").onclick = () => {
          if (renameSheetFormId) renameSheetFormId.value = sheet.form_id;
          if (renameSheetLabel) renameSheetLabel.value = sheet.sheet_label || "";
          renameSheetModal.classList.remove("hidden");
          setTimeout(() => renameSheetLabel.focus(), 50);
        };
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
      if (!confirm(`Remove "${label}" from this workbook?\n\nThe sheet definition itself will not be deleted.`)) return;
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

    // ── Workbook readiness ────────────────────────────────────────────────

    async function loadReadiness() {
      try {
        const res = await fetch(`/workbooks/api/${WORKBOOK_ID}/readiness`);
        const data = await res.json();
        renderReadiness(data);
      } catch { /* fail silently — non-critical */ }
    }

    function renderReadiness(data) {
      const el = document.getElementById("wb-readiness");
      if (!el) return;

      const isLive = data.workbook_status === "published";

      const badge = document.getElementById("wb-status-badge");
      if (badge) {
        badge.className = isLive
          ? "px-2 py-0.5 rounded-full font-bold text-[10px] uppercase bg-emerald-100 text-emerald-700"
          : "px-2 py-0.5 rounded-full font-bold text-[10px] uppercase bg-amber-100 text-amber-800";
        badge.textContent = isLive ? "Live" : "Draft";
      }

      const publishBtn = document.getElementById("btn-publish-workbook");
      if (publishBtn) {
        if (isLive) {
          publishBtn.textContent = "Live";
          publishBtn.disabled = true;
          publishBtn.className = "inline-flex items-center justify-center px-4 py-2 bg-emerald-100 text-emerald-700 text-sm font-semibold rounded-lg cursor-default";
        } else {
          const canPublish = !!(data.checklist && data.checklist.all_ok);
          publishBtn.disabled = !canPublish;
          publishBtn.textContent = "Publish Workbook";
          publishBtn.className = canPublish
            ? "inline-flex items-center justify-center px-4 py-2 bg-[#1a3a6b] hover:bg-[#1e4280] text-white text-sm font-semibold rounded-lg shadow transition-colors"
            : "inline-flex items-center justify-center px-4 py-2 bg-slate-200 text-slate-400 text-sm font-semibold rounded-lg cursor-not-allowed";
        }
      }

      if (!data.checklist) { el.innerHTML = ""; return; }

      const checks = [
        data.checklist.sheets,
        data.checklist.sites,
        data.checklist.submitters,
        data.checklist.approval_path,
      ];

      el.innerHTML = `
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider">Setup Checklist</h3>
          ${isLive ? '<span class="text-xs text-emerald-600 font-semibold">All requirements met</span>' : ""}
        </div>
        <div class="flex flex-wrap gap-3">
          ${checks.map(c => `
            <div class="flex items-start gap-2 rounded-lg border ${c.ok ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"} px-3 py-2 text-xs min-w-[160px]">
              <span class="mt-0.5 text-sm leading-none ${c.ok ? "text-emerald-500" : "text-amber-500"}">${c.ok ? "✓" : "○"}</span>
              <div>
                <div class="font-bold ${c.ok ? "text-emerald-700" : "text-amber-700"}">${esc(c.label)}</div>
                <div class="mt-0.5 ${c.ok ? "text-emerald-600" : "text-amber-600"}">${esc(c.detail)}</div>
              </div>
            </div>
          `).join("")}
        </div>`;
    }

    // ── Approval Path tab ─────────────────────────────────────────────────

    async function loadApprovalTab() {
      approvalTabLoaded = true;
      const content = document.getElementById("approval-path-content");
      if (!content) return;
      content.innerHTML = `
        <div class="rounded-xl border border-slate-200 bg-white p-6
                    text-center text-sm italic text-slate-400 shadow-sm">
          Loading approval chain…
        </div>`;

      try {
        const [chainRes, sitesRes] = await Promise.all([
          fetch(`/workbooks/api/${WORKBOOK_ID}/chain`),
          fetch(`/workbooks/api/${WORKBOOK_ID}/sites`)
        ]);
        chainData = await chainRes.json();
        const sites = await sitesRes.json();

        if (!sites.length) {
          content.innerHTML = `
            <div class="rounded-xl border border-dashed border-slate-300
                        bg-white p-10 text-center shadow-sm">
              <p class="text-sm font-semibold text-slate-700">No sites assigned yet.</p>
              <p class="mt-2 text-xs text-slate-400">
                Add sites in the Sites tab first, then configure approval chains here.
              </p>
            </div>`;
          return;
        }

        renderApprovalBuilder(sites, chainData);
      } catch (err) {
        content.innerHTML = `
          <div class="rounded-xl border border-rose-200 bg-rose-50 p-6
                      text-sm font-semibold text-rose-700 shadow-sm">
            ${esc(err.message || "Failed to load approval chain.")}
          </div>`;
      }
    }

    function renderApprovalBuilder(sites, chain) {
      const content = document.getElementById("approval-path-content");
      if (!content) return;

      const available_users = chain.available_users || [];
      const statusBadge = chain.version_status === "Published"
        ? `<span class="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">Live</span>`
        : chain.version_status === "Draft"
          ? `<span class="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-700">Draft — not yet published</span>`
          : "";

      const publishBtn = (chain.version_status === "Draft" && chain.version_id)
        ? `<button type="button" id="publish-approval-path-btn"
             class="rounded-lg bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white
                    hover:bg-emerald-700 disabled:opacity-40">
             Publish Approval Path
           </button>`
        : "";

      content.innerHTML = `
        <div class="space-y-5">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-sm font-bold text-slate-700">Approval Chain</h2>
              <p class="mt-1 text-xs text-slate-400">
                Configure who reviews workbook packages for each site.
                Each site can have its own reviewer sequence.
              </p>
            </div>
            <div class="flex items-center gap-3">
              ${statusBadge}
              ${publishBtn}
            </div>
          </div>
          <div id="approval-sites-list" class="space-y-4"></div>
        </div>`;

      const publishBtnEl = document.getElementById("publish-approval-path-btn");
      if (publishBtnEl) {
        publishBtnEl.onclick = async () => {
          publishBtnEl.disabled = true;
          publishBtnEl.textContent = "Publishing…";
          try {
            const res = await fetch(`/workbooks/api/${WORKBOOK_ID}/chain/publish`, { method: "POST" });
            const data = await res.json();
            if (!res.ok) {
              toast(data.error || "Failed to publish approval path.", "error");
              publishBtnEl.disabled = false;
              publishBtnEl.textContent = "Publish Approval Path";
              return;
            }
            toast("Approval path published. Workbook is now ready for submission.");
            approvalTabLoaded = false;
            loadApprovalTab();
            loadReadiness();
          } catch {
            toast("Failed to publish approval path.", "error");
            publishBtnEl.disabled = false;
            publishBtnEl.textContent = "Publish Approval Path";
          }
        };
      }

      const list = document.getElementById("approval-sites-list");
      sites.forEach(site => {
        const siteApprovers = (chain.approvers_by_site || {})[String(site.id)] || [];
        const levels = chain.levels || [];
        list.appendChild(buildSiteChainCard(site, levels, siteApprovers, available_users, chain));
      });
    }

    function buildSiteChainCard(site, levels, siteApprovers, users, chain) {
      const card = document.createElement("div");
      card.className = "rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden";
      card.id = `site-chain-card-${site.id}`;

      const header = document.createElement("div");
      header.className = "flex items-center justify-between border-b border-slate-100 bg-slate-50 px-5 py-3";
      header.innerHTML = `
        <div>
          <span class="text-sm font-bold text-slate-800">${esc(site.name)}</span>
          <span class="ml-2 font-mono text-[10px] text-slate-400">${esc(site.code)}</span>
        </div>
        <button type="button"
          class="save-chain-btn rounded-lg bg-[#1a3a6b] px-3 py-1.5
                 text-xs font-semibold text-white hover:bg-[#1e4280] disabled:opacity-40"
          data-site-id="${site.id}">
          Save
        </button>`;
      card.appendChild(header);

      const body = document.createElement("div");
      body.className = "overflow-x-auto px-5 py-5";
      body.id = `chain-body-${site.id}`;
      card.appendChild(body);

      let steps = [];
      if (levels.length) {
        steps = levels.map(level => {
          const approver = siteApprovers.find(a => a.level_id === level.id);
          return {
            level_number: level.level_number,
            level_name: level.level_name,
            level_type: level.level_type,
            user_id: approver ? approver.user_id : null,
          };
        });
      } else {
        steps = [{ level_number: 1, level_name: "Final Approval", level_type: "final", user_id: null }];
      }

      renderChainBody(body, site, steps, users);

      header.querySelector(".save-chain-btn").onclick = async (e) => {
        const btn = e.currentTarget;
        btn.disabled = true;
        btn.textContent = "Saving…";
        try {
          const res = await fetch(
            `/workbooks/api/${WORKBOOK_ID}/chain/site/${site.id}`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ steps }),
            }
          );
          const data = await res.json();
          if (!res.ok) {
            toast(data.error || "Failed to save chain.", "error");
            return;
          }
          toast(`${site.name} approval chain saved.`);
          chainData = data.data || data;
          approvalTabLoaded = false;
          loadApprovalTab();
        } catch {
          toast("Failed to save chain.", "error");
        } finally {
          btn.disabled = false;
          btn.textContent = "Save";
        }
      };

      return card;
    }

    function renderChainBody(container, site, steps, users) {
      container.innerHTML = "";
      const row = document.createElement("div");
      row.className = "flex items-center gap-0 min-w-max";

      row.appendChild(buildStaticNode("On submission", "Package\nenters review."));
      row.appendChild(buildArrow());

      const regularSteps = steps.filter(s => s.level_type !== "final");
      const finalStep = steps.find(s => s.level_type === "final");

      regularSteps.forEach((step, idx) => {
        row.appendChild(buildStepNode(step, idx, site, steps, users, container));
        row.appendChild(buildArrow());
      });

      if (finalStep) {
        row.appendChild(buildFinalNode(finalStep, site, steps, users, container));
        row.appendChild(buildArrow());
      }

      const addBtn = document.createElement("div");
      addBtn.className = "flex-shrink-0";
      addBtn.innerHTML = `
        <button type="button"
          class="flex h-24 w-28 flex-col items-center justify-center rounded-xl
                 border-2 border-dashed border-slate-300 bg-white text-slate-400
                 hover:border-indigo-400 hover:text-indigo-600 transition-colors
                 text-xs font-semibold gap-1">
          <span class="text-xl leading-none">+</span>
          <span>Add Step</span>
        </button>`;
      addBtn.querySelector("button").onclick = () => {
        const finalIdx = steps.findIndex(s => s.level_type === "final");
        const insertAt = finalIdx >= 0 ? finalIdx : steps.length;
        steps.splice(insertAt, 0, {
          level_number: insertAt + 1,
          level_name: `Review Step ${regularSteps.length + 1}`,
          level_type: "regular",
          user_id: null,
        });
        steps.forEach((s, i) => s.level_number = i + 1);
        renderChainBody(container, site, steps, users);
      };
      row.appendChild(addBtn);

      container.appendChild(row);
    }

    function buildStaticNode(title, subtitle) {
      const el = document.createElement("div");
      el.className = "flex-shrink-0 w-28 h-24 rounded-xl border border-slate-200 bg-slate-50 flex flex-col items-center justify-center text-center px-2";
      el.innerHTML = `
        <div class="text-xs font-semibold text-slate-600">${esc(title)}</div>
        <div class="mt-1 text-[10px] text-slate-400 leading-tight">${esc(subtitle)}</div>`;
      return el;
    }

    function buildArrow() {
      const el = document.createElement("div");
      el.className = "flex-shrink-0 flex items-center px-1 self-center";
      el.innerHTML = `
        <svg class="h-4 w-4 text-slate-300" fill="none" viewBox="0 0 24 24"
             stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
        </svg>`;
      return el;
    }

    function buildStepNode(step, idx, site, steps, users, container) {
      const el = document.createElement("div");
      el.className = "flex-shrink-0 w-36 rounded-xl border border-slate-200 bg-white p-3 flex flex-col gap-2";

      const userOptions = users.map(u =>
        `<option value="${u.id}" ${step.user_id === u.id ? "selected" : ""}>${esc(u.full_name)}</option>`
      ).join("");

      el.innerHTML = `
        <div class="text-[9px] font-bold uppercase tracking-wider text-slate-400">Review Step</div>
        <select class="step-user-select block w-full rounded-lg border border-slate-300
                       bg-white px-2 py-1.5 text-xs focus:border-indigo-500 focus:ring-indigo-500">
          <option value="">Select reviewer</option>
          ${userOptions}
        </select>
        <button type="button"
          class="remove-step-btn text-[10px] font-semibold text-rose-500 hover:underline text-left">
          Remove step
        </button>`;

      el.querySelector(".step-user-select").onchange = (e) => {
        step.user_id = e.target.value ? parseInt(e.target.value) : null;
      };
      el.querySelector(".remove-step-btn").onclick = () => {
        const stepIdx = steps.indexOf(step);
        if (stepIdx >= 0) steps.splice(stepIdx, 1);
        steps.forEach((s, i) => s.level_number = i + 1);
        renderChainBody(container, site, steps, users);
      };

      return el;
    }

    function buildFinalNode(step, site, steps, users, container) {
      const el = document.createElement("div");
      el.className = "flex-shrink-0 w-36 rounded-xl border border-emerald-200 bg-emerald-50 p-3 flex flex-col gap-2";

      const userOptions = users.map(u =>
        `<option value="${u.id}" ${step.user_id === u.id ? "selected" : ""}>${esc(u.full_name)}</option>`
      ).join("");

      el.innerHTML = `
        <div class="text-[9px] font-bold uppercase tracking-wider text-emerald-600">Final Approval</div>
        <select class="final-user-select block w-full rounded-lg border border-emerald-200
                       bg-white px-2 py-1.5 text-xs focus:border-indigo-500 focus:ring-indigo-500">
          <option value="">Select final reviewer</option>
          ${userOptions}
        </select>
        <div class="text-[10px] text-emerald-600 font-medium">Locks &amp; releases data</div>`;

      el.querySelector(".final-user-select").onchange = (e) => {
        step.user_id = e.target.value ? parseInt(e.target.value) : null;
      };

      return el;
    }

    // ── Sites tab ─────────────────────────────────────────────────────────────

    async function loadSitesTab() {
      sitesTabLoaded = true;
      const content = document.getElementById("sites-tab-content");
      if (!content) return;
      content.innerHTML = `
        <div class="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm italic text-slate-400 shadow-sm">
          Loading sites…
        </div>
      `;
      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/sites`);
        const sites = await r.json();
        await renderSitesTab(sites);
        loadReadiness();
      } catch {
        content.innerHTML = `
          <div class="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm font-semibold text-rose-700 shadow-sm">
            Failed to load sites.
          </div>
        `;
      }
    }

    async function renderSitesTab(sites) {
      const content = document.getElementById("sites-tab-content");
      if (!content) return;

      if (!sites.length) {
        content.innerHTML = `
          <div class="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
            <p class="text-sm font-semibold text-slate-700">No sites assigned yet.</p>
            <p class="mt-2 text-xs text-slate-400">Assign a site to this workbook to configure submitters.</p>
            <button class="mt-5 inline-flex items-center rounded-lg bg-[#1a3a6b] px-4 py-2 text-sm font-semibold text-white shadow hover:bg-[#1e4280]"
              id="btn-add-site-empty">+ Add Site</button>
          </div>
        `;
        document.getElementById("btn-add-site-empty").onclick = openAddSiteModal;
        return;
      }

      const submitterResults = await Promise.all(
        sites.map(site =>
          fetch(`/workbooks/api/${WORKBOOK_ID}/sites/${site.id}/submitters`)
            .then(r => r.json())
            .catch(() => [])
        )
      );

      content.innerHTML = `
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-sm font-bold text-slate-600">Sites assigned to this workbook</h2>
          <button id="btn-add-site-header"
            class="inline-flex items-center rounded-lg bg-[#1a3a6b] px-3 py-1.5 text-xs font-semibold text-white shadow hover:bg-[#1e4280]">
            + Add Site
          </button>
        </div>
        <div id="sites-cards-grid" class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"></div>
      `;
      document.getElementById("btn-add-site-header").onclick = openAddSiteModal;

      const grid = document.getElementById("sites-cards-grid");
      sites.forEach((site, i) => {
        const submitters = submitterResults[i] || [];
        const card = document.createElement("div");
        card.className = "rounded-xl border border-slate-200 bg-white p-4 shadow-sm";

        const submitterRows = submitters.map(u => `
          <div class="flex items-center justify-between text-xs py-1">
            <span class="text-slate-700 font-medium">${esc(u.full_name)} · ${esc(u.email)}</span>
            <button class="text-rose-600 hover:underline text-xs font-semibold"
              onclick="removeSubmitter(${site.id}, ${u.id})">remove</button>
          </div>
        `).join("");

        card.innerHTML = `
          <div class="flex items-start justify-between mb-1">
            <div>
              <div class="font-bold text-slate-800 text-sm">${esc(site.name)}</div>
              <div class="text-[10px] font-mono text-slate-400">${esc(site.code)}</div>
            </div>
            <button class="remove-site-btn text-slate-300 hover:text-rose-500 text-lg font-bold leading-none"
              data-site-id="${site.id}" title="Remove site">×</button>
          </div>
          <hr class="my-3 border-slate-100">
          <div class="flex items-center justify-between mb-2">
            <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Submitters</span>
            <button class="text-xs font-semibold text-[#1a3a6b] hover:underline"
              onclick="openAddSubmitterModal(${site.id}, ${JSON.stringify(site.name).replace(/"/g, '&quot;')})">+ Add</button>
          </div>
          <div class="space-y-0">
            ${submitters.length ? submitterRows : '<p class="text-xs italic text-slate-400">No submitters assigned yet.</p>'}
          </div>
        `;

        card.querySelector(".remove-site-btn").onclick = () => removeSiteFromWorkbook(site.id);
        grid.appendChild(card);
      });
    }

    async function removeSiteFromWorkbook(siteId) {
      if (!confirm("Remove this site from the workbook? All submitter assignments for this site will also be removed.")) return;
      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/sites/${siteId}`, { method: "DELETE" });
        const data = await r.json();
        if (!r.ok) { toast(data.error || "Failed to remove site.", "error"); return; }
        toast("Site removed.", "warn");
        sitesTabLoaded = false;
        loadSitesTab();
      } catch {
        toast("Failed to remove site.", "error");
      }
    }

    function openAddSiteModal() {
      if (!addSiteModal) return;
      addSiteModal.classList.remove("hidden");
      addSiteModal.classList.add("flex");
      loadAssignableSites();
    }

    async function loadAssignableSites() {
      if (!addSiteList) return;
      addSiteList.innerHTML = '<p class="text-xs text-slate-400 italic text-center py-6">Loading sites…</p>';
      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/assignable-sites`);
        const sites = await r.json();
        if (!sites.length) {
          addSiteList.innerHTML = '<p class="text-xs text-slate-400 italic text-center py-6">All sites are already assigned.</p>';
          return;
        }
        addSiteList.innerHTML = "";
        sites.forEach(site => {
          const btn = document.createElement("button");
          btn.className = "w-full text-left px-4 py-3 rounded-lg hover:bg-indigo-50 border border-transparent hover:border-indigo-200 transition-colors";
          btn.innerHTML = `
            <div class="font-semibold text-sm text-slate-800">${esc(site.name)}</div>
            <div class="text-[10px] font-mono text-slate-400">${esc(site.code)}</div>
          `;
          btn.onclick = () => assignSite(site.id, btn);
          addSiteList.appendChild(btn);
        });
      } catch {
        addSiteList.innerHTML = '<p class="text-xs text-rose-600 text-center py-6">Failed to load sites.</p>';
      }
    }

    async function assignSite(siteId, btn) {
      btn.disabled = true;
      btn.classList.add("opacity-50");
      try {
        const r = await fetch(`/workbooks/api/${WORKBOOK_ID}/sites`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ site_id: siteId }),
        });
        const data = await r.json();
        if (!r.ok) {
          toast(data.error || "Failed to add site.", "error");
          btn.disabled = false;
          btn.classList.remove("opacity-50");
          return;
        }
        toast("Site added.");
        sitesTabLoaded = false;
        closeAddSiteModal();
        loadSitesTab();
      } catch {
        toast("Failed to add site.", "error");
        btn.disabled = false;
        btn.classList.remove("opacity-50");
      }
    }

    function closeAddSiteModal() {
      if (!addSiteModal) return;
      addSiteModal.classList.add("hidden");
      addSiteModal.classList.remove("flex");
    }

    if (btnCloseAddSite) btnCloseAddSite.onclick = closeAddSiteModal;
    if (btnCloseAddSiteFooter) btnCloseAddSiteFooter.onclick = closeAddSiteModal;

    // ── Submitters ────────────────────────────────────────────────────────────

    function openAddSubmitterModal(siteId, siteName) {
      activeSiteIdForSubmitters = siteId;
      const titleEl = document.getElementById("add-submitter-modal-title");
      if (titleEl) titleEl.textContent = `Add Submitter — ${siteName}`;
      const modal = document.getElementById("modal-add-submitter");
      if (!modal) return;
      modal.classList.remove("hidden");
      modal.classList.add("flex");
      loadEligibleSubmitters(siteId);
    }

    async function loadEligibleSubmitters(siteId) {
      const list = document.getElementById("eligible-submitters-list");
      if (!list) return;
      list.innerHTML = '<p class="text-xs italic text-slate-400 text-center py-4">Loading…</p>';
      try {
        const res = await fetch(`/workbooks/api/${WORKBOOK_ID}/sites/${siteId}/eligible-submitters`);
        const users = await res.json();
        if (!users.length) {
          list.innerHTML = '<p class="text-xs italic text-slate-400 text-center py-4">All eligible submitters are already assigned, or no users have submission permission for this site.</p>';
          return;
        }
        list.innerHTML = "";
        users.forEach(user => {
          const row = document.createElement("div");
          row.className = "flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm";
          row.innerHTML = `
            <div>
              <div class="font-semibold text-slate-800">${esc(user.full_name)}</div>
              <div class="text-xs text-slate-400">${esc(user.email)}</div>
            </div>
            <button
              class="rounded-lg bg-[#1a3a6b] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1e4280]"
              onclick="addSubmitter(${siteId}, ${user.id}, this)">
              Add
            </button>
          `;
          list.appendChild(row);
        });
      } catch {
        list.innerHTML = '<p class="text-xs text-rose-600 text-center py-4">Failed to load eligible submitters.</p>';
      }
    }

    async function addSubmitter(siteId, userId, buttonEl) {
      buttonEl.disabled = true;
      buttonEl.textContent = "Adding…";
      try {
        const res = await fetch(`/workbooks/api/${WORKBOOK_ID}/sites/${siteId}/submitters`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: userId }),
        });
        const data = await res.json();
        if (!res.ok) {
          toast(data.error || "Failed to add submitter.", "error");
          buttonEl.disabled = false;
          buttonEl.textContent = "Add";
          return;
        }
        buttonEl.closest("div.flex").remove();
        toast("Submitter added.");
        sitesTabLoaded = false;
        loadSitesTab();
      } catch {
        toast("Failed to add submitter.", "error");
        buttonEl.disabled = false;
        buttonEl.textContent = "Add";
      }
    }

    async function removeSubmitter(siteId, userId) {
      if (!confirm("Remove this submitter?")) return;
      try {
        const res = await fetch(`/workbooks/api/${WORKBOOK_ID}/sites/${siteId}/submitters/${userId}`, { method: "DELETE" });
        const data = await res.json();
        if (!res.ok) { toast(data.error || "Failed to remove submitter.", "error"); return; }
        toast("Submitter removed.");
        sitesTabLoaded = false;
        loadSitesTab();
      } catch {
        toast("Failed to remove submitter.", "error");
      }
    }

    const btnCloseAddSubmitter = document.getElementById("btn-close-add-submitter");
    const btnCancelAddSubmitter = document.getElementById("btn-cancel-add-submitter");

    function closeAddSubmitterModal() {
      const modal = document.getElementById("modal-add-submitter");
      if (!modal) return;
      modal.classList.add("hidden");
      modal.classList.remove("flex");
      activeSiteIdForSubmitters = null;
    }

    if (btnCloseAddSubmitter) btnCloseAddSubmitter.addEventListener("click", closeAddSubmitterModal);
    if (btnCancelAddSubmitter) btnCancelAddSubmitter.addEventListener("click", closeAddSubmitterModal);

    window.openAddSubmitterModal = openAddSubmitterModal;
    window.addSubmitter = addSubmitter;
    window.removeSubmitter = removeSubmitter;
  }
});
