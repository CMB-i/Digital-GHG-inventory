document.addEventListener("DOMContentLoaded", function () {
  const siteSelect = document.getElementById("workbook-site");
  const fySelect = document.getElementById("workbook-fy");
  const formTabs = document.getElementById("form-tabs");
  const siteNameEl = document.getElementById("workbook-site-name");
  const fyLabelEl = document.getElementById("workbook-fy-label");
  const selectedStatusEl = document.getElementById("workbook-selected-status");
  const lastSavedEl = document.getElementById("workbook-last-saved");
  const alertEl = document.getElementById("workbook-alert");
  const emptyEl = document.getElementById("workbook-empty");
  const emptyTitleEl = document.getElementById("workbook-empty-title");
  const emptyBodyEl = document.getElementById("workbook-empty-body");
  const tableWrap = document.getElementById("workbook-table-wrap");
  const tableHead = document.getElementById("workbook-head");
  const tableBody = document.getElementById("workbook-body");
  const btnSave = document.getElementById("btn-save-row");
  const btnSubmit = document.getElementById("btn-submit-row");
  const cellDetailModal = document.getElementById("cell-detail-modal");
  const cellDetailContext = document.getElementById("cell-detail-context");
  const cellDetailValue = document.getElementById("cell-detail-value");
  const cellDetailState = document.getElementById("cell-detail-state");
  const cellDetailIssues = document.getElementById("cell-detail-issues");
  const btnCloseCellDetail = document.getElementById("btn-close-cell-detail");
  const btnCancelCellDetail = document.getElementById("btn-cancel-cell-detail");
  const initialParams = new URLSearchParams(window.location.search);

  function paramInt(name) {
    const value = parseInt(initialParams.get(name), 10);
    return Number.isNaN(value) ? null : value;
  }

  const state = {
    options: { sites: [], forms_by_site: {} },
    selectedSiteId: null,
    selectedFormId: null,
    selectedFy: paramInt("fy") || defaultFyStartYear(),
    requestedSiteId: paramInt("site_id"),
    requestedFormId: paramInt("form_id"),
    requestedMonth: paramInt("month"),
    workbook: null,
    selectedRowKey: null,
    dirtyRows: new Set(),
    dirtyWorkbookFields: new Set()
  };

  function defaultFyStartYear() {
    const now = new Date();
    const month = now.getMonth() + 1;
    return month >= 4 ? now.getFullYear() : now.getFullYear() - 1;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatDateTime(value) {
    if (!value) return "Not saved yet";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true
    });
  }

  function fieldValue(row, field) {
    const value = row.values ? row.values[field.field_code] : "";
    if (value && typeof value === "object") {
      return value.raw_value || value.calculated_value || value.original_name || "";
    }
    return value ?? "";
  }

  function rowKey(row) {
    return window.WorkbookSheet ? window.WorkbookSheet.rowKey(row) : `${row.year}-${row.month}`;
  }

  function selectedRow() {
    if (!state.workbook || !state.selectedRowKey) return null;
    return state.workbook.rows.find(row => rowKey(row) === state.selectedRowKey) || null;
  }

  function showAlert(message, kind = "info") {
    alertEl.className = "rounded-xl border p-4 text-sm font-semibold";
    if (kind === "error") {
      alertEl.classList.add("border-rose-200", "bg-rose-50", "text-rose-700");
    } else if (kind === "success") {
      alertEl.classList.add("border-emerald-200", "bg-emerald-50", "text-emerald-700");
    } else {
      alertEl.classList.add("border-blue-200", "bg-blue-50", "text-blue-700");
    }
    alertEl.textContent = message;
    alertEl.classList.remove("hidden");
  }

  function hideAlert() {
    alertEl.classList.add("hidden");
  }

  async function parseJsonResponse(response, fallbackMessage) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    const text = await response.text();
    const preview = text.replace(/\s+/g, " ").trim().slice(0, 120);
    throw new Error(`${fallbackMessage} The server returned a non-JSON response (${response.status})${preview ? `: ${preview}` : "."}`);
  }

  function packageSubmitErrorMessage(data) {
    const parts = [data.error || "Could not submit workbook package."];
    if (Array.isArray(data.errors) && data.errors.length) {
      data.errors.forEach(item => {
        const label = item.form_name ? `${item.form_name}: ` : "";
        if (item.validation_errors) {
          const fieldMessages = Object.values(item.validation_errors).filter(Boolean).join(" ");
          if (fieldMessages) {
            parts.push(`${label}${fieldMessages}`);
            return;
          }
        }
        if (item.error) parts.push(`${label}${item.error}`);
      });
    }
    if (Array.isArray(data.warnings) && data.warnings.length) {
      data.warnings.forEach(item => {
        const label = item.form_name ? `${item.form_name}: ` : "";
        if (item.reason) parts.push(`${label}${item.reason}`);
      });
    }
    return parts.filter(Boolean).join(" ");
  }

  function setEmpty(title, body) {
    tableWrap.classList.add("hidden");
    emptyTitleEl.textContent = title;
    emptyBodyEl.textContent = body;
    emptyEl.classList.remove("hidden");
    btnSave.disabled = true;
    btnSubmit.disabled = true;
  }

  function hasOpenWorkbookPeriod() {
    if (!state.workbook || !Array.isArray(state.workbook.rows)) return false;
    return state.workbook.rows.some(row => row.period_status === "OPEN" || row.period_status === "REOPENED");
  }

  function renderFyOptions() {
    fySelect.innerHTML = "";
    for (let year = state.selectedFy - 2; year <= state.selectedFy + 2; year += 1) {
      const opt = document.createElement("option");
      opt.value = String(year);
      opt.textContent = `FY ${year}-${String(year + 1).slice(-2)}`;
      opt.selected = year === state.selectedFy;
      fySelect.appendChild(opt);
    }
  }

  function renderSiteOptions() {
    siteSelect.innerHTML = "";
    if (!state.options.sites.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No assigned sites";
      siteSelect.appendChild(opt);
      return;
    }

    state.options.sites.forEach(site => {
      const opt = document.createElement("option");
      opt.value = String(site.id);
      opt.textContent = `${site.name}${site.code ? ` (${site.code})` : ""}`;
      opt.selected = String(site.id) === String(state.selectedSiteId);
      siteSelect.appendChild(opt);
    });
  }

  function formsForSelectedSite() {
    if (!state.selectedSiteId) return [];
    return state.options.forms_by_site[String(state.selectedSiteId)] || [];
  }

  function renderFormTabs() {
    const forms = formsForSelectedSite();
    formTabs.innerHTML = "";
    if (!forms.length && state.selectedFormId !== "calc_results") {
      formTabs.innerHTML = '<span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500">No assigned sheets</span>';
      return;
    }

    forms.forEach(form => {
      const button = document.createElement("button");
      button.type = "button";
      const active = String(form.id) === String(state.selectedFormId);
      button.className = `rounded-full border px-3 py-1.5 text-xs font-bold transition ${
        active
          ? "border-indigo-200 bg-indigo-50 text-indigo-700"
          : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
      }`;
      button.textContent = form.name;
      button.onclick = function () {
        state.selectedFormId = form.id;
        loadWorkbook().catch(error => showAlert(error.message, "error"));
      };
      formTabs.appendChild(button);
    });

    // Append Calculation Results tab button
    if (state.selectedSiteId) {
      const calcButton = document.createElement("button");
      calcButton.type = "button";
      const calcActive = state.selectedFormId === "calc_results";
      calcButton.className = `rounded-full border px-3 py-1.5 text-xs font-bold transition ${
        calcActive
          ? "border-indigo-200 bg-indigo-50 text-indigo-700"
          : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
      }`;
      calcButton.textContent = "Calculation Results";
      calcButton.onclick = function () {
        state.selectedFormId = "calc_results";
        loadWorkbook();
      };
      formTabs.appendChild(calcButton);
    }
  }

  function renderHeader() {
    const site = state.options.sites.find(item => String(item.id) === String(state.selectedSiteId));
    siteNameEl.textContent = site ? site.name : "Select a site";
    fyLabelEl.textContent = `FY ${state.selectedFy}-${String(state.selectedFy + 1).slice(-2)}`;

    if (state.selectedFormId === "calc_results") {
      selectedStatusEl.textContent = "Calculation Results";
      selectedStatusEl.className = "rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 border border-slate-200";
      lastSavedEl.textContent = "Read-only calculation dashboard for this financial year.";
      btnSave.disabled = true;
      btnSubmit.disabled = true;
      return;
    }

    const row = selectedRow();
    if (!row) {
      selectedStatusEl.textContent = "No month selected";
      selectedStatusEl.className = "rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600";
      lastSavedEl.textContent = "Select a month row to save or submit.";
      btnSave.disabled = state.dirtyWorkbookFields.size === 0;
      btnSubmit.disabled = true;
      return;
    }

    const status = row.submission_status || row.status || row.period_status || "Not Started";
    selectedStatusEl.textContent = `${row.label}: ${status}`;
    selectedStatusEl.className = "rounded-full px-2.5 py-1 text-xs font-semibold ";
    if (status === "Approved") {
      selectedStatusEl.classList.add("bg-emerald-100", "text-emerald-700");
    } else if (row.editability && row.editability.editable) {
      selectedStatusEl.classList.add("bg-blue-100", "text-blue-700");
    } else {
      selectedStatusEl.classList.add("bg-slate-100", "text-slate-600");
    }

    lastSavedEl.textContent = row.last_saved ? `Last saved ${formatDateTime(row.last_saved)}` : row.editability.reason;
    btnSave.disabled = !(row.editability && row.editability.editable) && state.dirtyWorkbookFields.size === 0;
    btnSubmit.disabled = !(row.editability && row.editability.editable);
  }

  function renderTable() {
    if (!state.workbook) {
      setEmpty("No workbook loaded", "Choose a site and assigned form.");
      return;
    }

    const fields = state.workbook.fields || [];
    const rows = state.workbook.rows || [];

    if (!fields.length) {
      setEmpty("No fields configured", "The selected form has no published fields.");
      return;
    }

    emptyEl.classList.add("hidden");
    tableWrap.classList.remove("hidden");

    const mode = state.selectedFormId === "calc_results" ? "calc_results" : "entry";

    window.WorkbookSheet.render({
      mode: mode,
      headEl: tableHead,
      bodyEl: tableBody,
      fields,
      sections: state.workbook.sections || [],
      workbookValues: state.workbook.workbook_values || {},
      canEditWorkbookValues: hasOpenWorkbookPeriod(),
      rows: rows.map(row => ({
        ...row,
        editable: mode === "calc_results" ? false : Boolean(row.editability && row.editability.editable),
        reason: row.editability ? row.editability.reason : ""
      })),
      selectedRowKey: state.selectedRowKey,
      onRowSelect: function (key) {
        state.selectedRowKey = key;
        renderTable();
        renderHeader();
      },
      onCellChange,
      onWorkbookValueChange,
      onCellOpen: openCellDetail
    });
  }

  function renderIssueList(issues) {
    if (!issues || !issues.length) {
      cellDetailIssues.innerHTML = '<div class="rounded-lg bg-slate-50 px-3 py-2 text-slate-400">No comments for this cell.</div>';
      return;
    }
    cellDetailIssues.innerHTML = issues.map(issue => `
      <div class="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2">
        <div class="text-xs font-bold text-amber-900">${escapeHtml(issue.raised_by_name || "Reviewer")}</div>
        <div class="mt-1 text-sm text-amber-800">${escapeHtml(issue.issue_text || "")}</div>
      </div>
    `).join("");
  }

  function openCellDetail(cellInfo) {
    cellDetailContext.textContent = `${state.workbook ? state.workbook.selected_form.name : "Workbook"} · ${cellInfo.rowLabel} · ${cellInfo.fieldName}`;
    cellDetailValue.textContent = cellInfo.value || "Empty";
    cellDetailState.textContent = `${cellInfo.cellStateLabel}${cellInfo.locked ? " · Locked" : ""}`;
    renderIssueList(cellInfo.issues || []);
    cellDetailModal.classList.remove("hidden");
    cellDetailModal.classList.add("flex");
  }

  function closeCellDetail() {
    cellDetailModal.classList.add("hidden");
    cellDetailModal.classList.remove("flex");
  }

  function onCellChange(event) {
    const input = event.target;
    const row = state.workbook.rows.find(item => rowKey(item) === input.dataset.rowKey);
    if (!row || !(row.editability && row.editability.editable)) return;

    // Ignore change events from non-monthly fields
    const field = state.workbook.fields.find(f => f.field_code === input.dataset.fieldCode);
    if (field && window.WorkbookSheet.isFieldNonMonthly(field, state.workbook)) return;

    if (!row.values) row.values = {};
    row.values[input.dataset.fieldCode] = input.type === "checkbox" ? input.checked : input.value;
    state.selectedRowKey = input.dataset.rowKey;
    state.dirtyRows.add(input.dataset.rowKey);
    renderHeader();
  }

  function onWorkbookValueChange(event) {
    const input = event.target;
    const fieldCode = input.dataset.workbookFieldCode;
    if (!fieldCode || !state.workbook) return;
    if (!state.workbook.workbook_values) state.workbook.workbook_values = {};
    const current = state.workbook.workbook_values[fieldCode] || {};
    const rawValue = input.type === "checkbox" ? input.checked : input.value;
    state.workbook.workbook_values[fieldCode] = {
      ...current,
      raw_value: rawValue,
      cell_state: rawValue ? "draft_filled" : "blank_editable",
      is_locked: false
    };
    state.dirtyWorkbookFields.add(fieldCode);
    renderHeader();
  }

  async function loadOptions() {
    const response = await fetch("/module/SUBMIT/api/annual-workbook/options");
    if (!response.ok) throw new Error("Could not load assigned sites and sheets.");
    state.options = await response.json();
    const requestedSite = state.options.sites.find(site => parseInt(site.id) === state.requestedSiteId);
    state.selectedSiteId = requestedSite
      ? requestedSite.id
      : (state.options.sites[0] ? state.options.sites[0].id : null);
    const firstForms = formsForSelectedSite();
    const requestedForm = firstForms.find(form => parseInt(form.id) === state.requestedFormId);
    state.selectedFormId = requestedForm
      ? requestedForm.id
      : (firstForms[0] ? firstForms[0].id : null);
    renderFyOptions();
    renderSiteOptions();
    renderFormTabs();
    await loadWorkbook();
  }

  async function loadWorkbook() {
    hideAlert();
    const previousRowKey = state.selectedRowKey;
    state.workbook = null;
    state.dirtyRows.clear();
    state.dirtyWorkbookFields.clear();
    renderFormTabs();
    renderHeader();

    const forms = formsForSelectedSite();
    if (!state.selectedSiteId) {
      setEmpty("No assigned sites", "You do not have site access for submissions.");
      return;
    }
    if (!forms.length && state.selectedFormId !== "calc_results") {
      setEmpty("No sheets assigned", "Published sheets assigned to this site will appear as tabs.");
      return;
    }
    if (!state.selectedFormId) {
      state.selectedFormId = forms[0] ? forms[0].id : "calc_results";
    }

    let url = "";
    if (state.selectedFormId === "calc_results") {
      const params = new URLSearchParams({
        site_id: state.selectedSiteId,
        fy: state.selectedFy
      });
      url = `/module/SUBMIT/api/annual-workbook/calculation-results?${params.toString()}`;
    } else {
      const params = new URLSearchParams({
        site_id: state.selectedSiteId,
        form_id: state.selectedFormId,
        fy: state.selectedFy
      });
      url = `/module/SUBMIT/api/annual-workbook?${params.toString()}`;
    }

    const response = await fetch(url);
    const data = await parseJsonResponse(response, "Could not load annual workbook.");
    if (!response.ok) throw new Error(data.error || "Could not load annual workbook.");

    state.workbook = data;
    const requestedRow = state.requestedMonth
      ? data.rows.find(row => parseInt(row.month) === state.requestedMonth)
      : null;
    const previousRow = previousRowKey
      ? data.rows.find(row => rowKey(row) === previousRowKey)
      : null;
    state.selectedRowKey = requestedRow
      ? rowKey(requestedRow)
      : (previousRow ? rowKey(previousRow) : (data.rows[0] ? rowKey(data.rows[0]) : null));
    renderTable();
    renderHeader();
    scrollSelectedRowIntoView();
  }

  function scrollSelectedRowIntoView() {
    if (!state.selectedRowKey) return;
    window.setTimeout(function () {
      const selected = tableBody.querySelector(`tr[data-row-key="${state.selectedRowKey}"]`);
      if (selected) {
        selected.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
      }
    }, 100);
  }

  async function saveSelectedRow() {
    const row = selectedRow();
    const shouldSaveMonthly = row && row.editability && row.editability.editable;
    const shouldSaveWorkbookValues = state.dirtyWorkbookFields.size > 0;
    if (!shouldSaveMonthly && !shouldSaveWorkbookValues) return;

    try {
      btnSave.disabled = true;
      btnSave.textContent = "Saving...";
      if (shouldSaveWorkbookValues) {
        const values = {};
        state.dirtyWorkbookFields.forEach(fieldCode => {
          const cell = state.workbook.workbook_values ? state.workbook.workbook_values[fieldCode] : null;
          values[fieldCode] = cell && typeof cell === "object" ? cell.raw_value : cell;
        });
        const valueResponse = await fetch("/module/SUBMIT/api/annual-workbook/values", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            site_id: state.workbook.site.id,
            form_id: state.workbook.selected_form.id,
            fy: state.workbook.financial_year.start_year,
            values
          })
        });
        const valueData = await parseJsonResponse(valueResponse, "Could not save annual workbook values.");
        if (!valueResponse.ok) {
          throw new Error(valueData.error || "Could not save annual workbook values.");
        }
        if (valueData.data && valueData.data.workbook_values) {
          state.workbook.workbook_values = valueData.data.workbook_values;
        }
        state.dirtyWorkbookFields.clear();
      }

      if (shouldSaveMonthly) {
        let submissionId = row.submission_id;
        if (!submissionId) {
          if (!row.period_id) {
            throw new Error("A reporting period must exist before this month can be saved.");
          }
          const createResponse = await fetch("/module/SUBMIT/api/submissions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              site_id: state.workbook.site.id,
              form_id: state.workbook.selected_form.id,
              reporting_period_id: row.period_id
            })
          });
          const createData = await parseJsonResponse(createResponse, "Could not create draft for this month.");
          if (createResponse.status === 409 && createData.existing_id) {
            submissionId = createData.existing_id;
          } else if (!createResponse.ok) {
            throw new Error(createData.error || "Could not create draft for this month.");
          } else {
            submissionId = createData.data.submission_id;
          }
        }

        const saveResponse = await fetch(`/module/SUBMIT/api/submissions/${submissionId}/autosave`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ values: row.values || {} })
        });
        const saveData = await parseJsonResponse(saveResponse, "Could not save draft.");
        if (!saveResponse.ok) {
          throw new Error(saveData.error || "Could not save draft.");
        }

        row.submission_id = submissionId;
        row.submission_status = "Draft";
        row.last_saved = new Date().toISOString();
        row.values = saveData.data && saveData.data.values ? saveData.data.values : row.values;
        state.dirtyRows.delete(rowKey(row));
      }
      renderTable();
      renderHeader();
      showAlert("Workbook draft saved.", "success");
    } catch (error) {
      showAlert(error.message, "error");
    } finally {
      btnSave.textContent = "Save draft";
      renderHeader();
    }
  }

  async function submitSelectedRow() {
    const row = selectedRow();
    if (!row) {
      showAlert("Select a month before submitting.", "error");
      return;
    }
    if (!(row.editability && row.editability.editable)) return;
    if (!window.confirm(`Submit the ${row.period_label} workbook package for approval?`)) {
      return;
    }

    try {
      btnSubmit.disabled = true;
      btnSubmit.textContent = "Submitting...";
      const response = await fetch("/module/SUBMIT/api/annual-workbook/package/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          site_id: state.workbook.site.id,
          period_id: row.period_id,
          year: row.year,
          month: row.month,
          selected_form_id: state.workbook.selected_form.id,
          values: row.values || {}
        })
      });
      const data = await parseJsonResponse(response, "Could not submit workbook package.");
      if (!response.ok) {
        throw new Error(packageSubmitErrorMessage(data));
      }
      const included = data.data && data.data.included_submissions ? data.data.included_submissions.length : 0;
      showAlert(`Workbook package submitted for approval. ${included} sheet${included === 1 ? "" : "s"} included.`, "success");
      await loadWorkbook();
    } catch (error) {
      showAlert(error.message, "error");
    } finally {
      btnSubmit.textContent = "Submit selected month package";
      renderHeader();
    }
  }

  siteSelect.addEventListener("change", function () {
    state.selectedSiteId = siteSelect.value;
    const forms = formsForSelectedSite();
    state.selectedFormId = forms[0] ? forms[0].id : null;
    renderSiteOptions();
    loadWorkbook().catch(error => showAlert(error.message, "error"));
  });

  fySelect.addEventListener("change", function () {
    state.selectedFy = parseInt(fySelect.value, 10);
    loadWorkbook().catch(error => showAlert(error.message, "error"));
  });

  btnSave.addEventListener("click", saveSelectedRow);
  btnSubmit.addEventListener("click", submitSelectedRow);
  [btnCloseCellDetail, btnCancelCellDetail].forEach(button => {
    if (button) button.addEventListener("click", closeCellDetail);
  });
  if (cellDetailModal) {
    cellDetailModal.addEventListener("click", function (event) {
      if (event.target === cellDetailModal) closeCellDetail();
    });
  }

  loadOptions().catch(error => {
    setEmpty("Could not load annual workbook", error.message);
    showAlert(error.message, "error");
  });
});
