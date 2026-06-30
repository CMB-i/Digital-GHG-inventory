document.addEventListener("DOMContentLoaded", function () {
  let formsList = [];
  let currentFields = [];
  let currentSections = [];
  let availableValueSets = [];
  let availableFormulas = [];
  let activeSites = [];
  let sitesMap = {};

  let selectedFormId = null;
  let selectedVersionId = null;
  let currentVersionStatus = null;
  let selectedFieldCode = null;
  let activeSectionCode = "";
  let isUnsaved = false;
  let pendingPrefill = null;
  let workspaceMode = "fields";
  let isWorkbookContext = false;
  let builderIsEditable = true;

  // View containers
  const listView = document.getElementById("list-view");
  const step1View = document.getElementById("step1-view");
  const step2View = document.getElementById("step2-view");

  // Table body in list-view
  const formsListBody = document.getElementById("forms-list-body");

  // Step 2 elements
  const builderFormTitle = document.getElementById("builder-form-title");
  const builderVersionBadge = document.getElementById("builder-version-badge");
  const formWorkspace = document.getElementById("form-workspace");
  const saveStatusText = document.getElementById("save-status-text");
  const btnSaveLayout = document.getElementById("btn-save-layout");
  const btnPublishForm = document.getElementById("btn-publish-form");
  const btnEditAsDraft = document.getElementById("btn-edit-as-draft");
  const publishErrors = document.getElementById("publish-errors");
  const publishErrorsList = document.getElementById("publish-errors-list");
  const btnAddSection = document.getElementById("btn-add-section");
  const sectionsList = document.getElementById("sections-list");
  const workspaceSectionTitle = document.getElementById("workspace-section-title");
  const workspaceSectionMeta = document.getElementById("workspace-section-meta");
  const workspaceTabFields = document.getElementById("workspace-tab-fields");
  const workspaceTabPreview = document.getElementById("workspace-tab-preview");
  const builderPreviewPanel = document.getElementById("builder-preview-panel");
  const builderPreviewEmpty = document.getElementById("builder-preview-empty");
  const builderPreviewTableWrap = document.getElementById("builder-preview-table-wrap");
  const builderPreviewWorkbookHead = document.getElementById("builder-preview-workbook-head");
  const builderPreviewWorkbookBody = document.getElementById("builder-preview-workbook-body");
  const builderPreviewStaticWrap = document.getElementById("builder-preview-static-wrap");
  const builderPreviewStaticHead = document.getElementById("builder-preview-static-head");
  const builderPreviewStaticBody = document.getElementById("builder-preview-static-body");
  const builderPreviewResultsOverflow = document.getElementById("builder-preview-results-overflow");

  // Inspector elements
  const inspectorPanel = document.getElementById("inspector-panel");
  const inspectorEmpty = document.getElementById("inspector-empty-state");
  const inspectorSummary = document.getElementById("inspector-summary");
  const formFieldProperties = document.getElementById("form-field-properties");
  const btnDeleteField = document.getElementById("btn-delete-field");
  const btnMoveUp = document.getElementById("btn-move-up");
  const btnMoveDown = document.getElementById("btn-move-down");
  const propSection = document.getElementById("prop-section");
  const propFrequency = document.getElementById("prop-frequency");
  const propCalcPlacement = document.getElementById("prop-calc-placement");
  const dropdownOptionsList = document.getElementById("dropdown-options-list");
  const btnAddDropdownOption = document.getElementById("btn-add-dropdown-option");

  // Step 1 Details elements
  const formDetailsSubmit = document.getElementById("form-details-submit");
  const dfCode = document.getElementById("df-code");
  const dfName = document.getElementById("df-name");
  const dfGri = document.getElementById("df-gri");
  const dfSitesList = document.getElementById("df-sites-list");
  const dfFrequency = document.getElementById("df-frequency");
  const dfDesc = document.getElementById("df-desc");
  const step1Title = document.getElementById("step1-title");

  // SPOC Preview elements
  const previewOverlay = document.getElementById("preview-overlay");
  const pvTitle = document.getElementById("pv-title");
  const pvMeta = document.getElementById("pv-meta");
  const previewWorkspaceEl = document.getElementById("preview-workspace-el");
  const previewEmpty = document.getElementById("preview-empty");
  const previewTableWrap = document.getElementById("preview-table-wrap");
  const previewWorkbookHead = document.getElementById("preview-workbook-head");
  const previewWorkbookBody = document.getElementById("preview-workbook-body");
  const previewStaticWrap = document.getElementById("preview-static-wrap");
  const previewStaticHead = document.getElementById("preview-static-head");
  const previewStaticBody = document.getElementById("preview-static-body");
  const previewResultsOverflow = document.getElementById("preview-results-overflow");

  // Toast Helper
  function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `p-4 rounded-xl shadow-lg border text-xs font-bold transition-all duration-300 transform translate-y-2 opacity-0 flex items-center justify-between ${
      type === "success"
        ? "bg-emerald-50 border-emerald-200 text-emerald-800"
        : "bg-rose-50 border-rose-200 text-rose-800"
    }`;
    toast.innerHTML = `
      <span>${message}</span>
      <button class="ml-4 font-normal text-slate-400 hover:text-slate-600">✕</button>
    `;
    toast.querySelector("button").onclick = () => toast.remove();
    container.appendChild(toast);

    // Animate in
    setTimeout(() => {
      toast.classList.remove("translate-y-2", "opacity-0");
    }, 10);

    // Auto remove
    setTimeout(() => {
      toast.classList.add("translate-y-2", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  function normalizeCode(value) {
    return (value || "").trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function humanizeType(value) {
    return String(value || "text")
      .replace(/_/g, " ")
      .replace(/\b\w/g, char => char.toUpperCase());
  }

  function layoutDisplayName(type) {
    const map = { monthly_table: "Monthly table", annual_table: "Annual table", reference_table: "Reference table" };
    return map[type] || "Monthly table";
  }

  function fieldType(field) {
    return String((field && field.field_type) || "").trim().toLowerCase();
  }

  function previewOrderedFields(fields, sections) {
    const allFields = Array.isArray(fields) ? fields : [];
    const allSections = Array.isArray(sections) ? sections : [];
    if (!allSections.length) {
      return [...allFields].sort((a, b) => (a.display_order || 0) - (b.display_order || 0));
    }
    const ordered = [];
    allSections.forEach(section => {
      ordered.push(...allFields
        .filter(field => field.section_id === section.id)
        .sort((a, b) => (a.display_order || 0) - (b.display_order || 0)));
    });
    const sectionIds = new Set(allSections.map(section => section.id));
    ordered.push(...allFields
      .filter(field => !field.section_id || !sectionIds.has(field.section_id))
      .sort((a, b) => (a.display_order || 0) - (b.display_order || 0)));
    return ordered;
  }

  function isPreviewNonMonthlyField(field, context) {
    if (isSheetResultField(field)) return true;
    if (window.WorkbookSheet && typeof window.WorkbookSheet.isFieldNonMonthly === "function") {
      return window.WorkbookSheet.isFieldNonMonthly(field, context);
    }
    const frequency = String((field && field.frequency) || "monthly").trim().toLowerCase();
    if (frequency === "annual" || frequency === "static") return true;
    const section = (context.sections || []).find(item => item.id === field.section_id);
    const layoutType = String((section && section.layout_type) || "monthly_table").trim().toLowerCase();
    return layoutType === "annual_table" || layoutType === "reference_table";
  }

  function isSheetResultField(field) {
    const config = field && field.field_config ? field.field_config : {};
    return (
      field &&
      field.field_type === "calculated" &&
      (
        config.field_scope === "annual_result" ||
        config.result_role === "aggregate_result" ||
        config.result_role === "formula_result" ||
        config.display_region === "below_monthly_table" ||
        config.display_region === "under_input_column"
      )
    );
  }

  function setResultFieldWorkflowControls(isResult) {
    ["prop-required", "prop-remarks-req", "prop-proof-req"].forEach(id => {
      const input = document.getElementById(id);
      if (!input) return;
      input.disabled = isResult || !builderIsEditable;
      if (isResult) input.checked = false;
    });
  }

  function dropdownSelectHtml(field) {
    const options = normalizeDropdownOptions(field && field.field_config ? field.field_config.options : []);
    return `
      <select class="workbook-cell-control min-h-9 w-full cursor-not-allowed border-0 bg-transparent px-2 py-1.5 text-sm text-slate-500 outline-none" disabled>
        <option value="">Select...</option>
        ${options.map(option => `<option value="${escapeHtml(option.entry_code || option.entry_label || "")}">${escapeHtml(option.entry_label || option.entry_code || "")}</option>`).join("")}
      </select>
    `;
  }

  function modalPreviewTarget() {
    return {
      empty: previewEmpty,
      tableWrap: previewTableWrap,
      head: previewWorkbookHead,
      body: previewWorkbookBody,
      staticWrap: previewStaticWrap,
      staticHead: previewStaticHead,
      staticBody: previewStaticBody,
      overflowEl: previewResultsOverflow,
    };
  }

  function builderPreviewTarget() {
    return {
      empty: builderPreviewEmpty,
      tableWrap: builderPreviewTableWrap,
      head: builderPreviewWorkbookHead,
      body: builderPreviewWorkbookBody,
      staticWrap: builderPreviewStaticWrap,
      staticHead: builderPreviewStaticHead,
      staticBody: builderPreviewStaticBody,
      overflowEl: builderPreviewResultsOverflow,
    };
  }

  function renderPreviewResultsOverflow(target, sheetResults) {
    if (!target || !target.overflowEl) return;
    if (!window.WorkbookSheet || typeof window.WorkbookSheet.renderSheetResultsOverflowHtml !== "function") {
      target.overflowEl.classList.add("hidden");
      target.overflowEl.innerHTML = "";
      return;
    }
    const html = window.WorkbookSheet.renderSheetResultsOverflowHtml(sheetResults || []);
    if (!html) {
      target.overflowEl.classList.add("hidden");
      target.overflowEl.innerHTML = "";
      return;
    }
    target.overflowEl.innerHTML = html;
    target.overflowEl.classList.remove("hidden");
  }

  function resetPreviewTarget(target, message = "Loading preview...") {
    if (!target) return;
    if (target.empty) {
      target.empty.classList.remove("hidden");
      target.empty.textContent = message;
    }
    if (target.tableWrap) target.tableWrap.classList.add("hidden");
    if (target.staticWrap) target.staticWrap.classList.add("hidden");
    if (target.head) target.head.innerHTML = "";
    if (target.body) target.body.innerHTML = "";
    if (target.staticHead) target.staticHead.innerHTML = "";
    if (target.staticBody) target.staticBody.innerHTML = "";
    if (target.overflowEl) {
      target.overflowEl.classList.add("hidden");
      target.overflowEl.innerHTML = "";
    }
  }

  function previewUrl(formId, versionId) {
    const params = new URLSearchParams();
    if (versionId) params.set("version_id", versionId);
    return `/module/FORMBLD/forms/${formId}/preview-spoc${params.toString() ? `?${params.toString()}` : ""}`;
  }

  function loadPreviewContext(formId, versionId) {
    return fetch(previewUrl(formId, versionId))
      .then(res => {
        if (!res.ok) throw new Error("Failed to load preview.");
        return res.json();
      });
  }

  function enhancePreviewMonthlyCells(target, context, monthlyFields) {
    if (!target || !target.body) return;
    if (target.head) {
      target.head.querySelectorAll("tr:first-child th[colspan]").forEach(header => {
        if (!header.textContent.trim()) return;
        header.classList.remove("bg-slate-100", "text-slate-700");
        header.classList.add("bg-navy", "text-white");
      });
    }
    const rows = target.body.querySelectorAll("tr[data-row-key]");
    rows.forEach(row => {
      monthlyFields.forEach((field, idx) => {
        const cell = row.children[idx + 1];
        if (!cell) return;
        cell.dataset.fieldCode = field.field_code || "";
        if (fieldType(field) === "dropdown") {
          cell.classList.remove("text-center");
          cell.classList.add("bg-slate-50", "text-slate-500");
          cell.innerHTML = `<div class="relative min-h-[48px]">${dropdownSelectHtml(field)}</div>`;
        } else if (fieldType(field) === "calculated") {
          cell.classList.add("bg-[#eef3fa]", "text-slate-500");
          cell.innerHTML = `
            <div class="flex min-h-[48px] items-center justify-center gap-1.5 px-2 py-2 text-sm font-semibold text-slate-500">
              <span title="Calculated field">🔒</span>
              <span>—</span>
            </div>
          `;
        }
      });
    });
  }

  function renderPreviewWorkbookContext(context, target) {
    if (!window.WorkbookSheet || !target || !target.head || !target.body) {
      throw new Error("Workbook preview renderer is unavailable.");
    }

    const fields = context.fields || [];
    if (!fields.length) {
      if (target.tableWrap) target.tableWrap.classList.add("hidden");
      if (target.staticWrap) target.staticWrap.classList.add("hidden");
      if (target.empty) {
        target.empty.classList.remove("hidden");
        target.empty.textContent = "No fields configured for this workbook.";
      }
      return;
    }

    if (target.empty) target.empty.classList.add("hidden");
    if (target.tableWrap) target.tableWrap.classList.remove("hidden");
    if (target.staticWrap) target.staticWrap.classList.add("hidden");

    const orderedFields = previewOrderedFields(fields, context.sections || []);
    const monthlyFields = orderedFields.filter(field => !isPreviewNonMonthlyField(field, context));
    const nonMonthlyFields = orderedFields.filter(field =>
      isPreviewNonMonthlyField(field, context) && !isSheetResultField(field)
    );
    const sheetResults = context.sheet_results || [];

    window.WorkbookSheet.render({
      mode: "calc_results",
      headEl: target.head,
      bodyEl: target.body,
      fields: monthlyFields,
      sections: context.sections || [],
      workbookValues: context.workbook_values || {},
      rows: context.rows || [],
      sheetResults,
      selectedRowKey: null,
    });
    enhancePreviewMonthlyCells(target, context, monthlyFields);
    renderPreviewResultsOverflow(target, sheetResults);

    if (nonMonthlyFields.length && target.staticHead && target.staticBody) {
      const unsectionedStaticSectionId = "__preview_static_values";
      let staticFields = nonMonthlyFields.map(field => ({ ...field }));
      const hasUnsectionedStatic = staticFields.some(field => !field.section_id);
      if (hasUnsectionedStatic) {
        staticFields = staticFields.map(field => (
          field.section_id
            ? field
            : { ...field, section_id: unsectionedStaticSectionId }
        ));
      }
      const staticSections = (context.sections || []).filter(section =>
        nonMonthlyFields.some(field => field.section_id === section.id)
      );
      if (hasUnsectionedStatic) {
        staticSections.push({
          id: unsectionedStaticSectionId,
          name: "Annual / static fields",
          code: "annual_static_fields",
          layout_type: "annual_table",
          display_order: 9999,
          description: "",
        });
      }
      window.WorkbookSheet.render({
        mode: "entry",
        headEl: target.staticHead,
        bodyEl: target.staticBody,
        fields: staticFields,
        sections: staticSections,
        workbookValues: context.workbook_values || {},
        rows: context.rows || [],
        selectedRowKey: null,
      });
      target.staticBody.querySelectorAll("tr[data-row-key]").forEach(row => row.remove());
      target.staticHead.innerHTML = "";
      if (target.staticBody.children.length && target.staticWrap) {
        target.staticWrap.classList.remove("hidden");
      }
    }
  }

  function setWorkspaceTabStyles() {
    if (workspaceTabFields) {
      workspaceTabFields.className = workspaceMode === "fields"
        ? "rounded-md bg-[#1a3a6b] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-sm"
        : "rounded-md px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500 hover:bg-slate-50 hover:text-[#1a3a6b]";
    }
    if (workspaceTabPreview) {
      workspaceTabPreview.className = workspaceMode === "preview"
        ? "rounded-md bg-[#1a3a6b] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-sm"
        : "rounded-md px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500 hover:bg-slate-50 hover:text-[#1a3a6b]";
    }
  }

  function showWorkspaceFields() {
    workspaceMode = "fields";
    setWorkspaceTabStyles();
    if (formWorkspace) formWorkspace.classList.remove("hidden");
    if (builderPreviewPanel) builderPreviewPanel.classList.add("hidden");
  }

  function refreshBuilderPreview() {
    if (!selectedFormId || !selectedVersionId) {
      resetPreviewTarget(builderPreviewTarget(), "No sheet is currently loaded for preview.");
      return;
    }
    const target = builderPreviewTarget();
    resetPreviewTarget(target);
    loadPreviewContext(selectedFormId, selectedVersionId)
      .then(data => {
        renderPreviewWorkbookContext(data, target);
      })
      .catch(err => {
        console.error("Error loading inline preview fields:", err);
        if (target.empty) {
          target.empty.classList.remove("hidden");
          target.empty.textContent = err.message || "Error loading preview.";
        }
        showToast("Error loading workbook preview.", "error");
      });
  }

  function showWorkspacePreview() {
    workspaceMode = "preview";
    setWorkspaceTabStyles();
    if (formWorkspace) formWorkspace.classList.add("hidden");
    if (builderPreviewPanel) builderPreviewPanel.classList.remove("hidden");
    refreshBuilderPreview();
  }

  function activeSection() {
    if (!activeSectionCode) return null;
    return currentSections.find(section => section.code === activeSectionCode) || null;
  }

  function orderedSections() {
    return currentSections
      .slice()
      .sort((a, b) => (a.display_order || 0) - (b.display_order || 0));
  }

  function sameSection(field, sectionCode) {
    return (field.section_code || "") === (sectionCode || "");
  }

  function fieldsForActiveSection() {
    return currentFields
      .filter(field => {
        if (!activeSectionCode) return true;
        return field.section_code === activeSectionCode;
      })
      .slice()
      .sort((a, b) => (a.display_order || 0) - (b.display_order || 0));
  }

  function fieldsForSection(sectionCode) {
    return currentFields
      .filter(field => sameSection(field, sectionCode))
      .slice()
      .sort((a, b) => (a.display_order || 0) - (b.display_order || 0));
  }

  function normalizeFieldDisplayOrder() {
    const ordered = [];
    fieldsForSection("").forEach(field => ordered.push(field));
    orderedSections().forEach(section => {
      fieldsForSection(section.code).forEach(field => ordered.push(field));
    });
    const seen = new Set();
    ordered.forEach((field, idx) => {
      field.display_order = idx + 1;
      seen.add(field.field_code);
    });
    currentFields
      .filter(field => !seen.has(field.field_code))
      .forEach(field => {
        field.display_order = ordered.length + 1;
        ordered.push(field);
      });
    currentFields = ordered;
  }

  function normalizeSectionDisplayOrder() {
    currentSections = orderedSections().map((section, idx) => ({
      ...section,
      display_order: idx + 1,
    }));
  }

  function moveSection(code, direction) {
    syncSectionsFromDom();
    const sections = orderedSections();
    const idx = sections.findIndex(section => section.code === code);
    const targetIdx = idx + direction;
    if (idx < 0 || targetIdx < 0 || targetIdx >= sections.length) return;
    const moving = sections[idx];
    sections[idx] = sections[targetIdx];
    sections[targetIdx] = moving;
    currentSections = sections.map((section, orderIdx) => ({
      ...section,
      display_order: orderIdx + 1,
    }));
    activeSectionCode = code;
    normalizeFieldDisplayOrder();
    isUnsaved = true;
    updateSaveStatusText();
    renderSections();
    renderWorkspace();
    if (selectedFieldCode) openInspector(selectedFieldCode);
    saveDraftLayout().catch(() => {});
  }

  function moveFieldWithinActiveSection(fieldCode, direction) {
    const field = currentFields.find(item => item.field_code === fieldCode);
    if (!field) return;
    const sectionCode = field.section_code || "";
    const sectionFields = fieldsForSection(sectionCode);
    const idx = sectionFields.findIndex(item => item.field_code === fieldCode);
    const targetIdx = idx + direction;
    if (idx < 0 || targetIdx < 0 || targetIdx >= sectionFields.length) return;
    const moving = sectionFields[idx];
    sectionFields[idx] = sectionFields[targetIdx];
    sectionFields[targetIdx] = moving;

    const previousFields = currentFields.slice();
    const ordered = [];
    ["", ...orderedSections().map(section => section.code)].forEach(code => {
      const source = code === sectionCode ? sectionFields : fieldsForSection(code);
      source.forEach(item => ordered.push(item));
    });
    const seen = new Set();
    currentFields = ordered.filter(item => {
      if (seen.has(item.field_code)) return false;
      seen.add(item.field_code);
      return true;
    });
    previousFields
      .filter(item => !seen.has(item.field_code))
      .forEach(item => currentFields.push(item));
    currentFields.forEach((item, orderIdx) => {
      item.display_order = orderIdx + 1;
    });
    selectedFieldCode = fieldCode;
    isUnsaved = true;
    updateSaveStatusText();
    renderWorkspace();
    openInspector(fieldCode);
    saveDraftLayout().catch(() => {});
  }

  function normalizeDropdownOptions(options) {
    if (!Array.isArray(options)) return [];
    return options
      .map((option) => {
        if (option && typeof option === "object") {
          const code = String(option.entry_code || option.code || option.value || "").trim();
          const label = String(option.entry_label || option.label || option.name || code).trim();
          return {
            entry_code: code || label,
            entry_label: label || code,
          };
        }
        const text = String(option ?? "").trim();
        return {
          entry_code: normalizeCode(text),
          entry_label: text,
        };
      })
      .filter(option => option.entry_label || option.entry_code);
  }

  function dropdownOptionCount(field) {
    return normalizeDropdownOptions(field && field.field_config ? field.field_config.options : []).length;
  }

  function dropdownOptionRow(value = "") {
    return `
      <div class="dropdown-option-row flex items-center gap-2">
        <input type="text" class="dropdown-option-input block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-xs h-9 px-3 border" value="${escapeHtml(value)}" placeholder="Option label">
        <button type="button" class="dropdown-option-remove h-9 rounded-lg border border-slate-200 px-2 text-[10px] font-bold text-rose-600 hover:bg-rose-50">Remove</button>
      </div>
    `;
  }

  function renderDropdownOptionsEditor(field) {
    if (!dropdownOptionsList) return;
    const options = normalizeDropdownOptions(field && field.field_config ? field.field_config.options : []);
    const rows = options.length ? options : [{ entry_label: "" }];
    dropdownOptionsList.innerHTML = rows
      .map(option => dropdownOptionRow(option.entry_label || option.entry_code || ""))
      .join("");
  }

  function collectDropdownOptions() {
    if (!dropdownOptionsList) return [];
    const seen = new Set();
    const options = [];
    dropdownOptionsList.querySelectorAll(".dropdown-option-input").forEach((input) => {
      const label = input.value.trim();
      if (!label) return;
      let code = normalizeCode(label);
      if (!code) code = `option_${options.length + 1}`;
      let uniqueCode = code;
      let suffix = 2;
      while (seen.has(uniqueCode)) {
        uniqueCode = `${code}_${suffix}`;
        suffix += 1;
      }
      seen.add(uniqueCode);
      options.push({
        entry_code: uniqueCode,
        entry_label: label,
      });
    });
    return options;
  }

  // --- View Switching ---
  window.showList = function () {
    showWorkspaceFields();
    step1View.classList.add("hidden");
    step2View.classList.add("hidden");
    listView.classList.remove("hidden");
    document.body.classList.remove("builder-canvas-active");
    loadForms();
  };

  window.startNew = function () {
    showWorkspaceFields();
    listView.classList.add("hidden");
    step2View.classList.add("hidden");
    step1View.classList.remove("hidden");
    document.body.classList.remove("builder-canvas-active");

    step1Title.textContent = "New Sheet · Step 1 — Sheet Details";
    selectedFormId = null;
    selectedVersionId = null;

    // Reset fields
    dfCode.value = "";
    dfCode.disabled = false;
    dfName.value = "";
    dfGri.value = "";
    dfFrequency.value = "Monthly";
    dfDesc.value = "";

    // Uncheck all sites
    const checkboxes = dfSitesList.querySelectorAll("input[type='checkbox']");
    checkboxes.forEach(cb => cb.checked = false);
  };

  window.editFormDetails = function (formId) {
    const form = formsList.find(x => x.id === formId);
    if (!form) return;

    listView.classList.add("hidden");
    step2View.classList.add("hidden");
    step1View.classList.remove("hidden");
    document.body.classList.remove("builder-canvas-active");

    step1Title.textContent = `Edit Sheet Details · ${form.display_name || form.name}`;
    selectedFormId = formId;
    selectedVersionId = form.latest_version_id;

    dfCode.value = form.code;
    dfCode.disabled = true; // Code cannot change once created
    dfName.value = form.display_name || form.name;
    dfGri.value = form.gri_code || "";
    dfFrequency.value = form.frequency || "Monthly";
    dfDesc.value = form.description || "";

    // Check sites
    const checkboxes = dfSitesList.querySelectorAll("input[type='checkbox']");
    checkboxes.forEach(cb => {
      const siteId = parseInt(cb.value);
      cb.checked = (form.sites || []).includes(siteId);
    });
  };

  window.editFormLayout = function (formId, versionId) {
    selectedFormId = formId;
    selectedVersionId = versionId;
    showWorkspaceFields();

    listView.classList.add("hidden");
    step1View.classList.add("hidden");
    step2View.classList.remove("hidden");
    document.body.classList.add("builder-canvas-active");

    const form = formsList.find(x => x.id === formId);
    if (form) {
      builderFormTitle.textContent = form.display_name || form.name;
    }

    return loadVersionDetails(versionId);
  };

  window.editWorkbookCard = function (formId, versionId, status) {
    if (status === "Published") {
      createNewDraft(formId);
      return;
    }
    if (versionId) {
      editFormLayout(formId, versionId);
    }
  };

  // --- Initial Setup & Data Fetching ---
  function init() {
    // 1. Fetch sites
    fetch("/module/SITEMST/api")
      .then(res => res.json())
      .then(sites => {
        activeSites = sites;
        sitesMap = {};
        sites.forEach(s => {
          sitesMap[s.id] = s.name;
        });
        renderSitesCheckboxes();
        return loadForms();
      })
      .then(() => {
        checkUrlPrefill();
      })
      .catch(err => {
        console.error("Error initializing data:", err);
        showToast("Error loading startup data.", "error");
      });
  }

  function renderSitesCheckboxes() {
    dfSitesList.innerHTML = "";
    if (activeSites.length === 0) {
      dfSitesList.innerHTML = '<span class="text-slate-400 italic">No active sites found.</span>';
      return;
    }
    activeSites.forEach(s => {
      const label = document.createElement("label");
      label.className = "flex items-center space-x-2 text-xs font-semibold text-slate-700 cursor-pointer hover:bg-slate-100 p-1 rounded transition";
      label.innerHTML = `
        <input type="checkbox" name="df-sites" value="${s.id}" class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500">
        <span>${s.name} (${s.code})</span>
      `;
      dfSitesList.appendChild(label);
    });
  }

  // Fetch all forms on load or refresh
  function loadForms() {
    formsListBody.innerHTML = '<div class="rounded-xl border border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-400 shadow-sm md:col-span-2 xl:col-span-3">Loading sheets...</div>';

    return fetch("/module/FORMBLD/api")
      .then(res => res.json())
      .then(data => {
        formsList = data;
        formsListBody.innerHTML = "";

        if (data.length === 0) {
          formsListBody.innerHTML = `
            <div class="rounded-xl border border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-400 shadow-sm md:col-span-2 xl:col-span-3">
              No sheets created yet. Click "Create Sheet" to get started.
            </div>
          `;
          return;
        }

        data.forEach(form => {
          const card = document.createElement("article");
          card.className = "flex min-h-[220px] flex-col justify-between rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm transition hover:border-slate-300 hover:shadow-md";

          // Map site IDs to names
          let sitesText = "None";
          let siteCountText = "No sites";
          if (form.sites && form.sites.length > 0) {
            sitesText = form.sites.map(sid => sitesMap[sid] || sid).join(", ");
            siteCountText = `${form.sites.length} site${form.sites.length === 1 ? "" : "s"}`;
          }

          // Build status badge
          let statusBadge = "";
          const status = form.latest_version_status || "Draft";
          if (status === "Published") {
            statusBadge = '<span class="status-badge status-badge-success">Published</span>';
          } else if (status === "Archived") {
            statusBadge = '<span class="status-badge status-badge-neutral">Archived</span>';
          } else {
            statusBadge = '<span class="status-badge status-badge-warning">Draft</span>';
          }

          // Actions
          let editAction = "";
          let previewAction = "";
          let secondaryActions = [];
          if (form.latest_version_id) {
            editAction = `<button onclick="editWorkbookCard(${form.id}, ${form.latest_version_id}, '${escapeHtml(status)}')" class="btn btn-primary btn-sm min-w-[72px]" aria-label="Edit sheet ${escapeHtml(form.display_name || form.name)}">Edit</button>`;
            previewAction = `<button onclick="openPreview(${form.id}, ${form.latest_version_id})" class="btn btn-outline btn-sm min-w-[72px]" aria-label="Preview sheet ${escapeHtml(form.display_name || form.name)}">Preview</button>`;
          }
          if (status === "Draft" && form.latest_version_id) {
            secondaryActions.push(`<button onclick="editFormDetails(${form.id})" class="block w-full px-3 py-1.5 text-left text-xs font-semibold text-slate-600 hover:bg-slate-50">Edit details</button>`);
          }

          card.innerHTML = `
            <div class="space-y-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <h2 class="card-title truncate" title="${escapeHtml(form.display_name || form.name)}">${escapeHtml(form.display_name || form.name)}</h2>
                  <div class="mt-1 flex flex-wrap items-center gap-2 text-[11px] font-semibold text-slate-500">
                    <span class="font-mono">${escapeHtml(form.gri_code || form.code || "Sheet")}</span>
                    <span>v${escapeHtml(form.latest_version_num || 1)}</span>
                  </div>
                </div>
                ${statusBadge}
              </div>
              <div class="grid grid-cols-2 gap-3 text-xs">
                <div class="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Sites</div>
                  <div class="mt-1 font-bold text-slate-800" title="${escapeHtml(sitesText)}">${escapeHtml(siteCountText)}</div>
                </div>
                <div class="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Frequency</div>
                  <div class="mt-1 font-bold text-slate-800">${escapeHtml(form.frequency || "Monthly")}</div>
                </div>
              </div>
            </div>
            <div class="mt-5 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
              <div class="text-[11px] font-semibold text-slate-400">
                Sheet configuration
              </div>
              <div class="flex items-center gap-2">
                ${editAction}
                ${previewAction}
                ${secondaryActions.length ? `
                  <div class="relative group">
                    <button type="button" class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-sm font-bold text-slate-500 hover:bg-slate-50" aria-label="More actions">...</button>
                    <div class="absolute right-0 z-20 mt-1 hidden w-40 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg group-hover:block">
                      ${secondaryActions.join("")}
                    </div>
                  </div>
                ` : ""}
              </div>
            </div>
          `;
          formsListBody.appendChild(card);
        });
      })
      .catch(err => {
        console.error("Error loading forms:", err);
        showToast("Error loading sheets list.", "error");
      });
  }

  // --- Step 1 Details Form Submit ---
  formDetailsSubmit.onsubmit = function (e) {
    e.preventDefault();

    const name = dfName.value.trim();
    const code = dfCode.value.trim().toUpperCase().replace(/\s+/g, "_");
    const gri_code = dfGri.value.trim();
    const frequency = dfFrequency.value;
    const description = dfDesc.value.trim();

    // Collect checked sites
    const sites = [];
    dfSitesList.querySelectorAll("input[name='df-sites']:checked").forEach(cb => {
      sites.push(parseInt(cb.value));
    });

    if (sites.length === 0) {
      showToast("Please select at least one site applicability.", "error");
      return;
    }

    const payload = {
      name: name,
      code: code,
      display_name: name,
      gri_code: gri_code,
      frequency: frequency,
      sites: sites,
      description: description,
      description_text: description
    };

    const wbParams = new URLSearchParams(window.location.search);
    const contextWorkbookId = wbParams.get("workbook_id");
    if (contextWorkbookId) {
      payload.workbook_id = parseInt(contextWorkbookId);
    }

    if (selectedFormId === null) {
      // Create new form
      fetch("/module/FORMBLD/api", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(res => res.json())
        .then(resData => {
          if (resData.error) {
            showToast(resData.error, "error");
          } else {
            showToast("Sheet details saved successfully.");

            // Reload list, find the form and open Step 2
            fetch("/module/FORMBLD/api")
              .then(res => res.json())
              .then(data => {
                formsList = data;
                const newForm = data.find(x => x.code === code);
                if (newForm && newForm.latest_version_id) {
                  editFormLayout(newForm.id, newForm.latest_version_id);
                } else {
                  showList();
                }
              });
          }
        })
        .catch(err => {
          console.error("Error creating form:", err);
          showToast("Failed to create sheet.", "error");
        });
    } else {
      // Update form details
      fetch(`/module/FORMBLD/api/${selectedFormId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(res => res.json())
        .then(resData => {
          if (resData.error) {
            showToast(resData.error, "error");
          } else {
            showToast("Sheet details updated successfully.");

            // Go directly to layout canvas
            editFormLayout(selectedFormId, selectedVersionId);
          }
        })
        .catch(err => {
          console.error("Error updating form details:", err);
          showToast("Failed to update sheet details.", "error");
        });
    }
  };

  // --- Step 2 Layout Canvas Logic ---
  function loadVersionDetails(versionId) {
    const fieldCodeToRestore = selectedFieldCode;
    closeInspector();
    publishErrors.classList.add("hidden");

    return fetch(`/module/FORMBLD/api/version/${versionId}`)
      .then(res => res.json())
      .then(data => {
        selectedVersionId = data.version.id;
        currentVersionStatus = data.version.status;
        currentFields = data.fields || [];
        currentSections = data.sections || [];
        if (!pendingPrefill && fieldCodeToRestore && currentFields.some(field => field.field_code === fieldCodeToRestore)) {
          selectedFieldCode = fieldCodeToRestore;
        }
        availableValueSets = data.available_value_sets || [];
        availableFormulas = data.available_formulas || [];
        if (activeSectionCode && !currentSections.some(section => section.code === activeSectionCode)) {
          activeSectionCode = "";
        }
        isUnsaved = false;

        // Set status badge and name
        builderFormTitle.textContent = data.form.display_name || data.form.name;
        builderVersionBadge.textContent = `V${data.version.version_number} ${data.version.status}`;

        let badgeClass = "bg-amber-100 text-amber-800";
        if (data.version.status === "Published") badgeClass = "bg-emerald-100 text-emerald-800";
        else if (data.version.status === "Archived") badgeClass = "bg-slate-100 text-slate-800";
        builderVersionBadge.className = `px-2 py-0.5 rounded-full font-bold uppercase text-[9px] ${badgeClass}`;

        // Populate dropdown options inside inspectors
        populateInspectorDropdowns();
        renderSections();

        // Render Canvas Preview
        renderWorkspace();
        if (workspaceMode === "preview") {
          refreshBuilderPreview();
        }

        // Save status styling
        updateSaveStatusText();

        // Setup actions and editability depending on status
        updateVersionActions();

        // Resolve any pending prefill from return-URL navigation
        if (pendingPrefill) {
          const pending = pendingPrefill;
          pendingPrefill = null;
          const targetField = currentFields.find(f => f.field_code === pending.fieldCode);
          if (targetField) {
            selectedFieldCode = pending.fieldCode;
            if (pending.formulaVersionId) {
              targetField.field_config = targetField.field_config || {};
              targetField.field_config.formula_version_id = pending.formulaVersionId;
            }
            openInspector(pending.fieldCode);
            if (pending.formulaVersionId) {
              const msg = document.getElementById("prefill-formula-msg");
              if (msg) {
                const formulaEntry = availableFormulas.find(f => f.current_version_id === pending.formulaVersionId);
                const formulaName = formulaEntry ? formulaEntry.name : "Formula";
                msg.textContent = `${formulaName} linked. Save Draft to persist this change.`;
                msg.classList.remove("hidden");
              }
            }
          }
        } else if (selectedFieldCode && currentFields.some(field => field.field_code === selectedFieldCode)) {
          openInspector(selectedFieldCode);
        }

      })
      .catch(err => {
        console.error("Error loading version details:", err);
        showToast("Error loading version layout.", "error");
      });
  }

  function populateInspectorDropdowns() {
    const fSelect = document.getElementById("prop-formula");
    if (fSelect) {
      fSelect.innerHTML = '<option value="">Select Formula...</option>';
      availableFormulas.forEach(f => {
        const opt = document.createElement("option");
        opt.value = f.current_version_id;
        opt.textContent = `${f.name} (${f.code})`;
        fSelect.appendChild(opt);
      });
    }

    populateSectionDropdown();
  }

  function populateSectionDropdown() {
    if (!propSection) return;
    const selected = propSection.value;
    propSection.innerHTML = '<option value="">No section</option>';
    currentSections
      .slice()
      .sort((a, b) => (a.display_order || 0) - (b.display_order || 0))
      .forEach(section => {
        const opt = document.createElement("option");
        opt.value = section.code;
        opt.textContent = `${section.name} (${section.layout_type || "monthly_table"})`;
        propSection.appendChild(opt);
      });
    propSection.value = selected;
  }

  function renderSections() {
    if (!sectionsList) return;
    const sortedSections = orderedSections();
    const totalCount = currentFields.length;
    const allActiveClass = !activeSectionCode
      ? "border-indigo-200 bg-indigo-50 text-indigo-700"
      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50";

    const allRow = `
      <button type="button" class="section-select w-full rounded-lg border px-3 py-2 text-left text-xs font-bold transition ${allActiveClass}" data-section-code="">
        <div class="flex items-center justify-between gap-2">
          <span>All fields</span>
          <span class="rounded-full bg-white/70 px-2 py-0.5 text-[10px] text-slate-500">${totalCount}</span>
        </div>
      </button>
    `;

    if (sortedSections.length === 0) {
      sectionsList.innerHTML = `${allRow}<p class="px-1 pt-1 text-[10px] text-slate-400 italic">No sections configured yet.</p>`;
      populateSectionDropdown();
      if (!builderIsEditable) {
        sectionsList.querySelectorAll("input, select, textarea").forEach(el => { el.disabled = true; });
        sectionsList.querySelectorAll(".section-move-up, .section-move-down, .section-delete").forEach(btn => { btn.disabled = true; });
      }
      return;
    }

    sectionsList.innerHTML = allRow + sortedSections
      .map(section => {
        const idx = sortedSections.findIndex(item => item.code === section.code);
        const sectionFields = currentFields.filter(field => field.section_code === section.code).length;
        const activeClass = activeSectionCode === section.code
          ? "border-indigo-200 bg-indigo-50/70"
          : "border-slate-200 bg-white";
        return `
        <div class="section-row rounded-lg border ${activeClass} p-2.5 space-y-1.5" data-section-code="${escapeHtml(section.code)}">
          <div class="flex items-center gap-1.5">
            <button type="button" class="section-select flex-1 min-w-0 text-left" data-section-code="${escapeHtml(section.code)}">
              <span class="truncate text-xs font-bold text-slate-800 block">${escapeHtml(section.name || section.code)}</span>
            </button>
            <span class="flex-shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">${sectionFields}</span>
            <button type="button" class="section-move-up flex-shrink-0 rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40" data-section-code="${escapeHtml(section.code)}" ${idx === 0 ? "disabled" : ""} aria-label="Move section up">▲</button>
            <button type="button" class="section-move-down flex-shrink-0 rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40" data-section-code="${escapeHtml(section.code)}" ${idx === sortedSections.length - 1 ? "disabled" : ""} aria-label="Move section down">▼</button>
          </div>
          <div class="flex items-center gap-1.5">
            <input type="text" class="section-name flex-1 min-w-0 block rounded border-slate-300 text-xs px-2 py-1 border font-semibold" value="${escapeHtml(section.name || "")}" placeholder="Section name">
            <button type="button" class="section-delete flex-shrink-0 text-[10px] font-semibold text-rose-500 border border-rose-200 rounded px-1.5 py-0.5 hover:bg-rose-50">✕</button>
          </div>
          <div class="flex items-center justify-between gap-2">
            <span class="text-[10px] text-slate-400">${escapeHtml(layoutDisplayName(section.layout_type))}</span>
            <button type="button" class="section-details-toggle text-[10px] text-indigo-500 hover:text-indigo-700 font-semibold">Edit details</button>
          </div>
          <div class="section-details-area hidden space-y-1.5 pt-1.5 border-t border-slate-100">
            <input type="text" class="section-code hidden" value="${escapeHtml(section.code || "")}" placeholder="section_code">
            <div>
              <label class="block text-[9px] font-bold uppercase tracking-wider text-slate-400 mb-0.5">Layout type</label>
              <select class="section-layout block w-full rounded border-slate-300 text-[11px] px-2 py-1 border bg-white">
                <option value="monthly_table" ${section.layout_type === "monthly_table" ? "selected" : ""}>Monthly table</option>
                <option value="annual_table" ${section.layout_type === "annual_table" ? "selected" : ""}>Annual table</option>
                <option value="reference_table" ${section.layout_type === "reference_table" ? "selected" : ""}>Reference table</option>
              </select>
            </div>
            <div>
              <label class="block text-[9px] font-bold uppercase tracking-wider text-slate-400 mb-0.5">Description (optional)</label>
              <textarea class="section-description block w-full rounded border-slate-300 text-[11px] px-2 py-1 border" rows="2" placeholder="Optional section description">${escapeHtml(section.description || "")}</textarea>
            </div>
          </div>
        </div>
      `;
      })
      .join("");
    populateSectionDropdown();
    if (!builderIsEditable) {
      sectionsList.querySelectorAll("input, select, textarea").forEach(el => { el.disabled = true; });
      sectionsList.querySelectorAll(".section-move-up, .section-move-down, .section-delete").forEach(btn => { btn.disabled = true; });
    }
  }

  function syncSectionsFromDom() {
    if (!sectionsList) return;
    const previousCodeMap = new Map(currentSections.map(section => [section.code, section]));
    const nextSections = [];
    sectionsList.querySelectorAll(".section-row").forEach((row, idx) => {
      const originalCode = row.dataset.sectionCode;
      const codeInput = row.querySelector(".section-code");
      const code = normalizeCode(codeInput.value || originalCode || `section_${idx + 1}`);
      const previous = previousCodeMap.get(originalCode) || {};
      nextSections.push({
        id: previous.id || null,
        name: row.querySelector(".section-name").value.trim() || `Section ${idx + 1}`,
        code: code,
        layout_type: row.querySelector(".section-layout").value || "monthly_table",
        display_order: idx + 1,
        description: row.querySelector(".section-description").value.trim()
      });
      codeInput.value = code;
      row.dataset.sectionCode = code;
      currentFields.forEach(field => {
        if (field.section_code === originalCode) {
          field.section_code = code;
          field.section_id = previous.id || null;
        }
      });
      if (activeSectionCode === originalCode) {
        activeSectionCode = code;
      }
    });
    currentSections = nextSections;
    normalizeSectionDisplayOrder();
    normalizeFieldDisplayOrder();
    if (activeSectionCode && !currentSections.some(section => section.code === activeSectionCode)) {
      activeSectionCode = "";
    }
    populateSectionDropdown();
  }

  function updateSaveStatusText() {
    if (isUnsaved) {
      saveStatusText.textContent = "Unsaved changes *";
      saveStatusText.className = "text-xs text-amber-600 font-bold animate-pulse";
      btnSaveLayout.disabled = false;
      btnSaveLayout.className = "btn btn-primary btn-sm";
    } else {
      saveStatusText.textContent = "All changes saved";
      saveStatusText.className = "text-xs text-slate-400 font-medium";
      btnSaveLayout.disabled = true;
      btnSaveLayout.className = "btn btn-neutral btn-sm cursor-not-allowed";
    }
  }

  function renderWorkspace() {
    const section = activeSection();
    const fields = fieldsForActiveSection();
    const countLabel = `${fields.length} field${fields.length === 1 ? "" : "s"}`;
    if (workspaceSectionTitle) {
      workspaceSectionTitle.textContent = section ? section.name : "All sheet fields";
    }
    if (workspaceSectionMeta) {
      workspaceSectionMeta.textContent = section
        ? `${humanizeType(section.layout_type || "monthly_table")} · ${countLabel}`
        : `${countLabel} across all sections`;
    }

    if (fields.length === 0) {
      formWorkspace.innerHTML = `
        <div class="flex min-h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-6 py-12 text-center">
          <div class="text-sm font-bold text-slate-700">No fields in this ${section ? "section" : "sheet"} yet</div>
          <p class="mt-2 max-w-sm text-xs text-slate-400">Use the field palette on the left to add the next data entry row.</p>
        </div>
      `;
      return;
    }

    formWorkspace.innerHTML = `
      <div class="space-y-2">
        ${fields.map((field) => {
          const config = field.field_config || {};
          const selectedClass = field.field_code === selectedFieldCode
            ? "border-indigo-300 bg-indigo-50/50 ring-1 ring-indigo-200"
            : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50";
          const sectionFields = fieldsForSection(field.section_code || "");
          const sectionIdx = sectionFields.findIndex(item => item.field_code === field.field_code);
          const indicators = [];
          if (config.is_required) indicators.push("Required");
          if (field.field_type === "calculated") indicators.push("Calculated");
          if (isSheetResultField(field)) indicators.push("Sheet/FY result");
          if (config.proof_required) indicators.push("Proof");
          if (field.field_type === "dropdown") {
            const optionCount = dropdownOptionCount(field);
            indicators.push(optionCount ? `Options: ${optionCount}` : "Needs options");
          }
          return `
            <div class="field-row flex w-full min-h-[52px] items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left transition ${selectedClass}" data-field-code="${escapeHtml(field.field_code)}">
              <button type="button" class="field-select min-w-0 flex-1 text-left" data-field-code="${escapeHtml(field.field_code)}">
                <div class="truncate text-sm font-semibold text-slate-900">${escapeHtml(field.field_name || field.field_code)}</div>
                <div class="mt-0.5 flex flex-wrap items-center gap-1.5">
                  <span class="font-mono text-[11px] text-[#94a3b8]">${escapeHtml(field.field_code)}</span>
                  ${indicators.map(item => `<span class="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">${escapeHtml(item)}</span>`).join("")}
                </div>
              </button>
              <div class="flex flex-shrink-0 items-center gap-1.5">
                <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-600">${escapeHtml(humanizeType(field.field_type))}</span>
                <span class="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-700">${escapeHtml(field.frequency || "monthly")}</span>
                <div class="flex items-center gap-0.5">
                  <button type="button" class="field-move-up rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-400 hover:bg-slate-50 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-30" data-field-code="${escapeHtml(field.field_code)}" ${sectionIdx <= 0 ? "disabled" : ""} aria-label="Move field up">▲</button>
                  <button type="button" class="field-move-down rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-400 hover:bg-slate-50 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-30" data-field-code="${escapeHtml(field.field_code)}" ${sectionIdx === sectionFields.length - 1 ? "disabled" : ""} aria-label="Move field down">▼</button>
                </div>
                <button type="button" class="field-select text-[10px] font-bold text-indigo-600 hover:text-indigo-800" data-field-code="${escapeHtml(field.field_code)}">Edit</button>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;

    formWorkspace.querySelectorAll(".field-select").forEach(button => {
      button.onclick = function () {
        selectedFieldCode = button.dataset.fieldCode;
        const row = button.closest(".field-row");
        if (row) highlightRow(row);
        openInspector(selectedFieldCode);
      };
    });
    formWorkspace.querySelectorAll(".field-move-up").forEach(button => {
      button.onclick = function () {
        moveFieldWithinActiveSection(button.dataset.fieldCode, -1);
      };
    });
    formWorkspace.querySelectorAll(".field-move-down").forEach(button => {
      button.onclick = function () {
        moveFieldWithinActiveSection(button.dataset.fieldCode, 1);
      };
    });
  }

  function highlightRow(rowElement) {
    const rows = formWorkspace.querySelectorAll(".field-row[data-field-code]");
    rows.forEach(r => {
      r.classList.remove("border-indigo-300", "bg-indigo-50/50", "ring-1", "ring-indigo-200");
      r.classList.add("border-slate-200", "bg-white");
      r.style.borderStyle = "";
    });

    rowElement.classList.remove("border-slate-200", "bg-white");
    rowElement.classList.add("border-indigo-300", "bg-indigo-50/50", "ring-1", "ring-indigo-200");
    rowElement.style.borderStyle = "solid";
  }

  function openInspector(fieldCode) {
    const field = currentFields.find(x => x.field_code === fieldCode);
    if (!field) return;

    inspectorEmpty.classList.add("hidden");
    inspectorPanel.classList.remove("hidden");
    if (inspectorSummary) {
      const config = field.field_config || {};
      const section = currentSections.find(item => item.code === field.section_code);
      const indicators = [];
      if (config.is_required) indicators.push("Required");
      if (field.field_type === "calculated") indicators.push("Read-only calculated");
      if (isSheetResultField(field)) indicators.push("Sheet/FY result");
      if (config.proof_required) indicators.push("Proof required");
      if (config.remarks_required) indicators.push("Remarks required");
      if (field.field_type === "dropdown") {
        const optionCount = dropdownOptionCount(field);
        indicators.push(optionCount ? `Options: ${optionCount}` : "Needs options");
      }
      inspectorSummary.innerHTML = `
        <div class="space-y-3">
          <div>
            <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Selected field</div>
            <div class="mt-1 text-sm font-bold text-slate-900">${escapeHtml(field.field_name || field.field_code)}</div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="rounded-lg bg-slate-50 p-2">
              <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Type</div>
              <div class="mt-0.5 font-bold text-slate-700">${escapeHtml(humanizeType(field.field_type))}</div>
            </div>
            <div class="rounded-lg bg-slate-50 p-2">
              <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Frequency</div>
              <div class="mt-0.5 font-bold text-slate-700">${escapeHtml(field.frequency || "monthly")}</div>
            </div>
          </div>
          <div class="text-[11px] font-semibold text-slate-500">
            ${escapeHtml(section ? section.name : "No section")}
          </div>
          ${indicators.length ? `<div class="flex flex-wrap gap-1.5">${indicators.map(item => `<span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">${escapeHtml(item)}</span>`).join("")}</div>` : ""}
        </div>
      `;
    }

    // Common fields
    document.getElementById("prop-code").value = field.field_code;
    const propCodeDisplay = document.getElementById("prop-code-display");
    if (propCodeDisplay) propCodeDisplay.textContent = field.field_code;
    document.getElementById("prop-name").value = field.field_name;
    const typeDisplay = document.getElementById("prop-type-display");
    if (typeDisplay) {
      typeDisplay.textContent = humanizeType(field.field_type);
    }
    propSection.value = field.section_code || "";
    propFrequency.value = field.frequency || "monthly";
    const sectionFields = fieldsForSection(field.section_code || "");
    const sectionIndex = sectionFields.findIndex(item => item.field_code === field.field_code);
    if (btnMoveUp) btnMoveUp.disabled = sectionIndex <= 0;
    if (btnMoveDown) btnMoveDown.disabled = sectionIndex === -1 || sectionIndex >= sectionFields.length - 1;
    document.getElementById("prop-required").checked = field.field_config.is_required || false;
    document.getElementById("prop-remarks-req").checked = field.field_config.remarks_required || false;
    document.getElementById("prop-proof-req").checked = field.field_config.proof_required || false;
    setResultFieldWorkflowControls(field.field_type === "calculated" && isSheetResultField(field));
    document.getElementById("prop-help").value = field.field_config.help_text || "";

    // Toggle specific type options
    document.getElementById("prop-section-numeric").classList.add("hidden");
    document.getElementById("prop-section-dropdown").classList.add("hidden");
    document.getElementById("prop-section-calculated").classList.add("hidden");
    document.getElementById("prop-section-file").classList.add("hidden");
    const _fHint = document.getElementById("formula-publish-hint");
    const _fOk   = document.getElementById("formula-status-ok");
    if (_fHint) _fHint.classList.add("hidden");
    if (_fOk)   _fOk.classList.add("hidden");

    const config = field.field_config || {};

    if (field.field_type === "number" || field.field_type === "integer") {
      document.getElementById("prop-section-numeric").classList.remove("hidden");
      document.getElementById("prop-unit").value = config.unit || "";
      document.getElementById("prop-min").value = config.min !== undefined ? config.min : "";
      document.getElementById("prop-max").value = config.max !== undefined ? config.max : "";
      document.getElementById("prop-anomaly").value = config.anomaly_threshold !== undefined ? config.anomaly_threshold : "";
    }

    if (field.field_type === "dropdown") {
      document.getElementById("prop-section-dropdown").classList.remove("hidden");
      renderDropdownOptionsEditor(field);
    }

    if (field.field_type === "calculated") {
      document.getElementById("prop-section-calculated").classList.remove("hidden");
      const formulaSelect = document.getElementById("prop-formula");
      const formulaHint   = document.getElementById("formula-publish-hint");
      const formulaOk     = document.getElementById("formula-status-ok");
      const calcUnitWrap  = document.getElementById("prop-calc-unit-wrap");
      const calcUnitInput = document.getElementById("prop-calc-unit");
      if (propCalcPlacement) {
        if (!isSheetResultField(field)) {
          propCalcPlacement.value = "monthly";
        } else if ((field.field_config || {}).display_region === "below_monthly_table") {
          propCalcPlacement.value = "annual_result_below";
        } else {
          propCalcPlacement.value = "annual_result";
        }
      }
      if (formulaSelect && config.formula_version_id) {
        formulaSelect.value = config.formula_version_id;
        if (formulaHint) formulaHint.classList.add("hidden");
        if (formulaOk)   formulaOk.classList.remove("hidden");
        if (calcUnitWrap)  calcUnitWrap.classList.remove("hidden");
        if (calcUnitInput) calcUnitInput.value = config.unit || "";
      } else {
        if (formulaHint)   formulaHint.classList.remove("hidden");
        if (formulaOk)     formulaOk.classList.add("hidden");
        if (calcUnitWrap)  calcUnitWrap.classList.add("hidden");
        if (calcUnitInput) calcUnitInput.value = "";
      }
    }

    if (field.field_type === "file") {
      document.getElementById("prop-section-file").classList.remove("hidden");
      const mimeCheckboxes = document.getElementsByName("mime-types");
      const acceptedList = config.accepted_mime_types || [];
      mimeCheckboxes.forEach(cb => {
        cb.checked = acceptedList.includes(cb.value);
      });
    }
  }

  function closeInspector() {
    selectedFieldCode = null;
    inspectorPanel.classList.add("hidden");
    inspectorEmpty.classList.remove("hidden");
    if (inspectorSummary) {
      inspectorSummary.innerHTML = "";
    }
  }

  function applySelectedFieldChanges(options = {}) {
    const render = options.render !== false;
    const notify = options.notify === true;
    if (!selectedFieldCode) return true;

    const fieldIdx = currentFields.findIndex(x => x.field_code === selectedFieldCode);
    if (fieldIdx === -1) return true;

    const field = currentFields[fieldIdx];
    field.field_config = field.field_config || {};
    const previousSectionCode = field.section_code || "";
    const newCode = document.getElementById("prop-code").value.trim().toLowerCase().replace(/\s+/g, "_");

    // Validate code duplicate
    const dup = currentFields.find((x, idx) => x.field_code === newCode && idx !== fieldIdx);
    if (dup) {
      showToast(`Field code '${newCode}' is already used.`, "error");
      return false;
    }

    field.field_code = newCode;
    field.field_name = document.getElementById("prop-name").value.trim();
    field.section_code = propSection.value || "";
    const section = currentSections.find(item => item.code === field.section_code);
    field.section_id = section && section.id ? section.id : null;
    if ((field.section_code || "") !== previousSectionCode) {
      const targetSectionFields = fieldsForSection(field.section_code).filter(item => item.field_code !== field.field_code);
      field.display_order = targetSectionFields.length
        ? Math.max(...targetSectionFields.map(item => item.display_order || 0)) + 1
        : currentFields.length + 1;
      activeSectionCode = field.section_code || "";
    }
    field.frequency = propFrequency.value || "monthly";
    field.field_config.is_required = document.getElementById("prop-required").checked;
    field.field_config.remarks_required = document.getElementById("prop-remarks-req").checked;
    field.field_config.proof_required = document.getElementById("prop-proof-req").checked;
    field.field_config.help_text = document.getElementById("prop-help").value.trim();

    if (field.field_type === "number" || field.field_type === "integer") {
      field.field_config.unit = document.getElementById("prop-unit").value.trim();

      const minVal = document.getElementById("prop-min").value;
      field.field_config.min = minVal !== "" ? parseFloat(minVal) : undefined;

      const maxVal = document.getElementById("prop-max").value;
      field.field_config.max = maxVal !== "" ? parseFloat(maxVal) : undefined;

      const anomalyVal = document.getElementById("prop-anomaly").value;
      field.field_config.anomaly_threshold = anomalyVal !== "" ? parseFloat(anomalyVal) : undefined;
    }

    if (field.field_type === "dropdown") {
      field.field_config.options = collectDropdownOptions();
    }

    if (field.field_type === "calculated") {
      const formulaSelect = document.getElementById("prop-formula");
      const calcUnitWrap  = document.getElementById("prop-calc-unit-wrap");
      const calcUnitInput = document.getElementById("prop-calc-unit");
      const placement = propCalcPlacement ? propCalcPlacement.value : "monthly";
      const isAnnualResult = placement === "annual_result" || placement === "annual_result_below";

      if (isAnnualResult) {
        field.frequency = "annual";
        if (propFrequency) propFrequency.value = "annual";
        field.field_config.field_scope = "annual_result";
        field.field_config.result_role = "aggregate_result";
        field.field_config.display_region = placement === "annual_result_below"
          ? "below_monthly_table"
          : "under_input_column";
        field.field_config.blank_policy = field.field_config.blank_policy || "strict";
        field.field_config.is_required = false;
        field.field_config.remarks_required = false;
        field.field_config.proof_required = false;
        document.getElementById("prop-required").checked = false;
        document.getElementById("prop-remarks-req").checked = false;
        document.getElementById("prop-proof-req").checked = false;
        setResultFieldWorkflowControls(true);
      } else {
        field.frequency = "monthly";
        if (propFrequency) propFrequency.value = "monthly";
        field.field_config.field_scope = "monthly";
        field.field_config.result_role = "monthly_calculated";
        field.field_config.display_region = "monthly_table";
        delete field.field_config.blank_policy;
        setResultFieldWorkflowControls(false);
      }

      if (formulaSelect) {
        const formulaVal = formulaSelect.value;
        const prevFormulaId = field.field_config.formula_version_id;
        field.field_config.formula_version_id = formulaVal ? parseInt(formulaVal) : undefined;
        field.field_config.unit = calcUnitInput ? calcUnitInput.value.trim() : "";

        if (formulaVal) {
          const formulaChanged = parseInt(formulaVal) !== prevFormulaId;
          if (formulaChanged) {
            field.field_config.unit = "";
            if (calcUnitInput) calcUnitInput.value = "";
            if (calcUnitWrap) calcUnitWrap.classList.remove("hidden");
            fetch(`/module/FRMULA/api/version/${formulaVal}`)
              .then(res => res.json())
              .then(resData => {
                field.field_config.expression = resData.version.expression;
                field.field_config.tokens = resData.version.tokens;
                renderWorkspace();
              });
          }
        } else {
          field.field_config.expression = "";
          field.field_config.tokens = [];
          if (calcUnitInput) calcUnitInput.value = "";
          if (calcUnitWrap) calcUnitWrap.classList.add("hidden");
        }
      }
    }

    if (field.field_type === "file") {
      const checkedMimes = [];
      document.getElementsByName("mime-types").forEach(cb => {
        if (cb.checked) checkedMimes.push(cb.value);
      });
      field.field_config.accepted_mime_types = checkedMimes;
    }

    selectedFieldCode = newCode;
    isUnsaved = true;
    normalizeFieldDisplayOrder();
    updateSaveStatusText();
    if (render) {
      renderSections();
      renderWorkspace();
      openInspector(newCode);
    }
    if (notify) {
      showToast("Field updated in workspace.");
    }
    return true;
  }

  // Apply Changes from properties form
  formFieldProperties.onsubmit = function (e) {
    e.preventDefault();
    if (applySelectedFieldChanges({ notify: true })) {
      saveDraftLayout().catch(() => {});
    }
  };

  formFieldProperties.addEventListener("input", function () {
    applySelectedFieldChanges({ render: false });
  });
  formFieldProperties.addEventListener("change", function () {
    applySelectedFieldChanges({ render: true });
  });

  // Palette item clicks
  document.querySelectorAll(".palette-btn").forEach(btn => {
    btn.onclick = function () {
      const type = btn.dataset.type;
      const displayOrder = currentFields.length + 1;
      const code = `field_${Date.now()}`;
      const name = `New ${type.charAt(0).toUpperCase() + type.slice(1)}`;
      const section = activeSection();

      const newField = {
        field_code: code,
        field_name: name,
        field_type: type,
        display_order: displayOrder,
        section_id: section && section.id ? section.id : null,
        section_code: section ? section.code : "",
        frequency: "monthly",
        field_config: {
          is_required: false,
          help_text: ""
        }
      };
      if (type === "calculated") {
        newField.field_config.field_scope = "monthly";
        newField.field_config.result_role = "monthly_calculated";
        newField.field_config.display_region = "monthly_table";
      }

      currentFields.push(newField);
      isUnsaved = true;
      selectedFieldCode = code;
      normalizeFieldDisplayOrder();

      updateSaveStatusText();
      renderSections();
      renderWorkspace();
      openInspector(code);
      saveDraftLayout().catch(() => {});
    };
  });

  // Delete field
  btnDeleteField.onclick = function () {
    if (!selectedFieldCode) return;
    if (!confirm("Are you sure you want to delete this field from the sheet layout?")) return;

    currentFields = currentFields.filter(x => x.field_code !== selectedFieldCode);

    // Normalize display order numbers
    normalizeFieldDisplayOrder();

    isUnsaved = true;
    closeInspector();
    updateSaveStatusText();
    renderSections();
    renderWorkspace();
    showToast("Field deleted.");
    saveDraftLayout().catch(() => {});
  };

  if (btnAddSection) {
    btnAddSection.onclick = function () {
      const displayOrder = currentSections.length + 1;
      const code = `section_${displayOrder}`;
      currentSections.push({
        id: null,
        name: `Section ${displayOrder}`,
        code: code,
        layout_type: "monthly_table",
        display_order: displayOrder,
        description: ""
      });
      activeSectionCode = code;
      isUnsaved = true;
      normalizeSectionDisplayOrder();
      normalizeFieldDisplayOrder();
      updateSaveStatusText();
      renderSections();
      renderWorkspace();
      saveDraftLayout().catch(() => {});
    };
  }

  if (sectionsList) {
    sectionsList.addEventListener("input", function (e) {
      if (!e.target.closest(".section-row")) return;
      syncSectionsFromDom();
      isUnsaved = true;
      updateSaveStatusText();
      renderWorkspace();
    });
    sectionsList.addEventListener("change", function (e) {
      if (!e.target.closest(".section-row")) return;
      syncSectionsFromDom();
      isUnsaved = true;
      updateSaveStatusText();
      renderSections();
      renderWorkspace();
      saveDraftLayout().catch(() => {});
    });
    sectionsList.addEventListener("click", function (e) {
      const moveUpButton = e.target.closest(".section-move-up");
      if (moveUpButton) {
        moveSection(moveUpButton.dataset.sectionCode, -1);
        return;
      }
      const moveDownButton = e.target.closest(".section-move-down");
      if (moveDownButton) {
        moveSection(moveDownButton.dataset.sectionCode, 1);
        return;
      }

      const selectButton = e.target.closest(".section-select");
      if (selectButton) {
        activeSectionCode = selectButton.dataset.sectionCode || "";
        renderSections();
        renderWorkspace();
        return;
      }

      const detailsToggle = e.target.closest(".section-details-toggle");
      if (detailsToggle) {
        const row = detailsToggle.closest(".section-row");
        const area = row && row.querySelector(".section-details-area");
        if (area) {
          const wasHidden = area.classList.contains("hidden");
          area.classList.toggle("hidden", !wasHidden);
          detailsToggle.textContent = wasHidden ? "Hide details" : "Edit details";
        }
        return;
      }

      const button = e.target.closest(".section-delete");
      if (!button) return;
      const row = button.closest(".section-row");
      const code = row.dataset.sectionCode;
      currentSections = currentSections.filter(section => section.code !== code);
      currentFields.forEach(field => {
        if (field.section_code === code) {
          field.section_code = "";
          field.section_id = null;
        }
      });
      if (activeSectionCode === code) {
        activeSectionCode = "";
      }
      isUnsaved = true;
      normalizeSectionDisplayOrder();
      normalizeFieldDisplayOrder();
      updateSaveStatusText();
      renderSections();
      renderWorkspace();
      if (selectedFieldCode) {
        openInspector(selectedFieldCode);
      }
      saveDraftLayout().catch(() => {});
    });
  }

  if (btnAddDropdownOption && dropdownOptionsList) {
    btnAddDropdownOption.onclick = function () {
      dropdownOptionsList.insertAdjacentHTML("beforeend", dropdownOptionRow(""));
      const inputs = dropdownOptionsList.querySelectorAll(".dropdown-option-input");
      const lastInput = inputs[inputs.length - 1];
      if (lastInput) lastInput.focus();
    };

    dropdownOptionsList.addEventListener("click", function (e) {
      const removeButton = e.target.closest(".dropdown-option-remove");
      if (!removeButton) return;
      const row = removeButton.closest(".dropdown-option-row");
      if (row) row.remove();
      if (!dropdownOptionsList.querySelector(".dropdown-option-row")) {
        dropdownOptionsList.insertAdjacentHTML("beforeend", dropdownOptionRow(""));
      }
    });
  }

  // Move Field Up
  btnMoveUp.onclick = function () {
    if (!selectedFieldCode) return;
    moveFieldWithinActiveSection(selectedFieldCode, -1);
  };

  // Move Field Down
  btnMoveDown.onclick = function () {
    if (!selectedFieldCode) return;
    moveFieldWithinActiveSection(selectedFieldCode, 1);
  };

  // "+ Add field" link in centre footer — deselects field and shows palette
  const btnAddFieldLink = document.getElementById("btn-add-field-link");
  if (btnAddFieldLink) {
    btnAddFieldLink.onclick = function () {
      showWorkspaceFields();
      closeInspector();
      renderWorkspace();
    };
  }

  if (workspaceTabFields) {
    workspaceTabFields.onclick = function () {
      showWorkspaceFields();
    };
  }

  if (workspaceTabPreview) {
    workspaceTabPreview.onclick = function () {
      if (isUnsaved) {
        showToast("Preview shows the last saved draft. Save changes to refresh it.", "error");
      }
      showWorkspacePreview();
    };
  }

  function ensureEditableDraftIfNeeded() {
    if (currentVersionStatus === "Draft") {
      return Promise.resolve();
    }
    if (!selectedFormId) {
      return Promise.reject(new Error("No sheet selected."));
    }
    return ensureDraftVersion(selectedFormId, true);
  }

  function updateVersionActions() {
    const isDraft = currentVersionStatus === "Draft";
    if (isDraft) {
      if (btnEditAsDraft) btnEditAsDraft.classList.add("hidden");
      btnSaveLayout.classList.remove("hidden");
      btnPublishForm.classList.remove("hidden");
    } else {
      if (btnEditAsDraft) btnEditAsDraft.classList.remove("hidden");
      btnSaveLayout.classList.add("hidden");
      btnPublishForm.classList.add("hidden");
    }
    setBuilderEditable(isDraft);
  }

  function setBuilderEditable(isEditable) {
    builderIsEditable = isEditable;
    Array.from(formFieldProperties.elements).forEach(el => { el.disabled = !isEditable; });
    document.querySelectorAll(".palette-btn").forEach(btn => { btn.disabled = !isEditable; });
    if (btnDeleteField) btnDeleteField.disabled = !isEditable;
    if (btnMoveUp) btnMoveUp.disabled = !isEditable;
    if (btnMoveDown) btnMoveDown.disabled = !isEditable;
    if (btnAddSection) btnAddSection.disabled = !isEditable;
    if (sectionsList) {
      sectionsList.querySelectorAll("input, select, textarea").forEach(el => { el.disabled = !isEditable; });
      sectionsList.querySelectorAll(".section-move-up, .section-move-down, .section-delete").forEach(btn => { btn.disabled = !isEditable; });
    }
  }

  if (btnEditAsDraft) {
    btnEditAsDraft.onclick = function () {
      ensureEditableDraftIfNeeded().catch(() => {});
    };
  }

  function saveDraftLayout() {
    if (!selectedVersionId) return;
    if (!applySelectedFieldChanges({ render: false })) {
      return Promise.reject(new Error("Resolve the field inspector errors before saving."));
    }
    syncSectionsFromDom();
    normalizeSectionDisplayOrder();
    normalizeFieldDisplayOrder();

    return ensureEditableDraftIfNeeded().then(() => fetch(`/module/FORMBLD/api/version/${selectedVersionId}/fields`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields: currentFields, sections: currentSections })
    }))
      .then(res => res.json())
      .then(resData => {
        if (resData.error) {
          showToast(resData.error, "error");
          throw new Error(resData.error);
        } else {
          showToast("Sheet draft saved successfully.");
          isUnsaved = false;
          return loadVersionDetails(selectedVersionId);
        }
      })
      .catch(err => {
        console.error("Error saving form fields:", err);
        showToast("Failed to save draft.", "error");
        throw err;
      });
  }

  // Save Layout Draft
  btnSaveLayout.onclick = function () {
    saveDraftLayout().catch(() => {});
  };

  // Publish validation & submit
  btnPublishForm.onclick = function () {
    if (!selectedVersionId) return;
    if (!applySelectedFieldChanges({ render: false })) {
      return;
    }

    const noun = isWorkbookContext ? "sheet" : "form";

    // 1. Client-side validations — actionable language
    const errors = [];
    const formObj = formsList.find(x => x.id === selectedFormId);

    if (currentFields.length === 0) {
      errors.push("Add at least one field before publishing.");
    }

    currentFields.forEach(f => {
      if (f.field_type === "calculated" && (!f.field_config || !f.field_config.formula_version_id)) {
        errors.push(`"${escapeHtml(f.field_name)}" is a calculated field — open its inspector and attach a published formula before publishing this ${noun}.`);
      }
      if (f.field_type === "dropdown" && dropdownOptionCount(f) === 0) {
        errors.push(`"${escapeHtml(f.field_name)}" is a dropdown with no options — add at least one option before publishing.`);
      }
    });

    if (!formObj || !formObj.sites || formObj.sites.length === 0) {
      errors.push(`Assign this ${noun} to at least one site before publishing.`);
    }

    if (errors.length > 0) {
      publishErrorsList.innerHTML = errors.map(e => `<li>${e}</li>`).join("");
      publishErrors.classList.remove("hidden");
      showToast(`Resolve all issues before publishing this ${noun}.`, "error");
      return;
    }

    publishErrors.classList.add("hidden");

    if (!confirm(`Publish this ${noun}? It will become active immediately and cannot be edited without creating a new draft.`)) {
      return;
    }

    saveDraftLayout().then(() => fetch(`/module/FORMBLD/api/version/${selectedVersionId}/publish`, {
      method: "POST"
    }))
      .then(res => res.json())
      .then(resData => {
        if (resData.error) {
          const friendly = resData.error === "Only Draft versions can be published."
            ? "This published sheet needs a draft version before changes can be published. A draft has been created for your edits."
            : resData.error;
          // Server-side error → show in error panel, not just toast
          publishErrorsList.innerHTML = `<li>${escapeHtml(friendly)}</li>`;
          publishErrors.classList.remove("hidden");
          showToast(`Publish blocked — see errors above.`, "error");
        } else {
          showToast(isWorkbookContext ? "Sheet published." : "Form version published.");
          isUnsaved = false;
          // Reload version so status badge refreshes to Published; stay in builder
          loadVersionDetails(selectedVersionId);
        }
      })
      .catch(err => {
        console.error("Error publishing:", err);
        showToast(`Failed to publish ${noun}. Please try again.`, "error");
      });
  };

  function ensureDraftVersion(formId, showReadyToast = true) {
    return fetch(`/module/FORMBLD/api/${formId}/new-version`, {
      method: "POST"
    })
      .then(res => res.json())
      .then(resData => {
        if (resData.error) {
          showToast(resData.error, "error");
          throw new Error(resData.error);
        } else {
          if (showReadyToast) {
            showToast("Draft version ready for editing.");
          }
          return fetch("/module/FORMBLD/api")
            .then(res => res.json())
            .then(data => {
              formsList = data;
              return editFormLayout(formId, resData.data.version_id)
                .then(() => resData.data);
            });
        }
      })
      .catch(err => {
        console.error("Error creating new draft version:", err);
        showToast("Failed to create draft version.", "error");
        throw err;
      });
  }

  // Create new version draft for published form
  window.createNewDraft = function (formId) {
    if (!confirm("Edit this published sheet? A draft will be prepared so the published version stays unchanged.")) return;
    ensureDraftVersion(formId);
  };

  // --- SPOC Preview Overlay Modal ---
  window.openPreview = function (formId, versionId) {
    // If we're previewing from Step 2 with unsaved changes, we alert first
    if (isUnsaved && !step2View.classList.contains("hidden")) {
      if (!confirm("You have unsaved changes in Step 2. Preview will show the last saved draft. Continue?")) {
        return;
      }
    }

    const form = formsList.find(x => x.id === formId);
    if (!form) return;

    pvTitle.textContent = form.display_name || form.name;

    let sitesText = "All Sites";
    if (form.sites && form.sites.length > 0) {
      sitesText = form.sites.map(sid => sitesMap[sid] || sid).join(", ");
    }
    pvMeta.textContent = `${sitesText} · Frequency: ${form.frequency || "Monthly"} · Loading preview...`;
    const target = modalPreviewTarget();
    resetPreviewTarget(target);
    previewOverlay.classList.remove("hidden");

    loadPreviewContext(formId, versionId)
      .then(data => {
        pvMeta.textContent = `${sitesText} · ${data.financial_year && data.financial_year.label ? data.financial_year.label : "Preview"} · Version: v${data.version ? data.version.version_number : (form.latest_version_num || 1)}`;
        renderPreviewWorkbookContext(data, target);
        previewOverlay.classList.remove("hidden");
      })
      .catch(err => {
        console.error("Error loading preview fields:", err);
        if (target.empty) {
          target.empty.classList.remove("hidden");
          target.empty.textContent = err.message || "Error loading preview.";
        }
        showToast("Error loading workbook preview.", "error");
      });
  };

  // Wrapper for calling preview from builder context (uses active state variables)
  window.openPreviewFromBuilder = function () {
    if (selectedFormId && selectedVersionId) {
      openPreview(selectedFormId, selectedVersionId);
    } else {
      showToast("No sheet is currently loaded for preview.", "error");
    }
  };

  window.closePreview = function () {
    previewOverlay.classList.add("hidden");
  };

  previewOverlay.onclick = function (e) {
    if (e.target === previewOverlay) {
      closePreview();
    }
  };

  // Open Formula Builder nav button
  const btnOpenFormulaBuilder = document.getElementById("btn-open-formula-builder");
  if (btnOpenFormulaBuilder) {
    btnOpenFormulaBuilder.onclick = function (e) {
      e.preventDefault();
      if (!selectedFormId || !selectedVersionId) return;
      const field = currentFields.find(x => x.field_code === selectedFieldCode);
      const formulaVerId = field && field.field_config ? field.field_config.formula_version_id : null;
      let url = "/module/FRMULA/?return_to=" + encodeURIComponent("/module/FORMBLD/") +
        "&form_id=" + selectedFormId +
        "&version_id=" + selectedVersionId +
        "&field_id=" + encodeURIComponent(selectedFieldCode || "");
      if (formulaVerId) {
        url += "&open_version_id=" + formulaVerId;
      }
      window.location.href = url;
    };
  }

  // Open Value Sets nav button
  const btnOpenValueSets = document.getElementById("btn-open-value-sets");
  if (btnOpenValueSets) {
    btnOpenValueSets.onclick = function (e) {
      e.preventDefault();
      if (!selectedFormId || !selectedVersionId) return;
      const url = "/module/VALSET/?return_to=" + encodeURIComponent("/module/FORMBLD/") +
        "&form_id=" + selectedFormId +
        "&version_id=" + selectedVersionId +
        "&field_id=" + encodeURIComponent(selectedFieldCode || "");
      window.location.href = url;
    };
  }

  // Check URL params for return-from-formula-builder or return-from-value-sets flow
  function checkUrlPrefill() {
    const params = new URLSearchParams(window.location.search);
    const prefillFormulaVersionId = params.get("prefill_formula");
    const fieldCode = params.get("field_id");
    const formId = params.get("form_id");
    const versionId = params.get("version_id");
    const workbookId = params.get("workbook_id");

    const formsBackBtn    = document.getElementById("btn-builder-forms-back");
    const tabFieldsLabel  = document.getElementById("tab-fields-label");
    const sectionSubtext  = document.getElementById("sections-panel-subtext");

    if (workbookId) {
      isWorkbookContext = true;
      // Show workbook return link
      const bar  = document.getElementById("fb-return-link-bar");
      const link = document.getElementById("fb-return-link");
      if (bar && link) {
        link.href = "/workbooks/" + workbookId;
        link.textContent = "← Back to Workbook";
        bar.classList.remove("hidden");
      }
      // Hide redundant sheet-list button — workbook link is the only back nav
      if (formsBackBtn) formsBackBtn.classList.add("hidden");
      // Relabel publish button, centre panel tab, left panel subtext
      if (btnPublishForm) btnPublishForm.textContent = "Publish Sheet";
      if (tabFieldsLabel) tabFieldsLabel.textContent = "Fields in This Sheet";
      if (sectionSubtext) sectionSubtext.textContent = "Choose column groups within this sheet.";
      // Auto-trigger create flow when no existing form is being edited
      if (!formId) {
        startNew();

        // WorkbookSite is the authoritative workbook-site assignment.
        // Keep legacy site applicability populated so old save validation does not block sheet creation.
        dfSitesList.querySelectorAll("input[type='checkbox']").forEach(cb => {
          cb.checked = true;
        });
      }
    } else if (formsBackBtn) {
      formsBackBtn.textContent = "← Workbooks";
      formsBackBtn.onclick = function () {
        window.location.href = "/workbooks/";
      };
    }

    if (!formId || !versionId) return;

    if (prefillFormulaVersionId && fieldCode) {
      pendingPrefill = {
        formulaVersionId: parseInt(prefillFormulaVersionId, 10),
        fieldCode: fieldCode
      };
    } else if (fieldCode) {
      pendingPrefill = { fieldCode: fieldCode };
    }

    // Clean URL before navigating into the builder
    window.history.replaceState({}, "", window.location.pathname);
    editFormLayout(parseInt(formId, 10), parseInt(versionId, 10));
  }

  // Run initial setup
  init();
});
