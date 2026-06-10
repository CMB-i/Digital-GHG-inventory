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
    dirtyRows: new Set()
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
    return `${row.year}-${row.month}`;
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

  function setEmpty(title, body) {
    tableWrap.classList.add("hidden");
    emptyTitleEl.textContent = title;
    emptyBodyEl.textContent = body;
    emptyEl.classList.remove("hidden");
    btnSave.disabled = true;
    btnSubmit.disabled = true;
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
    if (!forms.length) {
      formTabs.innerHTML = '<span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500">No assigned forms</span>';
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
        loadWorkbook();
      };
      formTabs.appendChild(button);
    });
  }

  function renderHeader() {
    const site = state.options.sites.find(item => String(item.id) === String(state.selectedSiteId));
    siteNameEl.textContent = site ? site.name : "Select a site";
    fyLabelEl.textContent = `FY ${state.selectedFy}-${String(state.selectedFy + 1).slice(-2)}`;

    const row = selectedRow();
    if (!row) {
      selectedStatusEl.textContent = "No month selected";
      selectedStatusEl.className = "rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600";
      lastSavedEl.textContent = "Select a month row to save or submit.";
      btnSave.disabled = true;
      btnSubmit.disabled = true;
      return;
    }

    const status = row.submission_status || row.period_status || "Not Started";
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
    btnSave.disabled = !(row.editability && row.editability.editable);
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

    tableHead.innerHTML = `
      <tr>
        <th class="sticky left-0 z-10 bg-slate-50 px-4 py-3 text-left">Month</th>
        <th class="px-4 py-3 text-left">Status</th>
        ${fields.map(field => `
          <th class="min-w-[180px] px-4 py-3 text-left">
            <span>${escapeHtml(field.field_name)}</span>
            ${field.field_config && field.field_config.unit ? `<span class="ml-1 text-slate-400 normal-case">(${escapeHtml(field.field_config.unit)})</span>` : ""}
            ${field.field_config && field.field_config.is_required ? '<span class="ml-1 text-rose-500">*</span>' : ""}
          </th>
        `).join("")}
      </tr>
    `;

    tableBody.innerHTML = rows.map(row => renderRow(row, fields)).join("");
    tableBody.querySelectorAll("tr[data-row-key]").forEach(tr => {
      tr.addEventListener("click", function (event) {
        if (event.target && ["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A"].includes(event.target.tagName)) return;
        state.selectedRowKey = tr.dataset.rowKey;
        renderTable();
        renderHeader();
      });
    });

    tableBody.querySelectorAll("[data-field-code]").forEach(input => {
      input.addEventListener("input", onCellChange);
      input.addEventListener("change", onCellChange);
    });
  }

  function renderRow(row, fields) {
    const key = rowKey(row);
    const selected = key === state.selectedRowKey;
    const editable = row.editability && row.editability.editable;
    const rowClass = selected ? "bg-indigo-50/60 ring-1 ring-inset ring-indigo-200" : "hover:bg-slate-50/60";
    const statusClass = editable
      ? "bg-blue-50 text-blue-700 border-blue-100"
      : row.editability && row.editability.state === "read_only"
        ? "bg-slate-100 text-slate-600 border-slate-200"
        : "bg-slate-50 text-slate-400 border-slate-200";

    return `
      <tr data-row-key="${key}" class="${rowClass} cursor-pointer transition">
        <td class="sticky left-0 z-10 border-r border-slate-100 bg-inherit px-4 py-4">
          <div class="font-bold text-slate-900">${escapeHtml(row.label)}</div>
          <div class="text-xs text-slate-500">${escapeHtml(row.period_label)}</div>
        </td>
        <td class="px-4 py-4 align-top">
          <span class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClass}">
            ${escapeHtml(row.submission_status || row.period_status || "Unavailable")}
          </span>
          <div class="mt-1 max-w-[180px] text-xs text-slate-400">${escapeHtml(row.editability ? row.editability.reason : "")}</div>
        </td>
        ${fields.map(field => renderCell(row, field, editable)).join("")}
      </tr>
    `;
  }

  function renderCell(row, field, editable) {
    const value = fieldValue(row, field);
    const disabled = !editable || field.field_type === "calculated" || field.field_type === "file";
    const common = `data-row-key="${rowKey(row)}" data-field-code="${escapeHtml(field.field_code)}" class="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-800 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-50 disabled:text-slate-500" ${disabled ? "disabled" : ""}`;

    let control;
    if (field.field_type === "boolean") {
      const checked = value === true || value === "true" || value === "1" || value === 1 || value === "on";
      control = `<input type="checkbox" data-row-key="${rowKey(row)}" data-field-code="${escapeHtml(field.field_code)}" class="h-5 w-5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}>`;
    } else if (field.field_type === "date") {
      control = `<input type="date" value="${escapeHtml(value)}" ${common}>`;
    } else if (field.field_type === "dropdown") {
      const options = Array.isArray(field.field_config && field.field_config.options)
        ? field.field_config.options
        : [];
      control = `
        <select ${common}>
          <option value="">Select...</option>
          ${options.map(option => {
            const optionValue = option.entry_code || option.code || option.value || "";
            const optionLabel = option.entry_label || option.label || optionValue;
            return `<option value="${escapeHtml(optionValue)}" ${String(value) === String(optionValue) ? "selected" : ""}>${escapeHtml(optionLabel)}</option>`;
          }).join("")}
        </select>
      `;
    } else if (field.field_type === "file") {
      const fileLabel = value && typeof value === "object" ? value.original_name : "";
      control = row.submission_id
        ? `<a href="/module/SUBMIT/submissions/${row.submission_id}" class="text-sm font-semibold text-indigo-600 hover:text-indigo-700">${fileLabel ? escapeHtml(fileLabel) : "Open monthly sheet"}</a>`
        : '<span class="text-sm text-slate-400">Create draft to upload</span>';
    } else {
      const type = field.field_type === "number" || field.field_type === "calculated" ? "number" : "text";
      control = `<input type="${type}" value="${escapeHtml(value)}" ${common}>`;
    }

    return `<td class="min-w-[180px] px-4 py-4 align-top">${control}</td>`;
  }

  function onCellChange(event) {
    const input = event.target;
    const row = state.workbook.rows.find(item => rowKey(item) === input.dataset.rowKey);
    if (!row || !(row.editability && row.editability.editable)) return;

    if (!row.values) row.values = {};
    row.values[input.dataset.fieldCode] = input.type === "checkbox" ? input.checked : input.value;
    state.selectedRowKey = input.dataset.rowKey;
    state.dirtyRows.add(input.dataset.rowKey);
    renderHeader();
  }

  async function loadOptions() {
    const response = await fetch("/module/SUBMIT/api/annual-workbook/options");
    if (!response.ok) throw new Error("Could not load assigned sites and forms.");
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
    state.workbook = null;
    state.selectedRowKey = null;
    state.dirtyRows.clear();
    renderFormTabs();
    renderHeader();

    const forms = formsForSelectedSite();
    if (!state.selectedSiteId) {
      setEmpty("No assigned sites", "You do not have site access for submissions.");
      return;
    }
    if (!forms.length) {
      setEmpty("No forms assigned", "Published forms assigned to this site will appear as tabs.");
      return;
    }
    if (!state.selectedFormId) {
      state.selectedFormId = forms[0].id;
    }

    const params = new URLSearchParams({
      site_id: state.selectedSiteId,
      form_id: state.selectedFormId,
      fy: state.selectedFy
    });
    const response = await fetch(`/module/SUBMIT/api/annual-workbook?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load annual workbook.");

    state.workbook = data;
    const requestedRow = state.requestedMonth
      ? data.rows.find(row => parseInt(row.month) === state.requestedMonth)
      : null;
    state.selectedRowKey = requestedRow
      ? rowKey(requestedRow)
      : (data.rows[0] ? rowKey(data.rows[0]) : null);
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
    if (!row || !(row.editability && row.editability.editable)) return;

    try {
      btnSave.disabled = true;
      btnSave.textContent = "Saving...";
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
        const createData = await createResponse.json();
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
      const saveData = await saveResponse.json();
      if (!saveResponse.ok) {
        throw new Error(saveData.error || "Could not save draft.");
      }

      row.submission_id = submissionId;
      row.submission_status = "Draft";
      row.last_saved = new Date().toISOString();
      row.values = saveData.data && saveData.data.values ? saveData.data.values : row.values;
      state.dirtyRows.delete(rowKey(row));
      renderTable();
      renderHeader();
      showAlert("Monthly draft saved.", "success");
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
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 422 && data.errors) {
          const details = data.errors.map(item => {
            if (item.validation_errors) {
              return Object.values(item.validation_errors).join(" ");
            }
            return item.error || "";
          }).filter(Boolean).join(" ");
          throw new Error(`${data.error || "Validation failed."} ${details}`);
        }
        throw new Error(data.error || "Could not submit workbook package.");
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

  loadOptions().catch(error => {
    setEmpty("Could not load annual workbook", error.message);
    showAlert(error.message, "error");
  });
});
