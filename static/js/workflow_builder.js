document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const wkbkContext = urlParams.get("context") === "workbook";
  const wkbkId = urlParams.get("workbook_id");
  const editWorkflowId = urlParams.get("edit");

  const listView = document.getElementById("list-view");
  const editorView = document.getElementById("editor-view");
  const workflowsListBody = document.getElementById("workflows-list-body");

  const dfName = document.getElementById("df-name");
  const dfCode = document.getElementById("df-code");
  const dfForm = document.getElementById("df-form");
  const editorTitle = document.getElementById("editor-title");
  const editorVersionBadge = document.getElementById("editor-version-badge");
  const saveState = document.getElementById("save-state");
  const headerFormName = document.getElementById("header-form-name");
  const headerSitesCount = document.getElementById("header-sites-count");
  const headerLevelsCount = document.getElementById("header-levels-count");
  const aboutPathName = document.getElementById("about-path-name");
  const aboutPathCode = document.getElementById("about-path-code");
  const btnEditorBack = document.getElementById("btn-editor-back");
  const readySitesCount = document.getElementById("ready-sites-count");
  const readinessSummary = document.getElementById("readiness-summary");
  const readinessSiteList = document.getElementById("readiness-site-list");
  const siteSummaryList = document.getElementById("site-summary-list");
  const coveredSitesCount = document.getElementById("covered-sites-count");
  const coveredSitesList = document.getElementById("covered-sites-list");
  const levelsContainer = document.getElementById("levels-container");
  const btnAddLevel = document.getElementById("btn-add-level");
  const btnSaveDraft = document.getElementById("btn-save-draft");
  const btnScrollPreview = document.getElementById("btn-scroll-preview");
  const versionActions = document.getElementById("version-actions");
  const previewSiteSelect = document.getElementById("preview-site-select");
  const previewPathOutput = document.getElementById("preview-path-output");

  const modalCreateWorkflow = document.getElementById("modal-create-workflow");
  const btnCloseWorkflowModal = document.getElementById("btn-close-workflow-modal");
  const btnCancelWorkflowModal = document.getElementById("btn-cancel-workflow-modal");
  const formCreateWorkflow = document.getElementById("form-create-workflow");

  const modalPublishReview = document.getElementById("modal-publish-review");
  const btnClosePublishModal = document.getElementById("btn-close-publish-modal");
  const btnCancelPublishModal = document.getElementById("btn-cancel-publish-modal");
  const btnConfirmPublish = document.getElementById("btn-confirm-publish");
  const publishReviewBody = document.getElementById("publish-review-body");

  let workflows = [];
  let currentWorkflowId = null;
  let currentVersionId = null;
  let currentVersion = null;
  let currentWorkflow = null;
  let levelsList = [];
  let availableUsers = [];
  let availableSites = [];
  let availableForms = [];
  let linkedForms = [];
  let selectedFormId = null;
  let selectedSiteIds = [];
  let permissions = {
    can_edit: false,
    can_publish: false,
    can_create_version: false
  };
  let hasUnsavedChanges = false;
  let lastValidation = null;
  let didAutoOpenContextWorkflow = false;

  const approvalModes = [
    { value: "ANY_ONE", label: "Any one reviewer can approve" },
    { value: "SEQUENTIAL", label: "Reviewers approve in order" }
  ];

  if (wkbkContext && wkbkId && btnEditorBack) {
    btnEditorBack.textContent = "← Back to Workbook";
    btnEditorBack.onclick = () => {
      if (hasUnsavedChanges && !confirm("You have unsaved changes. Discard and return to workbook?")) return;
      window.location.href = `/workbooks/${encodeURIComponent(wkbkId)}`;
    };
  }

  const escapeHtml = window.UIHelpers.escapeHtml;
  const showToast = window.UIHelpers.showToast;

  function setUnsaved(value) {
    hasUnsavedChanges = value;
    if (!saveState) return;
    saveState.textContent = value ? "Unsaved changes" : "Saved";
    saveState.className = value
      ? "rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-semibold text-amber-700"
      : "rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-500";
  }

  function getSite(siteId) {
    return availableSites.find(site => parseInt(site.id) === parseInt(siteId));
  }

  function getSiteName(siteId) {
    const site = getSite(siteId);
    return site ? site.name : `Site ${siteId}`;
  }

  function getLinkedSiteIds() {
    const ids = new Set();
    linkedForms.forEach(form => {
      (form.site_ids || []).forEach(siteId => {
        const parsed = parseInt(siteId);
        if (getSite(parsed)) ids.add(parsed);
      });
    });
    return Array.from(ids);
  }

  function getCoveredSites() {
    const ids = selectedFormId ? selectedSiteIds : getLinkedSiteIds();
    return ids
      .map(siteId => getSite(siteId))
      .filter(Boolean)
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  function getRoutingSites() {
    return getCoveredSites();
  }

  function getLinkedFormLabel() {
    const selectedForm = availableForms.find(form => parseInt(form.id) === parseInt(selectedFormId));
    if (selectedForm) return selectedForm.name;
    if (!linkedForms.length) return "Not linked";
    if (linkedForms.length === 1) return linkedForms[0].name;
    return `${linkedForms[0].name} +${linkedForms.length - 1} more`;
  }

  function isFinalLevel(index) {
    const level = levelsList[index];
    return Boolean(level && level.level_type === "final");
  }

  function finalApprovalIndex() {
    return levelsList.findIndex(level => level.level_type === "final");
  }

  function isGenericLevelName(value) {
    return !value || /^Level \d+$/.test(value) || /^Approval Level \d+$/.test(value) || /^Review Step \d+$/.test(value) || value === "Final Approval";
  }

  function normalizeLevelOrder() {
    if (!levelsList.length) return;
    const finalIndexes = levelsList
      .map((level, index) => level.level_type === "final" ? index : -1)
      .filter(index => index >= 0);
    if (finalIndexes.length > 1) {
      const keepIndex = finalIndexes[finalIndexes.length - 1];
      levelsList.forEach((level, index) => {
        if (level.level_type === "final" && index !== keepIndex) {
          level.level_type = "regular";
          if (level.level_name === "Final Approval") level.level_name = "";
        }
      });
    }
    const finalIndex = finalApprovalIndex();
    if (finalIndex >= 0 && finalIndex !== levelsList.length - 1) {
      const [finalLevel] = levelsList.splice(finalIndex, 1);
      levelsList.push(finalLevel);
    }
  }

  function ensureGenericLevelNames() {
    normalizeLevelOrder();
    let regularCount = 0;
    levelsList.forEach((level, index) => {
      if (!level.level_type) {
        level.level_type = level.level_name === "Final Approval" ? "final" : "regular";
      }
      const currentName = level.level_name || "";
      if (level.level_type === "final") {
        level.level_name = "Final Approval";
        level.skip_if_empty = false;
      } else {
        regularCount += 1;
        if (isGenericLevelName(currentName)) {
          level.level_name = `Review Step ${regularCount}`;
        }
      }
      level.level_number = index + 1;
    });
  }

  function getAssignmentMode(level) {
    if (level.assignment_mode) return level.assignment_mode;
    return (level.approvers || []).some(app => app.scope_site_id) ? "site" : "same";
  }

  function approvalModeOptions(selectedValue) {
    const modes = [...approvalModes];
    if (selectedValue && !modes.some(mode => mode.value === selectedValue)) {
      modes.push({ value: selectedValue, label: selectedValue.replaceAll("_", " ") });
    }
    return modes.map(mode => (
      `<option value="${mode.value}" ${selectedValue === mode.value ? "selected" : ""}>${escapeHtml(mode.label)}</option>`
    )).join("");
  }

  function getEligibleApprovers(level, siteId) {
    return (level.approvers || []).filter(app => (
      !app.scope_site_id || parseInt(app.scope_site_id) === parseInt(siteId)
    ));
  }

  function buildSitePath(site) {
    const rows = [];
    let blocked = false;
    let approvalsCount = 0;
    let skippedCount = 0;
    const issues = [];

    if (!levelsList.length) {
      blocked = true;
      issues.push("Add at least one review step.");
    }

    levelsList.forEach((level, index) => {
      if (blocked) return;
      const final = isFinalLevel(index);
      const eligible = getEligibleApprovers(level, site.id);

      if (eligible.length) {
        approvalsCount += 1;
        rows.push({
          level,
          status: "active",
          approvers: eligible,
          message: final ? "Final approval locks the workbook package and releases data for reporting." : "Workbook package waits here for review."
        });
        return;
      }

      if (!final && level.skip_if_empty) {
        skippedCount += 1;
        rows.push({
          level,
          status: "skipped",
          approvers: [],
          message: "This step will be skipped because no reviewer exists for this site."
        });
        return;
      }

      blocked = true;
      issues.push(final
        ? `${level.level_name} needs an eligible final reviewer for ${site.name}.`
        : `${level.level_name} needs an eligible reviewer for ${site.name}, or must be marked skippable.`
      );
      rows.push({
        level,
        status: final ? "blocked" : "attention",
        approvers: [],
        message: final
          ? "Final Approval is mandatory and cannot be skipped."
          : "This site cannot submit through this path until this step is fixed."
      });
    });

    const status = blocked ? "Blocked" : (issues.length ? "Needs attention" : "Ready");
    return { site, rows, approvalsCount, skippedCount, issues, status, blocked };
  }

  function validateWorkflow() {
    const coveredSites = getCoveredSites();
    const paths = coveredSites.map(site => buildSitePath(site));
    const issues = [];
    let setupState = "ready";
    const finalIndex = finalApprovalIndex();

    if (!selectedFormId) {
      setupState = "no_form";
      issues.push("Choose the workbook this approval path applies to before publishing.");
    } else if (!coveredSites.length) {
      setupState = "no_sites";
      issues.push("Choose at least one site before publishing this approval path.");
    }
    if (!levelsList.length) {
      issues.push("Add at least one review step.");
    }

    if (levelsList.length && finalIndex === -1) {
      issues.push("Final approval step is missing.");
    }
    if (finalIndex >= 0 && finalIndex !== levelsList.length - 1) {
      issues.push("Final approval must be the last review step.");
    }

    paths.forEach(path => {
      path.issues.forEach(issue => issues.push(issue));
      if (finalIndex >= 0) {
        const finalLevel = levelsList[levelsList.length - 1];
        if (!finalLevel || finalLevel.level_type !== "final") {
          return;
        }
        const finalApprovers = getEligibleApprovers(finalLevel, path.site.id);
        if (!finalApprovers.length) {
          issues.push(`${path.site.name} - Final approval needs a reviewer.`);
        }
      }
    });

    return {
      coveredSites,
      paths,
      issues: Array.from(new Set(issues)),
      readyCount: paths.filter(path => path.status === "Ready").length,
      blockedCount: paths.filter(path => path.status === "Blocked").length,
      canPublish: issues.length === 0 && paths.length > 0,
      setupState
    };
  }

  function renderHeader() {
    headerFormName.textContent = getLinkedFormLabel();
    headerSitesCount.textContent = String(getCoveredSites().length);
    headerLevelsCount.textContent = String(levelsList.length);
    if (aboutPathName) aboutPathName.textContent = currentWorkflow ? currentWorkflow.name : "Not selected";
    if (aboutPathCode) aboutPathCode.textContent = currentWorkflow ? currentWorkflow.code : "—";
  }

  function renderSetupControls() {
    dfForm.innerHTML = '<option value="">Choose form</option>';
    availableForms.forEach(form => {
      const option = document.createElement("option");
      option.value = form.id;
      option.textContent = `${form.name} (${form.code})`;
      if (parseInt(form.id) === parseInt(selectedFormId)) {
        option.selected = true;
      }
      dfForm.appendChild(option);
    });
    dfForm.disabled = !permissions.can_edit;

    coveredSitesCount.textContent = `${selectedSiteIds.length} selected`;
    coveredSitesList.innerHTML = "";
    if (!selectedFormId) {
      coveredSitesList.innerHTML = `
        <div class="sm:col-span-2 rounded-lg border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500">
          Site scope is configured on the workbook detail page.
        </div>
      `;
      return;
    }
    if (!availableSites.length) {
      coveredSitesList.innerHTML = `
        <div class="sm:col-span-2 rounded-lg border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500">
          No active sites are available.
        </div>
      `;
      return;
    }

    availableSites.forEach(site => {
      const label = document.createElement("label");
      label.className = "flex items-start gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm hover:bg-slate-50";
      label.innerHTML = `
        <input type="checkbox" class="covered-site-checkbox mt-1 rounded border-slate-300 text-indigo-600" value="${site.id}" ${selectedSiteIds.includes(parseInt(site.id)) ? "checked" : ""} ${!permissions.can_edit ? "disabled" : ""}>
        <span class="min-w-0">
          <span class="block truncate font-semibold text-slate-800">${escapeHtml(site.name)}</span>
          <span class="block truncate text-xs text-slate-400">${escapeHtml(site.code || "")}</span>
        </span>
      `;
      coveredSitesList.appendChild(label);
    });

    coveredSitesList.querySelectorAll(".covered-site-checkbox").forEach(input => {
      input.addEventListener("change", () => {
        const siteId = parseInt(input.value);
        if (input.checked && !selectedSiteIds.includes(siteId)) {
          selectedSiteIds.push(siteId);
        } else if (!input.checked) {
          selectedSiteIds = selectedSiteIds.filter(id => id !== siteId);
        }
        selectedSiteIds.sort((a, b) => a - b);
        setUnsaved(true);
        renderWorkspace();
      });
    });
  }

  function renderVersionBadge() {
    const published = currentVersion && currentVersion.status === "Published";
    editorVersionBadge.textContent = published
      ? `Live: V${currentVersion.version_number}`
      : `Draft: V${currentVersion ? currentVersion.version_number : 1}`;
    editorVersionBadge.className = published
      ? "rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-bold uppercase text-emerald-800"
      : "rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-bold uppercase text-amber-800";
  }

  function renderReadiness() {
    lastValidation = validateWorkflow();
    const total = lastValidation.paths.length;
    readySitesCount.textContent = `${lastValidation.readyCount}/${total || 0} ready`;

    if (lastValidation.setupState === "no_form") {
      readinessSummary.innerHTML = `
        <div class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600">
          Choose the workbook this approval path applies to.
        </div>
      `;
    } else if (lastValidation.setupState === "no_sites") {
      readinessSummary.innerHTML = `
        <div class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600">
          Choose the sites this approval path should cover.
        </div>
      `;
    } else if (lastValidation.canPublish) {
      readinessSummary.innerHTML = `
        <div class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">
          All selected sites have a valid approval path.
        </div>
      `;
    } else {
      readinessSummary.innerHTML = `
        <div class="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-800">
          ${lastValidation.issues.length} issue${lastValidation.issues.length === 1 ? "" : "s"} must be fixed before publishing.
        </div>
      `;
    }

    readinessSiteList.innerHTML = "";
    lastValidation.paths.forEach(path => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "grid w-full gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-left text-xs hover:bg-slate-50";
      const dotClass = path.status === "Ready" ? "bg-emerald-500" : path.status === "Blocked" ? "bg-rose-500" : "bg-amber-500";
      button.innerHTML = `
        <span class="flex items-start justify-between gap-3">
          <span class="flex min-w-0 items-center gap-2">
            <span class="mt-0.5 h-2 w-2 shrink-0 rounded-full ${dotClass}"></span>
            <span class="font-semibold text-slate-700">${escapeHtml(path.site.name)}</span>
          </span>
          <span class="shrink-0 text-[10px] font-bold uppercase text-slate-400">${path.status}</span>
        </span>
        ${path.issues[0] ? `<span class="block pl-4 text-[11px] leading-4 text-slate-500">${escapeHtml(path.issues[0])}</span>` : ""}
      `;
      button.onclick = () => {
        previewSiteSelect.value = path.site.id;
        renderPreviewPath();
        document.getElementById("preview-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      };
      readinessSiteList.appendChild(button);
    });
  }

  function renderSiteSummary() {
    const validation = lastValidation || validateWorkflow();
    siteSummaryList.innerHTML = "";

    if (!validation.paths.length) {
      siteSummaryList.innerHTML = '<p class="text-xs italic text-slate-400">No sites to summarize.</p>';
      return;
    }

    validation.paths.forEach(path => {
      const statusClass = path.status === "Ready"
        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
        : path.status === "Blocked"
          ? "bg-rose-50 text-rose-700 border-rose-200"
          : "bg-amber-50 text-amber-700 border-amber-200";
      const item = document.createElement("div");
      item.className = "rounded-lg border border-slate-200 px-3 py-2.5 text-xs";
      item.innerHTML = `
        <div class="flex items-center justify-between gap-2">
          <span class="truncate font-semibold text-slate-800">${escapeHtml(path.site.name)}</span>
          <span class="rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${statusClass}">${path.status}</span>
        </div>
        <div class="mt-1 text-[11px] leading-4 text-slate-500">
          ${path.approvalsCount} review step${path.approvalsCount === 1 ? "" : "s"} · ${path.skippedCount} skipped
        </div>
      `;
      siteSummaryList.appendChild(item);
    });
  }

  function renderPreviewSelector() {
    const previousValue = previewSiteSelect.value;
    const sites = selectedFormId ? getCoveredSites() : [];

    previewSiteSelect.innerHTML = '<option value="">Choose site</option>';
    sites.forEach(site => {
      const option = document.createElement("option");
      option.value = site.id;
      option.textContent = site.name;
      previewSiteSelect.appendChild(option);
    });

    if (previousValue && sites.some(site => parseInt(site.id) === parseInt(previousValue))) {
      previewSiteSelect.value = previousValue;
    } else if (sites.length) {
      previewSiteSelect.value = sites[0].id;
    }
  }

  function renderPreviewPath() {
    if (!selectedFormId) {
      previewPathOutput.innerHTML = `
        <div class="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
          Assign this path from a workbook detail page to preview it by site.
        </div>
      `;
      return;
    }

    if (!getCoveredSites().length) {
      previewPathOutput.innerHTML = `
        <div class="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
          Configure site scope from the workbook detail page to preview this path.
        </div>
      `;
      return;
    }

    const siteId = parseInt(previewSiteSelect.value);
    if (!siteId) {
      previewPathOutput.innerHTML = '<p class="text-sm italic text-slate-400">Choose a site to preview the approval path.</p>';
      return;
    }

    const site = getSite(siteId);
    if (!site) {
      previewPathOutput.innerHTML = '<p class="text-sm italic text-slate-400">Selected site is unavailable.</p>';
      return;
    }

    const path = buildSitePath(site);
    const rows = [];
    rows.push(`
      <li class="flex gap-3">
        <span class="mt-1 h-2.5 w-2.5 rounded-full bg-slate-400"></span>
        <div>
          <div class="text-sm font-semibold text-slate-800">On submission</div>
          <div class="text-xs text-slate-500">Package enters review.</div>
        </div>
      </li>
    `);

    path.rows.forEach(row => {
      const borderClass = row.status === "active"
        ? "border-emerald-200 bg-emerald-50"
        : row.status === "skipped"
          ? "border-slate-200 bg-slate-50"
          : "border-rose-200 bg-rose-50";
      const dotClass = row.status === "active"
        ? "bg-emerald-500"
        : row.status === "skipped"
          ? "bg-slate-300"
          : "bg-rose-500";
      const approverText = row.approvers.length
        ? row.approvers.map(app => `${escapeHtml(app.full_name)} <span class="text-slate-400">(${app.scope_site_id ? `${escapeHtml(getSiteName(app.scope_site_id))} only` : "All sites"})</span>`).join("<br>")
        : escapeHtml(row.message);
      const stepTitle = isFinalLevel(levelsList.indexOf(row.level)) ? "Final Approval" : `Step ${row.level.level_number}`;

      rows.push(`
        <li class="flex gap-3">
          <span class="mt-3 h-2.5 w-2.5 rounded-full ${dotClass}"></span>
          <div class="min-w-0 flex-1 rounded-lg border px-3 py-2 ${borderClass}">
            <div class="text-[10px] font-bold uppercase tracking-wider text-slate-500">${stepTitle}</div>
            <div class="text-sm font-semibold text-slate-800">${escapeHtml(row.level.level_name)}</div>
            <div class="mt-1 text-xs text-slate-600">${approverText}</div>
          </div>
        </li>
      `);
    });

    if (!path.blocked && finalApprovalIndex() >= 0) {
      rows.push(`
        <li class="flex gap-3">
          <span class="mt-1 h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
          <div>
            <div class="text-sm font-semibold text-slate-800">Approved & locked — data released for reporting</div>
            <div class="text-xs text-slate-500">Final approval locks the workbook package for this site.</div>
          </div>
        </li>
      `);
    }

    const pathParts = ["On submission"].concat(path.rows.map(row => (
      row.status === "skipped" ? `${row.level.level_name} (skipped if empty)` : row.level.level_name
    )));
    if (!path.blocked && finalApprovalIndex() >= 0) {
      pathParts.push("Approved & locked");
    }
    const warnings = [];
    path.rows.forEach(row => {
      if (row.status === "skipped") {
        warnings.push(`${row.level.level_name} will be skipped because no reviewer exists for ${site.name}.`);
      }
      if (row.status === "blocked" || row.status === "attention") {
        warnings.push(`${row.level.level_name} would block submission for ${site.name}.`);
      }
    });

    previewPathOutput.innerHTML = `
      <div class="mb-3 rounded-lg border ${path.blocked ? "border-rose-200 bg-rose-50 text-rose-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"} px-3 py-2 text-xs font-semibold">
        ${path.blocked ? "This site would block during submission." : "This site has a valid approval path."}
      </div>
      <div class="mb-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
        ${pathParts.join(" -> ")}
      </div>
      ${warnings.length ? `
        <div class="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          ${warnings.map(warning => `<div>${escapeHtml(warning)}</div>`).join("")}
        </div>
      ` : ""}
      <ol class="space-y-3">${rows.join("")}</ol>
    `;
  }

  function renderWorkspace() {
    ensureGenericLevelNames();
    const editable = permissions.can_edit;
    renderSetupControls();
    renderHeader();
    renderVersionBadge();

    levelsContainer.innerHTML = "";
    if (!levelsList.length) {
      levelsContainer.innerHTML = `
        <div class="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
          <div class="text-sm font-semibold text-slate-700">No review steps yet.</div>
          <div class="mt-1 text-xs text-slate-500">Add the first reviewer, then add a mandatory final approval step before publishing.</div>
        </div>
      `;
    } else {
      levelsList.forEach((level, index) => {
        levelsContainer.appendChild(renderLevelCard(level, index, editable));
      });
    }

    btnAddLevel.disabled = !editable;
    btnSaveDraft.disabled = !editable;
    renderPreviewSelector();
    renderReadiness();
    renderSiteSummary();
    renderVersionActions();
    renderPreviewPath();
  }

  function renderVersionActions() {
    versionActions.innerHTML = "";
    if (permissions.can_publish) {
      const publishButton = document.createElement("button");
      publishButton.type = "button";
      publishButton.className = "inline-flex h-9 items-center justify-center rounded-lg bg-emerald-50 px-3 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200 hover:bg-emerald-100";
      publishButton.textContent = (lastValidation && ["no_form", "no_sites"].includes(lastValidation.setupState))
        ? "Complete setup to publish"
        : (lastValidation && !lastValidation.canPublish)
          ? `Fix ${lastValidation.issues.length} issue${lastValidation.issues.length === 1 ? "" : "s"} to publish`
        : "Publish path";
      publishButton.onclick = openPublishReview;
      versionActions.appendChild(publishButton);
    }
    if (permissions.can_create_version) {
      const newVersionButton = document.createElement("button");
      newVersionButton.type = "button";
      newVersionButton.className = "inline-flex h-9 items-center justify-center rounded-lg bg-[#1a3a6b] px-3 text-xs font-semibold text-white hover:bg-[#142f57]";
      newVersionButton.textContent = "Edit path";
      newVersionButton.onclick = createNewVersionDraft;
      versionActions.appendChild(newVersionButton);
    }

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-rose-200 bg-white text-rose-600 hover:bg-rose-50";
    deleteButton.title = "Delete approval path";
    deleteButton.innerHTML = `
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
    `;
    deleteButton.onclick = deleteWorkflow;
    versionActions.appendChild(deleteButton);
  }

  function renderLevelCard(level, index, editable) {
    const final = isFinalLevel(index);
    const mode = getAssignmentMode(level);
    const stepLabel = final ? "Final Approval" : `Step ${level.level_number}`;
    const card = document.createElement("article");
    card.id = `workflow-level-${index}`;
    card.className = "rounded-xl border border-slate-200 bg-white p-6 shadow-sm";

    card.innerHTML = `
      <div class="flex flex-col gap-4 lg:flex-row lg:items-start">
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${final ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200" : "bg-[#e8eef7] text-[#1a3a6b] ring-1 ring-[#c8d6ea]"} text-sm font-bold">${final ? "✓" : level.level_number}</span>

        <div class="min-w-0 flex-1">
          <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div class="min-w-0 flex-1">
              <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400">${stepLabel}</div>
              <label class="mt-2 block text-[10px] font-bold uppercase tracking-wider text-slate-400">Step name</label>
              <input type="text" value="${escapeHtml(level.level_name)}" ${!editable ? "disabled" : ""}
                class="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-semibold text-slate-900 focus:border-indigo-500 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-500">
              <p class="mt-1 text-xs leading-5 text-slate-500">Shown in review queues, notifications, and preview paths.</p>
            </div>
            <div class="flex shrink-0 items-center gap-2 pt-5">
              <span class="rounded-full ${final ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200" : "bg-slate-50 text-slate-600 ring-1 ring-slate-200"} px-2.5 py-1 text-[10px] font-bold uppercase">
                ${final ? "Final approval" : "Review step"}
              </span>
              ${editable ? `<button type="button" class="delete-level rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100">Remove</button>` : ""}
            </div>
          </div>
        </div>
      </div>

      <div class="mt-5 rounded-xl border border-slate-200 bg-white p-5">
        <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div>
            <label class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Review rule</label>
            <select class="approval-mode mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm" ${!editable ? "disabled" : ""}>
              ${approvalModeOptions(level.approval_mode || "ANY_ONE")}
            </select>
            <p class="mt-2 text-xs leading-5 text-slate-500">This controls whether one reviewer is enough, or reviewers must approve in sequence.</p>
          </div>
          <div>
            <label class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Step type</label>
            <select class="level-type mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm" ${!editable ? "disabled" : ""}>
              <option value="regular" ${final ? "" : "selected"}>Review step</option>
              <option value="final" ${final ? "selected" : ""}>Final approval</option>
            </select>
            <p class="mt-2 text-xs leading-5 text-slate-500">${final ? "Final approval locks the workbook package and releases data for reporting." : "This step can be skipped if no reviewer exists for a site."}</p>
          </div>
        </div>
      </div>

      <div class="mt-5 rounded-xl border border-slate-200 bg-slate-50/70 p-5">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 class="text-sm font-semibold text-slate-800">${final ? "Who gives final approval?" : "Who reviews at this step?"}</h3>
            <p class="mt-1 text-xs text-slate-500">${mode === "same" ? "One reviewer applies to all selected sites." : "Each selected site can route to a different reviewer."}</p>
          </div>
          <div class="inline-flex rounded-lg border border-slate-200 bg-white p-1">
            <button type="button" data-mode="same" class="assignment-mode-button rounded-md px-3 py-1.5 text-xs font-semibold ${mode === "same" ? "bg-[#e8eef7] text-[#1a3a6b]" : "text-slate-500 hover:text-slate-800"}" ${!editable ? "disabled" : ""}>Same for every site</button>
            <button type="button" data-mode="site" class="assignment-mode-button rounded-md px-3 py-1.5 text-xs font-semibold ${mode === "site" ? "bg-[#e8eef7] text-[#1a3a6b]" : "text-slate-500 hover:text-slate-800"}" ${!editable ? "disabled" : ""}>Different per site</button>
          </div>
        </div>
        <div class="assignment-body mt-4"></div>
      </div>

      <div class="mt-4 rounded-lg border ${final ? "border-emerald-100 bg-emerald-50" : "border-indigo-100 bg-indigo-50"} px-4 py-3 text-xs leading-5">
        ${final
          ? '<span class="font-semibold text-emerald-800">Final approval is required.</span> <span class="text-emerald-700">This step locks the workbook package and releases it for reporting.</span>'
          : `<label class="inline-flex items-center gap-2 font-semibold text-slate-700">
              <input type="checkbox" class="skip-empty-checkbox rounded border-slate-300 text-indigo-600" ${level.skip_if_empty ? "checked" : ""} ${!editable ? "disabled" : ""}>
              Skip this step if no reviewer exists for this site
            </label>
            <p class="mt-1 text-slate-500">If no reviewer is assigned for a site, this step will block submission unless 'Skip if empty' is checked above.</p>`
        }
      </div>
    `;

    const nameInput = card.querySelector("input[type='text']");
    nameInput.addEventListener("change", () => {
      level.level_name = nameInput.value.trim() || (final ? "Final Approval" : `Review Step ${level.level_number}`);
      setUnsaved(true);
      renderWorkspace();
    });

    const approvalModeSelect = card.querySelector(".approval-mode");
    approvalModeSelect.addEventListener("change", () => {
      level.approval_mode = approvalModeSelect.value;
      if (level.approval_mode === "SEQUENTIAL") {
        level.approvers.forEach((app, appIndex) => app.sequence_number = appIndex + 1);
      } else {
        level.approvers.forEach(app => app.sequence_number = null);
      }
      setUnsaved(true);
      renderWorkspace();
    });

    const levelTypeSelect = card.querySelector(".level-type");
    levelTypeSelect.addEventListener("change", () => {
      if (levelTypeSelect.value === "final") {
        levelsList.forEach(item => {
          if (item !== level) item.level_type = "regular";
        });
        level.level_type = "final";
        level.level_name = "Final Approval";
        level.skip_if_empty = false;
        normalizeLevelOrder();
      } else {
        level.level_type = "regular";
        if (level.level_name === "Final Approval") {
          level.level_name = "";
        }
      }
      ensureGenericLevelNames();
      setUnsaved(true);
      renderWorkspace();
    });

    card.querySelectorAll(".assignment-mode-button").forEach(button => {
      button.addEventListener("click", () => {
        const nextMode = button.dataset.mode;
        const currentMode = getAssignmentMode(level);
        if (nextMode === currentMode) return;

        if (button.dataset.mode === "same") {
          level.assignment_mode = "same";
          const existingGlobal = (level.approvers || []).find(app => !app.scope_site_id);
          level.approvers = existingGlobal ? [{
            ...existingGlobal,
            scope_site_id: null,
            sequence_number: null
          }] : [];
        }
        if (button.dataset.mode === "site") {
          level.assignment_mode = "site";
          const existingScoped = (level.approvers || []).filter(app => app.scope_site_id);
          const existingGlobal = (level.approvers || []).find(app => !app.scope_site_id);
          if (existingScoped.length) {
            level.approvers = existingScoped;
          } else if (existingGlobal) {
            level.approvers = getCoveredSites().map(site => ({
              ...existingGlobal,
              scope_site_id: site.id,
              sequence_number: null
            }));
          } else {
            level.approvers = [];
          }
        }
        setUnsaved(true);
        renderWorkspace();
      });
    });

    const deleteButton = card.querySelector(".delete-level");
    if (deleteButton) {
      deleteButton.addEventListener("click", () => {
        levelsList.splice(index, 1);
        levelsList.forEach((item, idx) => item.level_number = idx + 1);
        ensureGenericLevelNames();
        setUnsaved(true);
        renderWorkspace();
      });
    }

    const skipInput = card.querySelector(".skip-empty-checkbox");
    if (skipInput) {
      skipInput.addEventListener("change", () => {
        level.skip_if_empty = skipInput.checked;
        setUnsaved(true);
        renderWorkspace();
      });
    }

    const body = card.querySelector(".assignment-body");
    if (mode === "same") {
      renderSameSiteAssignment(body, level, editable);
    } else {
      renderPerSiteAssignment(body, level, editable, final);
    }

    return card;
  }

  function renderSameSiteAssignment(container, level, editable) {
    const allSiteApprover = (level.approvers || []).find(app => !app.scope_site_id);
    container.innerHTML = `
      <div class="rounded-xl border border-slate-200 bg-white p-5">
        <label class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Reviewer</label>
        <select class="all-site-approver mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm" ${!editable ? "disabled" : ""}>
          <option value="">Choose reviewer</option>
          ${availableUsers.map(user => `<option value="${user.id}" ${allSiteApprover && parseInt(allSiteApprover.user_id) === parseInt(user.id) ? "selected" : ""}>${escapeHtml(user.full_name)} (${escapeHtml(user.email)})</option>`).join("")}
        </select>
        <div class="mt-3 inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-600">All sites</div>
      </div>
    `;

    container.querySelector(".all-site-approver").addEventListener("change", (event) => {
      const userId = parseInt(event.target.value);
      level.assignment_mode = "same";
      level.approvers = (level.approvers || []).filter(app => app.scope_site_id);
      if (userId) {
        const user = availableUsers.find(item => parseInt(item.id) === userId);
        level.approvers.unshift({
          user_id: user.id,
          full_name: user.full_name,
          email: user.email,
          scope_site_id: null,
          sequence_number: null
        });
      }
      setUnsaved(true);
      renderWorkspace();
    });
  }

  function renderPerSiteAssignment(container, level, editable, final) {
    const sites = getRoutingSites();
    if (!sites.length) {
      container.innerHTML = `
        <div class="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-500">
          No sites are available for routing yet.
        </div>
      `;
      return;
    }

    container.innerHTML = '<div class="space-y-3"></div>';
    const rowsContainer = container.querySelector("div");
    sites.forEach(site => {
      const assignment = (level.approvers || []).find(app => parseInt(app.scope_site_id) === parseInt(site.id));
      const eligible = getEligibleApprovers(level, site.id);
      const status = eligible.length
        ? { label: "Set", className: "bg-emerald-50 text-emerald-700 border-emerald-200" }
        : (!final && level.skip_if_empty)
          ? { label: "Will skip", className: "bg-slate-50 text-slate-600 border-slate-200" }
          : { label: "Needs reviewer", className: "bg-rose-50 text-rose-700 border-rose-200" };
      const row = document.createElement("div");
      row.className = "rounded-xl border border-slate-200 bg-white p-4";
      row.innerHTML = `
        <div class="grid gap-4 xl:grid-cols-[minmax(180px,1fr)_minmax(260px,420px)_132px] xl:items-center">
          <div class="min-w-0">
            <div class="truncate font-semibold text-slate-800">${escapeHtml(site.name)}</div>
            <div class="mt-1 text-xs text-slate-400">${escapeHtml(site.code || "")}</div>
          </div>
          <div>
            <select class="site-approver block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm" data-site-id="${site.id}" ${!editable ? "disabled" : ""}>
            <option value="">Choose reviewer</option>
            ${availableUsers.map(user => `<option value="${user.id}" ${assignment && parseInt(assignment.user_id) === parseInt(user.id) ? "selected" : ""}>${escapeHtml(user.full_name)} (${escapeHtml(user.email)})</option>`).join("")}
            </select>
            ${!eligible.length && !final && level.skip_if_empty ? '<p class="mt-1 text-xs text-slate-500">If no reviewer exists for this site, this step will be skipped.</p>' : ""}
          </div>
          <div class="flex justify-start xl:justify-self-end">
            <span class="inline-flex min-w-[112px] justify-center whitespace-nowrap rounded-full border px-3 py-1 text-xs font-semibold ${status.className}">${status.label}</span>
          </div>
        </div>
      `;
      rowsContainer.appendChild(row);
    });

    rowsContainer.querySelectorAll(".site-approver").forEach(select => {
      select.addEventListener("change", (event) => {
        const siteId = parseInt(event.target.dataset.siteId);
        const userId = parseInt(event.target.value);
        level.assignment_mode = "site";
        level.approvers = (level.approvers || []).filter(app => parseInt(app.scope_site_id) !== siteId);
        if (userId) {
          const user = availableUsers.find(item => parseInt(item.id) === userId);
          level.approvers.push({
            user_id: user.id,
            full_name: user.full_name,
            email: user.email,
            scope_site_id: siteId,
            sequence_number: null
          });
        }
        setUnsaved(true);
        renderWorkspace();
      });
    });
  }

  async function loadWorkflows() {
    workflowsListBody.innerHTML = '<tr><td colspan="5" class="px-6 py-12 text-center text-slate-400 italic">Loading approval paths...</td></tr>';
    try {
      const res = await fetch("/module/WFLWBLD/api");
      const data = await res.json();
      workflows = data;
      workflowsListBody.innerHTML = "";

      if (!data.length) {
        workflowsListBody.innerHTML = `
          <tr>
            <td colspan="5" class="px-6 py-12 text-center text-slate-400 italic">
              No approval paths configured yet. Create a path to decide who reviews submitted workbook packages.
            </td>
          </tr>
        `;
        return;
      }

      data.forEach(item => {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-50/50 transition-colors";
        const status = item.latest_version_status || "Draft";
        const statusBadge = status === "Published"
          ? '<span class="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase text-emerald-800">Published</span>'
          : '<span class="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-800">Draft</span>';
        const action = item.latest_version_id
          ? `<button onclick="editWorkflow(${item.id}, ${item.latest_version_id})" class="font-bold text-[#1a3a6b] hover:text-[#c8102e] hover:underline">Edit path</button>`
          : "";
        tr.innerHTML = `
          <td class="px-6 py-4 font-bold text-slate-800">${escapeHtml(item.name)}</td>
          <td class="px-6 py-4 font-mono text-slate-500">${escapeHtml(item.code)}</td>
          <td class="px-6 py-4 font-bold text-slate-500">${item.levels_count || 0} step${item.levels_count === 1 ? "" : "s"}</td>
          <td class="px-6 py-4">${statusBadge}</td>
          <td class="px-6 py-4 text-right whitespace-nowrap">${action}</td>
        `;
        workflowsListBody.appendChild(tr);
      });

      if (!didAutoOpenContextWorkflow && wkbkContext && editWorkflowId) {
        didAutoOpenContextWorkflow = true;
        const workflowToOpen = data.find(item => parseInt(item.id) === parseInt(editWorkflowId));
        if (workflowToOpen && workflowToOpen.latest_version_id) {
          editWorkflow(workflowToOpen.id, workflowToOpen.latest_version_id);
        } else {
          showToast("Could not find the requested approval path.", "error");
        }
      }
    } catch (err) {
      console.error(err);
      showToast("Error loading approval paths.", "error");
    }
  }

  async function loadVersionDetails(versionId) {
    try {
      const res = await fetch(`/module/WFLWBLD/api/version/${versionId}`);
      if (!res.ok) throw new Error("Failed to load details");
      const data = await res.json();

      currentVersionId = versionId;
      currentVersion = data.version;
      currentWorkflow = data.workflow;
      levelsList = (data.levels || []).map(level => ({
        ...level,
        level_type: level.level_name === "Final Approval" ? "final" : "regular",
        assignment_mode: (level.approvers || []).some(app => app.scope_site_id) ? "site" : "same"
      }));
      availableUsers = data.available_users || [];
      availableSites = data.available_sites || [];
      availableForms = data.available_forms || [];
      linkedForms = data.linked_forms || [];
      permissions = data.permissions || {};
      selectedFormId = linkedForms.length ? linkedForms[0].id : null;
      selectedSiteIds = linkedForms.length ? (linkedForms[0].site_ids || []).map(siteId => parseInt(siteId)).filter(Boolean) : [];

      dfName.value = currentWorkflow.name;
      dfCode.value = currentWorkflow.code;
      editorTitle.textContent = currentWorkflow.name;
      setUnsaved(false);
      renderWorkspace();
    } catch (err) {
      console.error(err);
      showToast("Error loading approval path details.", "error");
    }
  }

  window.showList = function () {
    if (hasUnsavedChanges && !confirm("You have unsaved changes. Discard and return to list?")) return;
    editorView.classList.add("hidden");
    listView.classList.remove("hidden");
    loadWorkflows();
  };

  window.startNewWorkflow = function () {
    modalCreateWorkflow.classList.remove("hidden");
  };

  window.editWorkflow = function (workflowId, versionId) {
    currentWorkflowId = workflowId;
    currentVersionId = versionId;
    listView.classList.add("hidden");
    editorView.classList.remove("hidden");
    loadVersionDetails(versionId);
  };

  function hideCreateWorkflowModal() {
    modalCreateWorkflow.classList.add("hidden");
    formCreateWorkflow.reset();
  }

  btnCloseWorkflowModal.onclick = hideCreateWorkflowModal;
  btnCancelWorkflowModal.onclick = hideCreateWorkflowModal;

  formCreateWorkflow.onsubmit = async (event) => {
    event.preventDefault();
    const name = document.getElementById("new-workflow-name").value.trim();
    const code = document.getElementById("new-workflow-code").value.trim().toUpperCase().replace(/\s+/g, "_");
    if (workflows.find(workflow => workflow.code === code)) {
      showToast(`Approval path with code '${code}' already exists.`, "error");
      return;
    }

    const submitButton = formCreateWorkflow.querySelector("button[type='submit']");
    const originalText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.textContent = "Creating...";

    try {
      const res = await fetch("/module/WFLWBLD/api", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, code })
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || "Failed to create approval path.", "error");
        return;
      }

      showToast("Approval path created.");
      hideCreateWorkflowModal();
      const listRes = await fetch("/module/WFLWBLD/api");
      const listData = await listRes.json();
      const found = listData.find(item => item.code === code);
      if (found && found.latest_version_id) {
        editWorkflow(found.id, found.latest_version_id);
      } else {
        showList();
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to create approval path.", "error");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = originalText;
    }
  };

  btnAddLevel.onclick = () => {
    if (levelsList.length === 0) {
      levelsList.push({
        level_number: 1,
        level_name: "Review Step 1",
        level_type: "regular",
        assignment_mode: "same",
        approval_mode: "ANY_ONE",
        skip_if_empty: false,
        approvers: []
      });
    } else {
      const insertIndex = finalApprovalIndex() >= 0 ? finalApprovalIndex() : levelsList.length;
      levelsList.splice(insertIndex, 0, {
        level_number: insertIndex + 1,
        level_name: "",
        level_type: "regular",
        assignment_mode: "same",
        approval_mode: "ANY_ONE",
        skip_if_empty: false,
        approvers: []
      });
    }
    levelsList.forEach((level, index) => level.level_number = index + 1);
    ensureGenericLevelNames();
    setUnsaved(true);
    renderWorkspace();
  };

  previewSiteSelect.onchange = renderPreviewPath;

  if (dfForm) {
    dfForm.addEventListener("change", () => {
      selectedFormId = dfForm.value ? parseInt(dfForm.value) : null;
      const selectedForm = availableForms.find(form => parseInt(form.id) === parseInt(selectedFormId));
      selectedSiteIds = selectedForm ? (selectedForm.site_ids || []).map(siteId => parseInt(siteId)).filter(Boolean) : [];
      setUnsaved(true);
      renderWorkspace();
    });
  }

  btnScrollPreview.onclick = () => {
    document.getElementById("preview-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  dfName.addEventListener("change", () => {
    setUnsaved(true);
  });

  async function saveDraft() {
    if (!permissions.can_edit) return;
    const name = dfName.value.trim();
    if (!name) {
      showToast("Approval path name cannot be empty.", "error");
      return;
    }

    ensureGenericLevelNames();
    const payload = {
      levels: levelsList.map((level, index) => ({
        level_number: index + 1,
        level_name: level.level_name,
        approval_mode: level.approval_mode || "ANY_ONE",
        skip_if_empty: isFinalLevel(index) ? false : Boolean(level.skip_if_empty),
        approvers: (level.approvers || []).map(approver => ({
          user_id: approver.user_id,
          sequence_number: approver.sequence_number || null,
          scope_site_id: approver.scope_site_id || null
        }))
      }))
    };

    try {
      await fetch(`/module/WFLWBLD/api/${currentWorkflowId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });

      const res = await fetch(`/module/WFLWBLD/api/version/${currentVersionId}/levels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || "Failed to save approval path.", "error");
        return;
      }

      showToast("Approval path draft saved.");
      setUnsaved(false);
      loadVersionDetails(currentVersionId);
    } catch (err) {
      console.error(err);
      showToast("Failed to save draft.", "error");
    }
  }

  btnSaveDraft.onclick = saveDraft;

  function openPublishReview() {
    lastValidation = validateWorkflow();
    btnConfirmPublish.disabled = !lastValidation.canPublish || hasUnsavedChanges;

    if (hasUnsavedChanges) {
      publishReviewBody.innerHTML = `
        <div class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Save your draft changes before publishing.
        </div>
      `;
    } else if (lastValidation.canPublish) {
      publishReviewBody.innerHTML = `
        <div class="space-y-3">
          <div class="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-800">
            This path is ready to publish. It will be live for ${lastValidation.coveredSites.length} site${lastValidation.coveredSites.length === 1 ? "" : "s"} immediately after publishing.
          </div>
          <ul class="space-y-2 text-slate-600">
            <li>✓ Every selected site has a valid path.</li>
            <li>✓ Final approval exists for every selected site.</li>
            <li>✓ No partial publishing will be performed.</li>
          </ul>
        </div>
      `;
    } else {
      publishReviewBody.innerHTML = `
        <div class="space-y-3">
          <div class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 font-semibold text-rose-800">
            Publishing is blocked until these issues are fixed.
          </div>
          <ul class="list-disc space-y-1 pl-5 text-slate-700">
            ${lastValidation.issues.map(issue => `<li>${escapeHtml(issue)}</li>`).join("")}
          </ul>
        </div>
      `;
    }
    modalPublishReview.classList.remove("hidden");
    modalPublishReview.classList.add("flex");
  }

  function closePublishReview() {
    modalPublishReview.classList.add("hidden");
    modalPublishReview.classList.remove("flex");
  }

  btnClosePublishModal.onclick = closePublishReview;
  btnCancelPublishModal.onclick = closePublishReview;
  btnConfirmPublish.onclick = publishVersion;

  async function publishVersion() {
    if (!permissions.can_publish) return;
    lastValidation = validateWorkflow();
    if (!lastValidation.canPublish || hasUnsavedChanges) {
      openPublishReview();
      return;
    }

    try {
      const res = await fetch(`/module/WFLWBLD/api/version/${currentVersionId}/publish`, {
        method: "POST"
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || "Publish failed.", "error");
        return;
      }

      closePublishReview();
      showToast("Approval path published.");
      showList();
    } catch (err) {
      console.error(err);
      showToast("Failed to publish approval path.", "error");
    }
  }

  async function createNewVersionDraft() {
    if (!permissions.can_create_version) return;
    if (!confirm("Create a new draft version starting from this live approval path?")) return;

    try {
      const res = await fetch(`/module/WFLWBLD/api/${currentWorkflowId}/new-version`, {
        method: "POST"
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || "Failed to create draft version.", "error");
        return;
      }
      showToast("New draft version created.");
      editWorkflow(currentWorkflowId, data.data.version_id);
    } catch (err) {
      console.error(err);
      showToast("Failed to create new draft version.", "error");
    }
  }

  async function deleteWorkflow() {
    if (!confirm("Delete this approval path? This soft-deletes the path record.")) return;
    try {
      const res = await fetch(`/module/WFLWBLD/api/${currentWorkflowId}`, {
        method: "DELETE"
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || "Failed to delete approval path.", "error");
        return;
      }
      showToast("Approval path deleted.");
      showList();
    } catch (err) {
      console.error(err);
      showToast("Failed to delete approval path.", "error");
    }
  }

  loadWorkflows();
});
