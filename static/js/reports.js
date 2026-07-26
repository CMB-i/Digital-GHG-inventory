(function () {
  "use strict";

  // Elements
  const openDrawerBtn = document.getElementById("open_create_drawer_btn");
  const closeDrawerBtn = document.getElementById("close_create_drawer_btn");
  const closeDrawerSecBtn = document.getElementById("close_create_drawer_secondary");
  const drawer = document.getElementById("create_drawer");
  const backdrop = document.getElementById("drawer_backdrop");
  const drawerTitle = document.getElementById("drawer_title");
  const scopeTypeSelect = document.getElementById("template_scope_type");
  const scopeSiteContainer = document.getElementById("scope_site_container");
  const createForm = document.getElementById("create_template_form");
  const feedbackContainer = document.getElementById("feedback_container");

  const previewTitle = document.getElementById("preview_title");
  const previewSubtitle = document.getElementById("preview_subtitle");
  const previewActions = document.getElementById("preview_actions");
  const previewSearch = document.getElementById("preview_search");
  const previewExportBtn = document.getElementById("preview_export_btn");
  const previewEmptyState = document.getElementById("preview_empty_state");
  const previewLoadingState = document.getElementById("preview_loading_state");
  const previewTableWrapper = document.getElementById("preview_table_wrapper");
  const previewTbody = document.getElementById("preview_tbody");
  const previewPivotWrapper = document.getElementById("preview_pivot_wrapper");
  const previewPivotThead = document.getElementById("preview_pivot_thead");
  const previewPivotTbody = document.getElementById("preview_pivot_tbody");

  // Row Groups panel
  const rowGroupsList = document.getElementById("row_groups_list");
  const btnAddRowGroup = document.getElementById("btn_add_row_group");
  const rowGroupBlockTemplate = document.getElementById("row_group_block_template");

  // Metric Aliasing panel
  const metricAliasesList = document.getElementById("metric_aliases_list");

  // Computed Columns panel -- no longer gated; a real template id exists
  // unconditionally by the time this step is reachable (see Step 1).
  const computedColumnsList = document.getElementById("computed_columns_list");
  const btnAddComputedColumn = document.getElementById("btn_add_computed_column");

  // Wizard chrome
  const wizardRail = document.getElementById("wizard_rail");
  const wizardRailItems = Array.from(wizardRail.querySelectorAll(".wizard-rail-item"));
  const wizardSteps = Array.from(createForm.querySelectorAll(".wizard-step"));
  const wizardBackBtn = document.getElementById("wizard_back_btn");
  const wizardContinueBtn = document.getElementById("wizard_continue_btn");
  const WIZARD_STEP_COUNT = wizardSteps.length; // 7: Basics, Scope & Entities, Row Groups, Metric Aliasing, Computed Columns, Date Range, Review
  const REVIEW_STEP_INDEX = WIZARD_STEP_COUNT - 1;
  const ROW_GROUPS_STEP_INDEX = 2;
  const COMPUTED_COLUMNS_STEP_INDEX = 4;

  // Review step preview targets (separate from the main page's preview pane
  // elements above -- renderPreviewTable/renderPivotPreviewTable are
  // parameterized to draw into either set, see below).
  const reviewLoadingState = document.getElementById("review_loading_state");
  const reviewPreviewTableWrapper = document.getElementById("review_preview_table_wrapper");
  const reviewPreviewTbody = document.getElementById("review_preview_tbody");
  const reviewPreviewPivotWrapper = document.getElementById("review_preview_pivot_wrapper");
  const reviewPreviewPivotThead = document.getElementById("review_preview_pivot_thead");
  const reviewPreviewPivotTbody = document.getElementById("review_preview_pivot_tbody");

  let activePreviewData = [];

  // null => Step 1 not yet saved; a real template id from Step 1 onward.
  let currentTemplateId = null;
  // The most recently loaded/saved config_json, kept around so panels that
  // don't have UI in this phase (e.g. computed-column override entries in
  // metric_aliases) are preserved rather than silently dropped on save.
  let existingConfigJson = null;

  let currentStepIndex = 0;
  let highestVisitedStepIndex = 0;

  let canonicalMetrics = [];
  let formsListCache = null;
  const fieldOptionsCache = {}; // form_id -> [{field_id, field_code, field_name, form_name}]
  let rowGroupBlockCounter = 0;
  let computedColumnCounter = 0;

  // ── Small helpers ────────────────────────────────────────────────────
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str === null || str === undefined ? "" : String(str);
    return div.innerHTML;
  }

  function slugifyId(text) {
    const slug = (text || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    return slug || "group";
  }

  function metricDisplayLabel(key) {
    return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  }

  function setSelectValue(selectEl, value) {
    if (!selectEl) return;
    selectEl.value = value !== null && value !== undefined ? String(value) : "";
  }

  // Feedback messaging helper
  function showFeedback(message, type = "success") {
    feedbackContainer.classList.remove("hidden", "border-emerald-200", "bg-emerald-50", "text-emerald-700", "border-red-200", "bg-red-50", "text-red-700");
    if (type === "success") {
      feedbackContainer.classList.add("border-emerald-200", "bg-emerald-50", "text-emerald-700");
    } else {
      feedbackContainer.classList.add("border-red-200", "bg-red-50", "text-red-700");
    }
    feedbackContainer.textContent = message;
    feedbackContainer.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Drawer Toggles
  function openDrawer() {
    backdrop.classList.remove("hidden");
    setTimeout(() => {
      backdrop.classList.remove("opacity-0");
      drawer.classList.remove("translate-x-full");
    }, 50);
  }

  // A template already exists past Step 1, so closing mid-wizard needs the
  // templates list (left column) to reflect whatever was actually saved so
  // far -- a plain in-place close would leave a real, saved template
  // invisible until the next manual page load. Nothing to reload if the
  // user bails during Step 1 itself, since nothing has been created yet.
  function closeDrawer() {
    if (currentTemplateId !== null) {
      window.location.href = "/module/RPTBLD/";
      return;
    }
    drawer.classList.add("translate-x-full");
    backdrop.classList.add("opacity-0");
    setTimeout(() => {
      backdrop.classList.add("hidden");
    }, 300);
    createForm.reset();
    scopeSiteContainer.classList.add("hidden");
  }

  if (closeDrawerBtn) closeDrawerBtn.addEventListener("click", closeDrawer);
  if (closeDrawerSecBtn) closeDrawerSecBtn.addEventListener("click", closeDrawer);
  if (backdrop) {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) closeDrawer();
    });
  }

  // Scope Type Visibility Toggle
  if (scopeTypeSelect) {
    scopeTypeSelect.addEventListener("change", function () {
      if (this.value === "site") {
        scopeSiteContainer.classList.remove("hidden");
        document.getElementById("template_scope_site_id").setAttribute("required", "required");
      } else {
        scopeSiteContainer.classList.add("hidden");
        document.getElementById("template_scope_site_id").removeAttribute("required");
      }
    });
  }

  // ════════════════════════════════════════════════════════════════════
  // Wizard navigation
  // ════════════════════════════════════════════════════════════════════
  function renderWizardRail() {
    wizardRailItems.forEach((el, i) => {
      const badge = el.querySelector(".wizard-rail-badge");
      const isCurrent = i === currentStepIndex;
      const isReachable = i <= highestVisitedStepIndex;
      const isCompleted = isReachable && !isCurrent;

      el.classList.remove("bg-slate-900", "text-white", "text-emerald-700", "hover:bg-slate-100", "text-slate-400", "cursor-not-allowed");
      badge.classList.remove("bg-white", "text-slate-900", "bg-emerald-100", "text-emerald-700", "bg-slate-200", "text-slate-400");

      if (isCurrent) {
        el.classList.add("bg-slate-900", "text-white");
        badge.classList.add("bg-white", "text-slate-900");
        badge.textContent = String(i + 1);
      } else if (isCompleted) {
        el.classList.add("text-emerald-700", "hover:bg-slate-100");
        badge.classList.add("bg-emerald-100", "text-emerald-700");
        badge.textContent = "✓";
      } else {
        el.classList.add("text-slate-400", "cursor-not-allowed");
        badge.classList.add("bg-slate-200", "text-slate-400");
        badge.textContent = String(i + 1);
      }

      el.disabled = !isReachable;
    });
  }

  function updateWizardFooter() {
    wizardBackBtn.disabled = currentStepIndex === 0;
    wizardContinueBtn.textContent = currentStepIndex === REVIEW_STEP_INDEX ? "Finish" : "Save & Continue";
  }

  function showStep(index) {
    currentStepIndex = index;
    highestVisitedStepIndex = Math.max(highestVisitedStepIndex, index);
    wizardSteps.forEach(el => {
      el.classList.toggle("hidden", parseInt(el.dataset.stepIndex, 10) !== index);
    });
    renderWizardRail();
    updateWizardFooter();
    if (index === REVIEW_STEP_INDEX) {
      loadReviewPreview();
    }
  }

  wizardRailItems.forEach(el => {
    el.addEventListener("click", function () {
      const target = parseInt(this.dataset.stepIndex, 10);
      if (target <= highestVisitedStepIndex) showStep(target);
    });
  });

  wizardBackBtn.addEventListener("click", function () {
    if (currentStepIndex > 0) showStep(currentStepIndex - 1);
  });

  wizardContinueBtn.addEventListener("click", async function () {
    if (currentStepIndex === REVIEW_STEP_INDEX) {
      window.location.href = "/module/RPTBLD/";
      return;
    }

    if (currentStepIndex === 0 && currentTemplateId === null) {
      const created = await createTemplateFromBasics();
      if (!created) return;
      showStep(1);
      return;
    }

    if (currentStepIndex === ROW_GROUPS_STEP_INDEX && !validateRowGroupsClientSide()) {
      return;
    }

    const saved = await saveTemplateProgress();
    if (!saved) return;
    showStep(currentStepIndex + 1);
  });

  // ════════════════════════════════════════════════════════════════════
  // Drawer entry points
  // ════════════════════════════════════════════════════════════════════
  function resetWizardState() {
    currentTemplateId = null;
    existingConfigJson = null;
    currentStepIndex = 0;
    highestVisitedStepIndex = 0;
    createForm.reset();
    rowGroupsList.innerHTML = "";
    computedColumnsList.innerHTML = "";
    scopeSiteContainer.classList.add("hidden");
    document.getElementById("template_code").disabled = false;
  }

  function openDrawerForCreate() {
    resetWizardState();
    renderMetricAliasesPanel();
    drawerTitle.textContent = "Create Report Template";
    showStep(0);
    openDrawer();
  }

  async function openDrawerForEdit(templateId, landingStepIndex) {
    try {
      const res = await fetch(`/module/RPTBLD/api/templates/${templateId}`);
      if (!res.ok) {
        showFeedback("Could not load template for editing.", "error");
        return;
      }
      const t = await res.json();
      resetWizardState();
      currentTemplateId = templateId;
      existingConfigJson = t.config_json || {};

      document.getElementById("template_name").value = t.name || "";
      document.getElementById("template_code").value = t.code || "";
      document.getElementById("template_code").disabled = true; // immutable post-creation
      document.getElementById("template_description").value = t.description || "";
      scopeTypeSelect.value = t.scope_type || "global";
      scopeTypeSelect.dispatchEvent(new Event("change"));
      if (t.scope_site_id) {
        setSelectValue(document.getElementById("template_scope_site_id"), t.scope_site_id);
      }

      const formIds = new Set(existingConfigJson.form_ids || []);
      createForm.querySelectorAll("input[name='form_ids']").forEach(cb => {
        cb.checked = formIds.has(parseInt(cb.value, 10));
      });
      const siteIds = new Set(existingConfigJson.site_ids || []);
      createForm.querySelectorAll("input[name='site_ids']").forEach(cb => {
        cb.checked = siteIds.has(parseInt(cb.value, 10));
      });

      setSelectValue(createForm.querySelector("select[name='start_month']"), existingConfigJson.start_month);
      setSelectValue(createForm.querySelector("select[name='start_year']"), existingConfigJson.start_year);
      setSelectValue(createForm.querySelector("select[name='end_month']"), existingConfigJson.end_month);
      setSelectValue(createForm.querySelector("select[name='end_year']"), existingConfigJson.end_year);

      (existingConfigJson.row_groups || []).forEach(g => addRowGroupBlock(g));
      await renderMetricAliasesPanel(existingConfigJson.metric_aliases || {});
      renderComputedColumnsPanel(existingConfigJson.computed_columns || []);

      drawerTitle.textContent = "Edit Report Template";
      highestVisitedStepIndex = WIZARD_STEP_COUNT - 1; // every step is reachable -- the template already has all of this data
      showStep(landingStepIndex || 0);
      openDrawer();
    } catch (err) {
      console.error(err);
      showFeedback("Error loading template for editing.", "error");
    }
  }

  if (openDrawerBtn) openDrawerBtn.addEventListener("click", openDrawerForCreate);

  document.querySelectorAll(".edit-template-btn").forEach(btn => {
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      window.location.href = "/module/RPTBLD/?edit_template_id=" + this.dataset.templateId;
    });
  });

  // ════════════════════════════════════════════════════════════════════
  // Row Groups panel (unchanged internals -- moved into Step 3's container)
  // ════════════════════════════════════════════════════════════════════
  function addRowGroupBlock(prefill) {
    rowGroupBlockCounter += 1;
    const frag = rowGroupBlockTemplate.content.cloneNode(true);
    const block = frag.querySelector(".row-group-block");
    block.dataset.rgUid = "rg_" + rowGroupBlockCounter;
    block.dataset.rgId = (prefill && prefill.id) || "";

    const labelInput = block.querySelector(".rg-label");
    const subtotalInput = block.querySelector(".rg-subtotal-label");
    const includeCheckbox = block.querySelector(".rg-include-grand-total");
    const referenceRadio = block.querySelector(".rg-reference-base");
    const removeBtn = block.querySelector(".remove-row-group-btn");
    const heading = block.querySelector(".rg-heading");

    if (prefill) {
      labelInput.value = prefill.label || "";
      subtotalInput.value = prefill.subtotal_label || "";
      includeCheckbox.checked = prefill.include_in_grand_total !== false;
      if (prefill.is_reference_base) referenceRadio.checked = true;
      (prefill.site_ids || []).forEach(sid => {
        const cb = block.querySelector(`.rg-site-checkbox[value="${sid}"]`);
        if (cb) cb.checked = true;
      });
    }

    function updateHeading() {
      heading.textContent = labelInput.value.trim() || "Row Group";
    }
    labelInput.addEventListener("input", updateHeading);
    updateHeading();

    removeBtn.addEventListener("click", function () {
      block.remove();
    });

    rowGroupsList.appendChild(block);
    return block;
  }

  if (btnAddRowGroup) btnAddRowGroup.addEventListener("click", () => addRowGroupBlock());

  // Exactly one is_reference_base, mirroring validate_row_groups -- a UX
  // nicety only, the real enforcement is server-side in validate_report_config.
  function validateRowGroupsClientSide() {
    const blocks = rowGroupsList.querySelectorAll(".row-group-block");
    if (blocks.length === 0) return true;
    const checkedCount = rowGroupsList.querySelectorAll(".rg-reference-base:checked").length;
    if (checkedCount !== 1) {
      showFeedback(`Exactly one row group must be marked "Reference base" (found ${checkedCount}).`, "error");
      return false;
    }
    return true;
  }

  function collectRowGroups() {
    const blocks = Array.from(rowGroupsList.querySelectorAll(".row-group-block"));
    const usedIds = new Set();
    return blocks.map(block => {
      const label = block.querySelector(".rg-label").value.trim();
      const base = slugifyId(block.dataset.rgId || label);
      let candidate = base;
      let n = 2;
      while (usedIds.has(candidate)) {
        candidate = base + "_" + n;
        n += 1;
      }
      usedIds.add(candidate);
      block.dataset.rgId = candidate;

      const siteIds = Array.from(block.querySelectorAll(".rg-site-checkbox:checked")).map(cb => parseInt(cb.value, 10));
      return {
        id: candidate,
        label: label,
        subtotal_label: block.querySelector(".rg-subtotal-label").value.trim(),
        site_ids: siteIds,
        include_in_grand_total: block.querySelector(".rg-include-grand-total").checked,
        is_reference_base: block.querySelector(".rg-reference-base").checked,
      };
    });
  }

  // ════════════════════════════════════════════════════════════════════
  // Metric Aliasing panel (unchanged internals -- moved into Step 4's container)
  // ════════════════════════════════════════════════════════════════════
  async function loadCanonicalMetrics() {
    if (canonicalMetrics.length) return canonicalMetrics;
    const res = await fetch("/module/RPTBLD/api/canonical-metrics");
    const data = await res.json();
    canonicalMetrics = data.metrics || [];
    return canonicalMetrics;
  }

  async function getFieldOptionsForApplicableForms() {
    const checkedFormIds = Array.from(createForm.querySelectorAll("input[name='form_ids']:checked")).map(el => parseInt(el.value, 10));
    const targetFormIds = checkedFormIds.length ? checkedFormIds : (window.RPTBLD_FORMS || []).map(f => f.id);

    if (!formsListCache) {
      const res = await fetch("/module/FORMBLD/api");
      formsListCache = await res.json();
    }

    const numericTypes = ["number", "integer", "decimal", "float", "numeric", "calculated"];
    const results = [];
    for (const formId of targetFormIds) {
      if (fieldOptionsCache[formId]) {
        results.push(...fieldOptionsCache[formId]);
        continue;
      }
      const formMeta = formsListCache.find(f => f.id === formId);
      const versionId = formMeta && (formMeta.current_version_id || formMeta.latest_version_id);
      if (!versionId) continue;
      try {
        const verRes = await fetch(`/module/FORMBLD/api/version/${versionId}`);
        const verData = await verRes.json();
        const opts = (verData.fields || [])
          .filter(f => numericTypes.includes((f.field_type || "").toLowerCase()))
          .map(f => ({ field_id: f.id, field_code: f.field_code, field_name: f.field_name, form_name: formMeta.name }));
        fieldOptionsCache[formId] = opts;
        results.push(...opts);
      } catch (err) {
        console.error("Error loading fields for form", formId, err);
      }
    }
    return results;
  }

  function ensureFieldSelectCount(row, count) {
    const container = row.querySelector(".malias-fields");
    const selects = Array.from(container.querySelectorAll(".malias-field"));
    while (selects.length < count) {
      const clone = selects[0].cloneNode(true);
      clone.value = "";
      container.appendChild(clone);
      selects.push(clone);
    }
    while (selects.length > count) {
      selects.pop().remove();
    }
  }

  function onMetricAliasOpChange(row) {
    const op = row.querySelector(".malias-op").value;
    const addBtn = row.querySelector(".malias-add-field");
    if (op === "sum") {
      addBtn.classList.remove("hidden");
      ensureFieldSelectCount(row, Math.max(2, row.querySelectorAll(".malias-field").length));
    } else {
      addBtn.classList.add("hidden");
      ensureFieldSelectCount(row, 1);
    }
  }

  function updateMetricAliasCount(metricKey) {
    const block = metricAliasesList.querySelector(`.metric-alias-block[data-metric-key="${metricKey}"]`);
    if (!block) return;
    const count = block.querySelectorAll(".metric-alias-row").length;
    const countEl = block.querySelector(".metric-alias-count");
    if (countEl) countEl.textContent = `${count} mapping${count === 1 ? "" : "s"}`;
  }

  async function addMetricAliasRow(metricKey, prefill) {
    const block = metricAliasesList.querySelector(`.metric-alias-block[data-metric-key="${metricKey}"]`);
    if (!block) return;
    const rowsContainer = block.querySelector(".metric-alias-rows");

    const fieldOptions = await getFieldOptionsForApplicableForms();
    const siteOptionsHtml = (window.RPTBLD_SITES || []).map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");
    const fieldOptionsHtml = `<option value="">Select field…</option>` +
      fieldOptions.map(f => `<option value="${f.field_id}">${escapeHtml(f.field_name)} (${escapeHtml(f.form_name)})</option>`).join("");

    const row = document.createElement("div");
    row.className = "metric-alias-row flex flex-wrap items-center gap-2 bg-white border border-slate-200 rounded-md p-2";
    row.innerHTML = `
      <select class="malias-site text-[11px] rounded border-slate-300 py-1 px-1.5">${siteOptionsHtml}</select>
      <div class="malias-fields flex flex-col gap-1 flex-1 min-w-[160px]">
        <select class="malias-field text-[11px] rounded border-slate-300 py-1 px-1.5 w-full">${fieldOptionsHtml}</select>
      </div>
      <button type="button" class="malias-add-field text-[10px] text-indigo-600 hover:text-indigo-800 hidden">+ field</button>
      <select class="malias-op text-[11px] rounded border-slate-300 py-1 px-1.5">
        <option value="single">Single</option>
        <option value="sum">Sum</option>
      </select>
      <label class="flex items-center gap-1 text-[10px] text-slate-600 cursor-pointer">
        <input type="checkbox" class="malias-verified rounded text-slate-900"> Verified
      </label>
      <button type="button" class="remove-metric-alias-row-btn text-rose-500 hover:text-rose-700 text-[11px] font-bold">✕</button>
    `;
    rowsContainer.appendChild(row);

    row.querySelector(".malias-add-field").onclick = () =>
      ensureFieldSelectCount(row, row.querySelectorAll(".malias-field").length + 1);
    row.querySelector(".malias-op").onchange = () => onMetricAliasOpChange(row);
    row.querySelector(".remove-metric-alias-row-btn").onclick = () => {
      row.remove();
      updateMetricAliasCount(metricKey);
    };

    if (prefill) {
      setSelectValue(row.querySelector(".malias-site"), prefill.site_id);
      setSelectValue(row.querySelector(".malias-op"), prefill.op || "single");
      const verifiedBox = row.querySelector(".malias-verified");
      if (verifiedBox) verifiedBox.checked = !!prefill.verified;
      const fieldIds = prefill.field_ids || [];
      ensureFieldSelectCount(row, Math.max(1, fieldIds.length));
      const selects = row.querySelectorAll(".malias-field");
      fieldIds.forEach((fid, idx) => { if (selects[idx]) setSelectValue(selects[idx], fid); });
      if (prefill.op === "sum") row.querySelector(".malias-add-field").classList.remove("hidden");
    }

    updateMetricAliasCount(metricKey);
  }

  async function renderMetricAliasesPanel(prefillAliases) {
    await loadCanonicalMetrics();
    metricAliasesList.innerHTML = "";

    canonicalMetrics.forEach(key => {
      const details = document.createElement("details");
      details.className = "metric-alias-block border border-slate-200 rounded-md bg-slate-50";
      details.dataset.metricKey = key;
      details.innerHTML = `
        <summary class="cursor-pointer px-3 py-2 text-xs font-bold text-slate-700 flex items-center justify-between select-none">
          <span>${escapeHtml(metricDisplayLabel(key))}</span>
          <span class="metric-alias-count text-[10px] font-normal text-slate-400">0 mappings</span>
        </summary>
        <div class="px-3 pb-3 space-y-2">
          <div class="metric-alias-rows space-y-2"></div>
          <button type="button" class="add-metric-alias-row-btn text-[11px] font-semibold text-indigo-600 hover:text-indigo-800">+ Add mapping</button>
        </div>
      `;
      metricAliasesList.appendChild(details);
      details.querySelector(".add-metric-alias-row-btn").onclick = () => addMetricAliasRow(key);
    });

    if (prefillAliases) {
      for (const [metricKey, entries] of Object.entries(prefillAliases)) {
        if (!canonicalMetrics.includes(metricKey)) continue; // computed-column override keys aren't editable here
        for (const entry of entries) {
          await addMetricAliasRow(metricKey, entry);
        }
      }
    }
  }

  function collectMetricAliases() {
    const result = {};
    metricAliasesList.querySelectorAll(".metric-alias-block").forEach(block => {
      const metricKey = block.dataset.metricKey;
      const entries = [];
      block.querySelectorAll(".metric-alias-row").forEach(row => {
        const siteId = parseInt(row.querySelector(".malias-site").value, 10);
        const op = row.querySelector(".malias-op").value;
        const verified = row.querySelector(".malias-verified").checked;
        const fieldIds = Array.from(row.querySelectorAll(".malias-field"))
          .map(sel => parseInt(sel.value, 10))
          .filter(v => !isNaN(v));
        if (!siteId || fieldIds.length === 0) return; // skip incomplete rows
        entries.push({ site_id: siteId, field_ids: fieldIds, op: op, verified: verified });
      });
      if (entries.length) result[metricKey] = entries;
    });

    // Preserve pre-existing non-canonical-metric alias keys (computed-column
    // overrides, e.g. "H") this panel doesn't edit, so saving never silently
    // destroys them.
    if (existingConfigJson && existingConfigJson.metric_aliases) {
      Object.entries(existingConfigJson.metric_aliases).forEach(([key, entries]) => {
        if (!canonicalMetrics.includes(key) && !result[key]) {
          result[key] = entries;
        }
      });
    }
    return result;
  }

  // ════════════════════════════════════════════════════════════════════
  // Computed Columns panel (unchanged internals -- moved into Step 5's
  // container; the disabled/"save first" gating that used to live here is
  // gone, since Step 1 guarantees a real currentTemplateId before this step
  // is ever reachable)
  // ════════════════════════════════════════════════════════════════════
  function addComputedColumnEntry(prefill) {
    computedColumnCounter += 1;
    const hasFormula = !!(prefill && prefill.formula_id);

    const row = document.createElement("div");
    row.className = "computed-column-row border border-slate-200 rounded-md p-2.5 bg-slate-50 flex flex-wrap items-center gap-2";
    row.dataset.ccUid = "cc_" + computedColumnCounter;
    row.dataset.ccId = (prefill && prefill.id) || "";
    row.dataset.formulaId = hasFormula ? String(prefill.formula_id) : "";

    row.innerHTML = `
      <input type="text" class="cc-label flex-1 min-w-[160px] rounded-md border border-slate-300 px-2.5 py-1.5 text-xs focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
             placeholder="e.g. Energy Intensity (Aggregate)" value="${prefill ? escapeHtml(prefill.label || "") : ""}">
      <span class="cc-status text-[10px] font-semibold ${hasFormula ? "text-emerald-600" : "text-amber-600"}">
        ${hasFormula ? "Formula attached" : "No formula yet"}
      </span>
      <button type="button" class="cc-build-btn text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 whitespace-nowrap">
        ${hasFormula ? "View Formula →" : "Build Formula →"}
      </button>
      <button type="button" class="remove-computed-column-btn text-rose-500 hover:text-rose-700 text-[11px] font-bold">✕</button>
    `;
    computedColumnsList.appendChild(row);

    row.querySelector(".remove-computed-column-btn").onclick = () => row.remove();
    row.querySelector(".cc-build-btn").onclick = () => goBuildComputedColumnFormula(row);

    return row;
  }

  function renderComputedColumnsPanel(prefillColumns) {
    computedColumnsList.innerHTML = "";
    (prefillColumns || []).forEach(col => addComputedColumnEntry(col));
  }

  function collectComputedColumns() {
    const usedIds = new Set();
    return Array.from(computedColumnsList.querySelectorAll(".computed-column-row"))
      .map(row => {
        const label = row.querySelector(".cc-label").value.trim();
        const base = slugifyId(row.dataset.ccId || label);
        let candidate = base;
        let n = 2;
        while (usedIds.has(candidate)) {
          candidate = base + "_" + n;
          n += 1;
        }
        usedIds.add(candidate);
        row.dataset.ccId = candidate;
        return {
          id: candidate,
          label: label,
          formula_id: row.dataset.formulaId ? parseInt(row.dataset.formulaId, 10) : null,
        };
      })
      .filter(c => c.label);
  }

  function buildConfigJsonFromForm() {
    const formIds = Array.from(createForm.querySelectorAll("input[name='form_ids']:checked")).map(el => parseInt(el.value, 10));
    const siteIds = Array.from(createForm.querySelectorAll("input[name='site_ids']:checked")).map(el => parseInt(el.value, 10));
    const startMonthVal = createForm.querySelector("select[name='start_month']").value;
    const startYearVal = createForm.querySelector("select[name='start_year']").value;
    const endMonthVal = createForm.querySelector("select[name='end_month']").value;
    const endYearVal = createForm.querySelector("select[name='end_year']").value;

    // Start from whatever config_json already exists (e.g. a previously
    // saved grand_total_label or any other key this drawer has no panel
    // for) and only overwrite the keys this drawer actually manages --
    // same instinct as collectMetricAliases()'s override-key preservation,
    // generalized to the whole object so nothing unmanaged is silently
    // dropped on save.
    return {
      ...(existingConfigJson || {}),
      form_ids: formIds,
      site_ids: siteIds,
      start_month: startMonthVal ? parseInt(startMonthVal, 10) : null,
      start_year: startYearVal ? parseInt(startYearVal, 10) : null,
      end_month: endMonthVal ? parseInt(endMonthVal, 10) : null,
      end_year: endYearVal ? parseInt(endYearVal, 10) : null,
      row_groups: collectRowGroups(),
      metric_aliases: collectMetricAliases(),
      computed_columns: collectComputedColumns(),
    };
  }

  // Step 1 only: creates the template for real the moment "Continue" is
  // clicked, mirroring FORMBLD's sheet builder (its Form row is created at
  // its own Step 1, before the layout editor ever opens against a real
  // form.id). Every step after this one operates against a real
  // currentTemplateId and saves via saveTemplateProgress() below.
  async function createTemplateFromBasics() {
    const name = document.getElementById("template_name").value.trim();
    const code = document.getElementById("template_code").value.trim();
    if (!name) { showFeedback("Report name is required.", "error"); return false; }
    if (!code) { showFeedback("Unique code is required.", "error"); return false; }

    const payload = {
      name: name,
      code: code,
      description: document.getElementById("template_description").value,
      scope_type: "global",
      scope_site_id: null,
      config_json: {},
    };

    try {
      const res = await fetch("/module/RPTBLD/api/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.status !== "success") {
        showFeedback(data.message || "Failed to save report template.", "error");
        return false;
      }
      currentTemplateId = data.template.id;
      existingConfigJson = data.template.config_json || {};
      document.getElementById("template_code").disabled = true; // immutable from here on
      drawerTitle.textContent = "Edit Report Template";
      return true;
    } catch (err) {
      console.error(err);
      showFeedback("An unexpected network error occurred.", "error");
      return false;
    }
  }

  // The one save path every step from Step 2 onward uses to advance --
  // generalized from what used to be a FRMULA-round-trip-only helper.
  // Leaving mid-wizard, refreshing, or navigating to FRMULA and back all hit
  // this same path, including the fix that preserves unmanaged config_json
  // keys (see buildConfigJsonFromForm()).
  async function saveTemplateProgress() {
    const payload = {
      name: document.getElementById("template_name").value,
      description: document.getElementById("template_description").value,
      scope_type: scopeTypeSelect.value,
      scope_site_id: scopeTypeSelect.value === "site" ? parseInt(document.getElementById("template_scope_site_id").value, 10) : null,
      config_json: buildConfigJsonFromForm(),
    };
    try {
      const res = await fetch(`/module/RPTBLD/api/templates/${currentTemplateId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.status !== "success") {
        showFeedback(data.message || "Failed to save template before continuing.", "error");
        return false;
      }
      existingConfigJson = data.template.config_json;
      return true;
    } catch (err) {
      console.error(err);
      showFeedback("Network error while saving template.", "error");
      return false;
    }
  }

  async function goBuildComputedColumnFormula(row) {
    const label = row.querySelector(".cc-label").value.trim();
    if (!label) {
      showFeedback("Give this computed column a label before building its formula.", "error");
      return;
    }
    if (!currentTemplateId) {
      // Defensive only -- unreachable in practice, since this step is never
      // shown before Step 1 has created a real template.
      showFeedback("Save the template first.", "error");
      return;
    }
    if (!validateRowGroupsClientSide()) return;

    let ccId = row.dataset.ccId;
    if (!ccId) {
      ccId = slugifyId(label);
      row.dataset.ccId = ccId;
    }

    const saved = await saveTemplateProgress();
    if (!saved) return;

    const params = new URLSearchParams();
    params.set("return_to", "/module/RPTBLD/");
    params.set("report_template_id", String(currentTemplateId));
    params.set("context", "report");
    params.set("cc_id", ccId);
    params.set("cc_label", label);
    if (row.dataset.formulaId) params.set("open_formula_id", row.dataset.formulaId);

    window.location.href = "/module/FRMULA/?" + params.toString();
  }

  if (btnAddComputedColumn) {
    btnAddComputedColumn.addEventListener("click", function () {
      addComputedColumnEntry();
    });
  }

  // ════════════════════════════════════════════════════════════════════
  // Auto-open the edit wizard -- shared by "Edit" clicks and returning from
  // FRMULA with a newly built/published formula (report_template_id +
  // formula_id + cc_id on the URL). The latter lands directly on the
  // Computed Columns step instead of Step 1, so the person sees their
  // newly-attached formula immediately.
  // ════════════════════════════════════════════════════════════════════
  async function maybeAutoOpenEditDrawer() {
    const params = new URLSearchParams(window.location.search);
    const templateIdRaw = params.get("edit_template_id") || params.get("report_template_id");
    if (!templateIdRaw) return;
    const templateId = parseInt(templateIdRaw, 10);
    if (isNaN(templateId)) return;

    const returnedFormulaId = params.get("formula_id");
    const ccId = params.get("cc_id");
    const landingStep = (returnedFormulaId && ccId) ? COMPUTED_COLUMNS_STEP_INDEX : 0;

    await openDrawerForEdit(templateId, landingStep);

    if (returnedFormulaId && ccId) {
      let row = Array.from(computedColumnsList.querySelectorAll(".computed-column-row"))
        .find(r => r.dataset.ccId === ccId);
      if (!row) {
        row = addComputedColumnEntry({ id: ccId, label: params.get("cc_label") || ccId, formula_id: null });
      }
      row.dataset.formulaId = returnedFormulaId;
      const statusEl = row.querySelector(".cc-status");
      statusEl.textContent = "Formula attached";
      statusEl.className = "cc-status text-[10px] font-semibold text-emerald-600";
      row.querySelector(".cc-build-btn").textContent = "View Formula →";

      // Persist the returned formula_id immediately -- the person already
      // left and came back once for this; don't make them click Continue
      // again just to avoid losing it a second time.
      await saveTemplateProgress();
      showFeedback('Computed column formula attached and saved.', "success");
    }

    // Clean the URL so a page refresh doesn't re-trigger this.
    window.history.replaceState({}, "", "/module/RPTBLD/");
  }

  // Enter-key-in-a-text-input can still trigger a native form submit even
  // with no type="submit" button in the form; guard against a page reload.
  if (createForm) {
    createForm.addEventListener("submit", function (e) {
      e.preventDefault();
    });
  }

  // Delete Template Action
  document.querySelectorAll(".delete-template-btn").forEach(btn => {
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      const templateId = this.dataset.templateId;
      if (!confirm("Are you sure you want to delete this report template?")) {
        return;
      }

      fetch(`/module/RPTBLD/api/templates/${templateId}`, {
        method: "DELETE"
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === "success") {
          showFeedback("Report template deleted.", "success");
          // Remove from list DOM
          const card = document.querySelector(`.template-card[data-template-id="${templateId}"]`);
          if (card) card.remove();
          // Reset preview panel if deleted template was active
          if (previewExportBtn.getAttribute("href") && previewExportBtn.getAttribute("href").includes(`/${templateId}/`)) {
            resetPreviewPane();
          }
        } else {
          showFeedback(data.message || "Failed to delete template.", "error");
        }
      })
      .catch(err => {
        console.error(err);
        showFeedback("Error deleting template.", "error");
      });
    });
  });

  function resetPreviewPane() {
    previewTitle.textContent = "Report Preview";
    previewSubtitle.textContent = "Select a report template to preview aggregated data.";
    previewActions.classList.add("hidden");
    previewEmptyState.classList.remove("hidden");
    previewLoadingState.classList.add("hidden");
    previewTableWrapper.classList.add("hidden");
    previewPivotWrapper.classList.add("hidden");
    activePreviewData = [];
  }

  // Preview Action -- branches to the pivot renderer when the template has
  // row_groups configured, otherwise keeps the original flat rendering path
  // completely intact.
  document.querySelectorAll(".preview-template-btn").forEach(btn => {
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      const templateId = this.dataset.templateId;
      const card = document.querySelector(`.template-card[data-template-id="${templateId}"]`);
      const templateName = card ? card.querySelector("h3").textContent : "Report";

      previewEmptyState.classList.add("hidden");
      previewTableWrapper.classList.add("hidden");
      previewPivotWrapper.classList.add("hidden");
      previewLoadingState.classList.remove("hidden");
      previewActions.classList.add("hidden");
      previewTitle.textContent = `Preview: ${templateName}`;
      previewSubtitle.textContent = "Fetching environmental data...";

      fetch(`/module/RPTBLD/api/templates/${templateId}`)
        .then(res => res.json())
        .then(t => {
          const isPivot = !!(t.config_json && t.config_json.row_groups && t.config_json.row_groups.length);
          const endpoint = isPivot
            ? `/module/RPTBLD/api/templates/${templateId}/pivot-preview`
            : `/module/RPTBLD/api/templates/${templateId}/preview`;

          return fetch(endpoint)
            .then(res => res.json())
            .then(async resData => {
              previewLoadingState.classList.add("hidden");
              if (resData.status !== "success") {
                previewSubtitle.textContent = "Error loading report data.";
                previewEmptyState.classList.remove("hidden");
                showFeedback(resData.message || "Failed to fetch preview data.", "error");
                return;
              }

              if (isPivot) {
                activePreviewData = null;
                await loadCanonicalMetrics();
                renderPivotPreviewTable(resData.data, t.config_json);
                previewSubtitle.textContent = "Grouped pivot preview (row groups configured).";
              } else {
                activePreviewData = resData.data;
                renderPreviewTable(activePreviewData);
                previewSubtitle.textContent = `Aggregated metrics from ${activePreviewData.length} records.`;
              }
              previewActions.classList.remove("hidden");
              previewExportBtn.setAttribute("href", `/module/RPTBLD/api/templates/${templateId}/export`);
            });
        })
        .catch(err => {
          console.error(err);
          previewLoadingState.classList.add("hidden");
          previewSubtitle.textContent = "Connection error.";
          previewEmptyState.classList.remove("hidden");
          showFeedback("Failed to connect to server.", "error");
        });
    });
  });

  // Render Table helper (flat mode). Parameterized with optional target
  // elements so the wizard's Review step can reuse the exact same rendering
  // logic against its own containers -- defaults to the main preview pane's
  // elements for the existing "Preview" button call site, unchanged.
  function renderPreviewTable(records, wrapperEl, tbodyEl) {
    wrapperEl = wrapperEl || previewTableWrapper;
    tbodyEl = tbodyEl || previewTbody;

    tbodyEl.innerHTML = "";
    if (records.length === 0) {
      tbodyEl.innerHTML = `
        <tr>
          <td colspan="7" class="py-10 text-center text-slate-500 font-medium">
            No approved submission data matching template criteria was found.
          </td>
        </tr>
      `;
      wrapperEl.classList.remove("hidden");
      return;
    }

    records.forEach(r => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50 transition-colors border-b border-slate-100";

      let displayValue = r.value;
      let alignClass = "text-left";
      if (typeof displayValue === "number") {
        displayValue = displayValue.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 });
        alignClass = "text-right font-mono font-semibold text-slate-900";
      }

      tr.innerHTML = `
        <td class="py-3 pr-3 whitespace-nowrap font-medium text-slate-800">${r.period_label}</td>
        <td class="py-3 pr-3">${r.site_name}</td>
        <td class="py-3 pr-3">${r.form_name}</td>
        <td class="py-3 pr-3"><code class="text-xs bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded font-mono">${r.field_code}</code></td>
        <td class="py-3 pr-3 text-slate-700">${r.field_name}</td>
        <td class="py-3 pr-3 ${alignClass}">${displayValue === null ? "—" : displayValue}</td>
        <td class="py-3 pl-3 text-slate-500">${r.unit || "—"}</td>
      `;
      tbodyEl.appendChild(tr);
    });

    wrapperEl.classList.remove("hidden");
  }

  // Render Table helper (pivot mode): per-site rows, a bold subtotal row per
  // group, a bold grand-total row. Amber background on any sourced-metric
  // cell whose verified flag is false, or an override computed-cell whose
  // verified flag is false -- matches the bg-amber-* "needs attention"
  // convention already used elsewhere in this app (workbook_sheet.js,
  // package_review.js). null renders as an em dash; a computed cell with a
  // non-null error renders that error text in rose/red, not blank.
  // Parameterized the same way as renderPreviewTable() above, for the same
  // reason (Review step reuse).
  function renderPivotPreviewTable(pivotData, config, wrapperEl, theadEl, tbodyEl) {
    wrapperEl = wrapperEl || previewPivotWrapper;
    theadEl = theadEl || previewPivotThead;
    tbodyEl = tbodyEl || previewPivotTbody;

    const metricAliases = (config && config.metric_aliases) || {};
    const metricKeys = canonicalMetrics.filter(k => metricAliases[k] && metricAliases[k].length);
    const computedColumns = (config && config.computed_columns) || [];
    const computedLabels = {};
    computedColumns.forEach(c => { computedLabels[c.id] = c.label || c.id; });
    const computedIds = computedColumns.map(c => c.id);

    theadEl.innerHTML = `
      <tr class="border-b border-slate-200 text-xs font-bold uppercase text-slate-500">
        <th class="pb-3 pr-3">Group</th>
        <th class="pb-3 pr-3">Site</th>
        ${metricKeys.map(k => `<th class="pb-3 pr-3 text-right">${escapeHtml(metricDisplayLabel(k))}</th>`).join("")}
        ${computedIds.map(id => `<th class="pb-3 pr-3 text-right">${escapeHtml(computedLabels[id] || id)}</th>`).join("")}
      </tr>
    `;

    function formatValue(v) {
      if (v === null || v === undefined) return `<span class="text-slate-300">—</span>`;
      if (typeof v === "number") return v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 });
      return escapeHtml(String(v));
    }

    function metricCellHtml(cellInfo) {
      if (!cellInfo) return `<td class="py-2.5 pr-3 text-right">—</td>`;
      const amberClass = cellInfo.verified === false ? "bg-amber-50" : "";
      return `<td class="py-2.5 pr-3 text-right ${amberClass}">${formatValue(cellInfo.value)}</td>`;
    }

    function computedCellHtml(cellInfo) {
      if (!cellInfo) return `<td class="py-2.5 pr-3 text-right">—</td>`;
      if (cellInfo.error) {
        return `<td class="py-2.5 pr-3 text-right text-rose-600 text-[11px] font-semibold">${escapeHtml(cellInfo.error)}</td>`;
      }
      const amberClass = (cellInfo.source === "override" && cellInfo.verified === false) ? "bg-amber-50" : "";
      return `<td class="py-2.5 pr-3 text-right ${amberClass}">${formatValue(cellInfo.value)}</td>`;
    }

    const rowsHtml = [];

    (pivotData.row_groups || []).forEach(group => {
      group.site_rows.forEach(row => {
        rowsHtml.push(`
          <tr class="hover:bg-slate-50 transition-colors border-b border-slate-100">
            <td class="py-2.5 pr-3 text-slate-500">${escapeHtml(group.label || group.id)}</td>
            <td class="py-2.5 pr-3 font-medium text-slate-800">${escapeHtml(row.site_name || "")}</td>
            ${metricKeys.map(k => metricCellHtml(row.metrics[k])).join("")}
            ${computedIds.map(id => computedCellHtml(row.computed[id])).join("")}
          </tr>
        `);
      });

      const subtotal = group.subtotal;
      rowsHtml.push(`
        <tr class="bg-slate-50 border-b border-slate-200 font-bold text-slate-800">
          <td class="py-2.5 pr-3" colspan="2">${escapeHtml(group.label || group.id)} — ${escapeHtml(subtotal.label || "Subtotal")}</td>
          ${metricKeys.map(k => `<td class="py-2.5 pr-3 text-right">${formatValue(subtotal.metrics[k])}</td>`).join("")}
          ${computedIds.map(id => computedCellHtml(subtotal.computed[id])).join("")}
        </tr>
      `);
    });

    rowsHtml.push(`
      <tr class="bg-slate-900 text-white font-bold">
        <td class="py-3 pr-3" colspan="2">Grand Total</td>
        ${metricKeys.map(k => `<td class="py-3 pr-3 text-right">${formatValue(pivotData.grand_total.metrics[k])}</td>`).join("")}
        ${computedIds.map(id => computedCellHtml(pivotData.grand_total.computed[id])).join("")}
      </tr>
    `);

    tbodyEl.innerHTML = rowsHtml.join("");
    wrapperEl.classList.remove("hidden");
  }

  // Step 7 (Review): the actual live result for currentTemplateId, fetched
  // fresh every time this step is entered (every prior step's Continue
  // already saved, so this always reflects the latest state).
  async function loadReviewPreview() {
    if (!currentTemplateId) return;

    reviewLoadingState.classList.remove("hidden");
    reviewPreviewTableWrapper.classList.add("hidden");
    reviewPreviewPivotWrapper.classList.add("hidden");

    const isPivot = !!(existingConfigJson && existingConfigJson.row_groups && existingConfigJson.row_groups.length);
    const endpoint = isPivot
      ? `/module/RPTBLD/api/templates/${currentTemplateId}/pivot-preview`
      : `/module/RPTBLD/api/templates/${currentTemplateId}/preview`;

    try {
      const res = await fetch(endpoint);
      const resData = await res.json();
      reviewLoadingState.classList.add("hidden");
      if (resData.status !== "success") {
        showFeedback(resData.message || "Failed to load review preview.", "error");
        return;
      }
      if (isPivot) {
        await loadCanonicalMetrics();
        renderPivotPreviewTable(
          resData.data, existingConfigJson,
          reviewPreviewPivotWrapper, reviewPreviewPivotThead, reviewPreviewPivotTbody,
        );
      } else {
        renderPreviewTable(resData.data, reviewPreviewTableWrapper, reviewPreviewTbody);
      }
    } catch (err) {
      console.error(err);
      reviewLoadingState.classList.add("hidden");
      showFeedback("Failed to load review preview.", "error");
    }
  }

  // Live Table Search Filter (flat mode only -- a no-op while a pivot preview is showing)
  if (previewSearch) {
    previewSearch.addEventListener("input", function () {
      if (!activePreviewData) return;
      const query = this.value.toLowerCase().trim();
      if (!query) {
        renderPreviewTable(activePreviewData);
        return;
      }

      const filtered = activePreviewData.filter(r => {
        return (
          r.period_label.toLowerCase().includes(query) ||
          r.site_name.toLowerCase().includes(query) ||
          r.form_name.toLowerCase().includes(query) ||
          r.field_code.toLowerCase().includes(query) ||
          r.field_name.toLowerCase().includes(query) ||
          (r.unit && r.unit.toLowerCase().includes(query)) ||
          (r.value !== null && String(r.value).toLowerCase().includes(query))
        );
      });
      renderPreviewTable(filtered);
    });
  }

  maybeAutoOpenEditDrawer();

})();
