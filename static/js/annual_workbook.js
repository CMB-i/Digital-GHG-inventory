document.addEventListener("DOMContentLoaded", function () {
  const siteSelect = document.getElementById("workbook-site");
  const fySelect = document.getElementById("workbook-fy");
  const formTabs = document.getElementById("form-tabs");
  const siteNameEl = document.getElementById("workbook-site-name");
  const fyLabelEl = document.getElementById("workbook-fy-label");
  const selectedStatusEl = document.getElementById("workbook-selected-status");
  const workbookTitleEl = document.getElementById("annual-workbook-title");
  const workbookBreadcrumbEl = document.getElementById("annual-workbook-breadcrumb");
  const lastSavedEl = document.getElementById("workbook-last-saved");
  const alertEl = document.getElementById("workbook-alert");
  const emptyEl = document.getElementById("workbook-empty");
  const emptyTitleEl = document.getElementById("workbook-empty-title");
  const emptyBodyEl = document.getElementById("workbook-empty-body");
  const tableWrap = document.getElementById("workbook-table-wrap");
  const tableHead = document.getElementById("workbook-head");
  const tableBody = document.getElementById("workbook-body");
  const btnSave = document.getElementById("btn-save-draft");
  const btnSubmit = document.getElementById("btn-submit-sheet");
  const cellDetailModal = document.getElementById("cell-detail-modal");
  const cellDetailContext = document.getElementById("cell-detail-context");
  const cellDetailValue = document.getElementById("cell-detail-value");
  const cellDetailState = document.getElementById("cell-detail-state");
  const cellDetailIssues = document.getElementById("cell-detail-issues");
  const btnCloseCellDetail = document.getElementById("btn-close-cell-detail");
  const btnCancelCellDetail = document.getElementById("btn-cancel-cell-detail");
  const initialParams = new URLSearchParams(window.location.search);

  const currentMonthEl = document.getElementById("workbook-current-month");

  function getMonthName(m) {
    const months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return months[parseInt(m, 10)] || "";
  }

  function getFullMonthYear(month, year) {
    const months = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    const name = months[parseInt(month, 10)] || "";
    return year ? `${name} ${year}` : name;
  }

  let autosaveTimeout = null;
  let lastSavedTime = null;

  function paramInt(name) {
    const value = parseInt(initialParams.get(name), 10);
    return Number.isNaN(value) ? null : value;
  }

  const state = {
    options: { sites: [], forms_by_site: {}, workbooks_by_site: {} },
    selectedSiteId: null,
    selectedWorkbookId: null,
    selectedFormId: null,
    selectedFy: paramInt("fy") || defaultFyStartYear(),
    requestedSiteId: paramInt("site_id"),
    requestedWorkbookId: paramInt("workbook_id"),
    requestedFormId: paramInt("form_id"),
    requestedMonth: paramInt("month"),
    workbook: null,
    calculationResults: null,
    dashboardData: null,
    selectedRowKey: null,
    dirtyRows: new Set(),
    dirtyWorkbookFields: new Set()
  };

  function defaultFyStartYear() {
    const now = new Date();
    const month = now.getMonth() + 1;
    return month >= 4 ? now.getFullYear() : now.getFullYear() - 1;
  }

  function fyForMonth(year, month) {
    return month >= 4 ? year : year - 1;
  }

  function fyLabel(startYear) {
    return `FY ${startYear}-${String(startYear + 1).slice(-2)}`;
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
    alertEl.className = "rounded-xl border p-4 text-sm font-semibold mb-4";
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
    document.getElementById("calculated-results-section").classList.add("hidden");
    formTabs.innerHTML = "";
    emptyTitleEl.textContent = title;
    emptyBodyEl.textContent = body;
    emptyEl.classList.remove("hidden");
    siteNameEl.textContent = title;
    lastSavedEl.textContent = body;
    if (selectedStatusEl) {
      selectedStatusEl.textContent = "Unavailable";
      selectedStatusEl.className = "rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 border border-amber-200";
    }
    if (currentMonthEl) currentMonthEl.classList.add("hidden");
    btnSave.disabled = true;
    btnSubmit.disabled = true;
  }

  function hasOpenWorkbookPeriod() {
    if (!state.workbook || !Array.isArray(state.workbook.rows)) return false;
    return state.workbook.rows.some(row => row.period_status === "OPEN" || row.period_status === "REOPENED");
  }

  function openPeriodLabels() {
    if (!state.workbook || !Array.isArray(state.workbook.rows)) return [];
    return state.workbook.rows
      .filter(row => row.period_status === "OPEN" || row.period_status === "REOPENED" || (row.editability && row.editability.editable))
      .map(row => row.period_label || getFullMonthYear(row.month, row.year))
      .filter(Boolean);
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
    if (
      state.workbook
      && String(state.workbook.workbook?.id) === String(state.selectedWorkbookId)
      && Array.isArray(state.workbook.forms)
    ) {
      return state.workbook.forms || [];
    }
    const workbook = workbooksForSelectedSite().find(item => String(item.id || item.workbook_id) === String(state.selectedWorkbookId));
    return workbook ? (workbook.sheets || []) : [];
  }

  function workbooksForSelectedSite() {
    if (!state.selectedSiteId) return [];
    return state.options.workbooks_by_site[String(state.selectedSiteId)] || [];
  }

  function getFormStatusColor(formId) {
    if (!state.dashboardData) return null;
    const siteId = state.selectedSiteId;
    const fy = state.selectedFy;
    
    const actionNeeded = (state.dashboardData.action_needed || []).filter(row => 
      String(row.form_id) === String(formId) && 
      String(row.site_id) === String(siteId) && 
      fyForMonth(row.year, row.month) === fy
    );

    if (actionNeeded.some(row => row.status === "Changes Requested" || row.status === "Rejected" || row.status === "Changes requested")) {
      return "#c8102e"; // Red sent back
    }
    if (actionNeeded.some(row => row.status === "Draft")) {
      return "#8a6a13"; // Amber draft
    }
    return null;
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
      button.className = `workbook-tab whitespace-nowrap flex items-center gap-1.5 ${
        active ? "workbook-tab-active" : "workbook-tab-inactive"
      }`;
      
      // Add status dot (size 8px, only show on draft/sent back)
      const dotColor = getFormStatusColor(form.id);
      const dot = dotColor
        ? `<span class="w-[8px] h-[8px] rounded-full inline-block flex-shrink-0" style="background-color: ${dotColor};"></span>`
        : "";
      
      button.innerHTML = `${dot}<span>${escapeHtml(form.name)}</span>`;
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
      calcButton.className = `workbook-tab whitespace-nowrap ${
        calcActive ? "workbook-tab-active" : "workbook-tab-inactive"
      }`;
      calcButton.textContent = "Calculation Results";
      calcButton.onclick = function () {
        state.selectedFormId = "calc_results";
        loadWorkbook();
      };
      formTabs.appendChild(calcButton);
    }
  }

  function checkRequiredFields() {
    const btnSubmitEl = document.getElementById("btn-submit-sheet");
    const tooltip = document.getElementById("submit-tooltip");
    const tooltipList = document.getElementById("submit-tooltip-list");
    if (!btnSubmitEl || !state.workbook) return;

    const row = selectedRow();
    if (!row || !(row.editability && row.editability.editable)) {
      btnSubmitEl.disabled = true;
      if (tooltip) tooltip.classList.add("hidden");
      return;
    }

    const missingFields = [];
    const fields = state.workbook.fields || [];
    
    fields.forEach(field => {
      const isNonMonthly = window.WorkbookSheet.isFieldNonMonthly(field, state.workbook);
      const isRequired = field.field_config && field.field_config.is_required;
      const fieldType = String(field.field_type || "").trim().toLowerCase();
      
      if (isRequired && !isNonMonthly && fieldType !== "calculated") {
        const val = fieldValue(row, field);
        if (val === "" || val === null || val === undefined) {
          missingFields.push(field.field_name);
        }
      }
    });

    if (missingFields.length > 0) {
      btnSubmitEl.disabled = true;
      if (tooltipList) {
        tooltipList.innerHTML = missingFields.map(name => `<li><strong>${escapeHtml(name)}</strong> is required</li>`).join("");
      }
      if (tooltip) tooltip.classList.remove("hidden");
    } else {
      btnSubmitEl.disabled = false;
      if (tooltipList) {
        tooltipList.innerHTML = "<li>All required fields filled</li>";
      }
      if (tooltip) tooltip.classList.add("hidden");
    }
  }

  function renderHeader() {
    const site = state.options.sites.find(item => String(item.id) === String(state.selectedSiteId));
    const workbookName = state.workbook && state.workbook.workbook
      ? state.workbook.workbook.name
      : "Annual Workbook";
    if (workbookTitleEl) workbookTitleEl.textContent = workbookName;
    if (workbookBreadcrumbEl) workbookBreadcrumbEl.textContent = workbookName;
    siteNameEl.textContent = site ? site.name : "Select a site";
    fyLabelEl.textContent = `FY ${state.selectedFy}-${String(state.selectedFy + 1).slice(-2)}`;

    // Set current month badge
    if (currentMonthEl) {
      const labels = openPeriodLabels();
      if (state.workbook && Array.isArray(state.workbook.rows)) {
        if (labels.length === 1) {
          currentMonthEl.textContent = `${labels[0]} open for entry`;
        } else if (labels.length > 1) {
          currentMonthEl.textContent = `Open periods: ${labels.join(", ")}`;
        } else {
          currentMonthEl.textContent = "No period currently open for entry";
        }
        currentMonthEl.classList.remove("hidden");
      } else {
        currentMonthEl.classList.add("hidden");
      }
    }

    // Set Sheet specific label for Submit button
    const btnSubmitEl = document.getElementById("btn-submit-sheet");
    const sheetName = state.workbook ? state.workbook.selected_form.name : "Sheet";
    if (btnSubmitEl) {
      btnSubmitEl.textContent = `Submit ${sheetName}`;
    }

    if (state.selectedFormId === "calc_results") {
      if (selectedStatusEl) {
        selectedStatusEl.textContent = "Calculation Results";
        selectedStatusEl.className = "rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 border border-slate-200";
      }
      lastSavedEl.textContent = "Read-only calculation dashboard for this financial year.";
      btnSave.disabled = true;
      btnSubmit.disabled = true;
      return;
    }

    const row = selectedRow();
    if (!row) {
      if (selectedStatusEl) {
        selectedStatusEl.textContent = "No month selected";
        selectedStatusEl.className = "rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600";
      }
      lastSavedEl.textContent = "Select a month row to save or submit.";
      btnSave.disabled = state.dirtyWorkbookFields.size === 0;
      btnSubmit.disabled = true;
      return;
    }

    const status = row.submission_status || row.status || row.period_status || "Not Started";
    if (selectedStatusEl) {
      selectedStatusEl.textContent = `${row.label}: ${status}`;
      selectedStatusEl.className = "rounded-full px-2.5 py-1 text-xs font-semibold ";
      if (status === "Approved") {
        selectedStatusEl.classList.add("bg-emerald-100", "text-emerald-700");
      } else if (row.editability && row.editability.editable) {
        selectedStatusEl.classList.add("bg-blue-100", "text-blue-700");
      } else {
        selectedStatusEl.classList.add("bg-slate-100", "text-slate-600");
      }
    }

    lastSavedEl.textContent = row.last_saved ? `Last saved ${formatDateTime(row.last_saved)}` : row.editability.reason;
    btnSave.disabled = !(row.editability && row.editability.editable) && state.dirtyWorkbookFields.size === 0;
    
    checkRequiredFields();
  }

  function triggerAutosave() {
    if (autosaveTimeout) clearTimeout(autosaveTimeout);
    
    const dot = document.getElementById("save-status-dot");
    const text = document.getElementById("save-status-text");
    if (dot && text) {
      dot.className = "h-2 w-2 rounded-full bg-amber-500 animate-pulse";
      text.textContent = "Saving...";
    }
    
    autosaveTimeout = setTimeout(async function () {
      await saveSelectedRow();
      lastSavedTime = new Date();
      updateLastSavedText();
    }, 2000);
  }

  function updateLastSavedText() {
    const dot = document.getElementById("save-status-dot");
    const text = document.getElementById("save-status-text");
    if (!dot || !text) return;
    if (!lastSavedTime) {
      dot.className = "h-2 w-2 rounded-full bg-slate-300";
      text.textContent = "Your changes save automatically";
      return;
    }
    
    const diffMs = new Date() - lastSavedTime;
    const diffMins = Math.floor(diffMs / 60000);
    
    dot.className = "h-2 w-2 rounded-full bg-emerald-500";
    if (diffMins < 1) {
      text.textContent = "Last saved just now";
    } else {
      text.textContent = `Last saved ${diffMins} min${diffMins === 1 ? "" : "s"} ago`;
    }
  }

  // Update save status text every 30 seconds
  setInterval(updateLastSavedText, 30000);

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
      onCellChange: function(e) {
        onCellChange(e);
        triggerAutosave();
      },
      onWorkbookValueChange: function(e) {
        onWorkbookValueChange(e);
        triggerAutosave();
      },
      onCellOpen: openCellDetail
    });

    // Check sent back badge
    const needsCorrectionRow = rows.find(row => 
      row.submission_status === "Changes Requested" || row.submission_status === "Rejected"
    );
    const sentBackBadge = document.getElementById("sent-back-badge");
    if (sentBackBadge) {
      if (needsCorrectionRow) {
        sentBackBadge.classList.remove("hidden");
        sentBackBadge.onclick = function() {
          const rowEl = tableBody.querySelector(`tr[data-row-key="${rowKey(needsCorrectionRow)}"]`);
          if (rowEl) {
            rowEl.scrollIntoView({ behavior: "smooth", block: "center" });
            rowEl.classList.add("ring-4", "ring-rose-400");
            setTimeout(() => rowEl.classList.remove("ring-4", "ring-rose-400"), 2000);
          }
        };
      } else {
        sentBackBadge.classList.add("hidden");
      }
    }
  }

  function statusClass(row) {
    const status = row.submission_status || row.status || row.period_status || "Unavailable";
    if (status === "Approved") return "bg-emerald-100 text-emerald-700 border-emerald-200";
    if (status === "Changes Requested") return "bg-amber-100 text-amber-700 border-amber-200";
    if (["Submitted", "Resubmitted", "Under Review"].includes(status)) return "bg-indigo-100 text-indigo-700 border-indigo-200";
    if (row.editable) return "bg-blue-100 text-blue-700 border-blue-200";
    return "bg-slate-100 text-slate-600 border-slate-200";
  }

  function renderCalculatedResultsSection(calcData) {
    const calcSection = document.getElementById("calculated-results-section");
    const calcHead = document.getElementById("calc-head-tr");
    const calcBody = document.getElementById("calc-body-rows");
    if (!calcSection || !calcHead || !calcBody || !state.workbook) return;

    const currentFormId = state.workbook.selected_form.id;
    const calcFields = (calcData.fields || []).filter(f => String(f.form_id) === String(currentFormId));
    
    if (calcFields.length === 0 || state.selectedFormId === "calc_results") {
      calcSection.classList.add("hidden");
      return;
    }

    calcSection.classList.remove("hidden");

    const getMonthName = (m) => {
      const months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      return months[parseInt(m, 10)] || "";
    };

    calcHead.innerHTML = `
      <th class="border border-slate-300 px-3 py-2 text-left bg-navy text-white w-[100px] min-w-[100px] max-w-[100px]">Month</th>
      ${calcFields.map(field => `
        <th class="border border-slate-300 px-3 py-2 text-left bg-navy text-white min-w-[180px]">
          <div class="font-bold">${escapeHtml(field.field_name.split(" (")[0])}</div>
          ${field.field_config && field.field_config.unit ? `<div class="text-[10px] text-slate-300 font-semibold normal-case">${escapeHtml(field.field_config.unit)}</div>` : ""}
        </th>
      `).join("")}
    `;

    const rows = calcData.rows || [];
    calcBody.innerHTML = rows.map(row => {
      const isApproved = row.submission_status === "Approved" || row.is_locked;
      const rowClass = row.is_active_period 
        ? "bg-white font-semibold active-reporting-row" 
        : isApproved 
          ? "bg-[#eef3fa]/50 opacity-85 text-slate-500"
          : "bg-slate-50";

      const status = row.submission_status || row.status || row.period_status || "Not Started";
      let monthBgClass = "";
      let lockSuffix = "";
      if (row.is_active_period) {
        monthBgClass = "bg-white text-[#1f2937] border-l-[3px] border-l-[#1a3a6b]";
      } else if (status === "Approved") {
        monthBgClass = "bg-[#e6f4ea] text-[#1f2937] border-l-4 border-l-[#137333]";
        lockSuffix = " 🔒";
      } else if (row.is_locked || status === "Locked") {
        monthBgClass = "bg-[#f1f3f4] text-[#1f2937] border-l-4 border-l-[#5f6368]";
        lockSuffix = " 🔒";
      } else if (["Submitted", "Resubmitted", "Under Review"].includes(status)) {
        monthBgClass = "bg-[#f3e8ff] text-[#1f2937] border-l-4 border-l-[#7000af]";
      } else if (status === "Changes Requested" || status === "Rejected" || status === "Changes requested") {
        if (status === "Rejected") {
          monthBgClass = "bg-[#fff7ed] text-[#1f2937] border-l-4 border-l-[#ea580c]";
        } else {
          monthBgClass = "bg-[#fce8e6] text-[#1f2937] border-l-4 border-l-[#c5221f]";
        }
      } else if (status === "Draft") {
        monthBgClass = "bg-[#e6fffa] text-[#1f2937] border-l-4 border-l-[#007a78]";
      } else if (!row.period_id || row.period_status === "LOCKED") {
        monthBgClass = "bg-[#f8f9fa] text-[#1f2937] opacity-60 border-l-4 border-l-[#70757a]";
      } else {
        monthBgClass = "bg-white text-[#1f2937] border-l-4 border-l-slate-300";
      }

      return `
        <tr class="${rowClass} border-b border-slate-200">
          <td class="w-[100px] min-w-[100px] max-w-[100px] border border-slate-300 month-cell ${monthBgClass}">${escapeHtml(row.label || getMonthName(row.month) || row.period_label)}${lockSuffix}</td>
          ${calcFields.map(field => {
            const cell = row.values ? row.values[field.field_code] : null;
            if (!cell) {
              return `<td class="border border-slate-300 px-3 py-2.5 text-slate-400 italic bg-slate-100/50 min-w-[180px]">—</td>`;
            }
            if (cell.status === "not_configured") {
              return `<td class="border border-slate-300 px-3 py-2.5 text-slate-400 italic bg-slate-100/50 min-w-[180px]">Not configured</td>`;
            }
            if (cell.status === "missing_input") {
              const warningText = Array.isArray(cell.warnings) ? cell.warnings.join(" | ") : "Missing input";
              return `
                <td class="border border-slate-300 px-3 py-2.5 text-slate-500 bg-slate-100/50 min-w-[180px]">
                  <div class="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 px-2 py-1">${escapeHtml(warningText)}</div>
                </td>
              `;
            }
            if (cell.status === "evaluation_error") {
              const warningText = Array.isArray(cell.warnings) ? cell.warnings.join(" | ") : "Error";
              return `
                <td class="border border-slate-300 px-3 py-2.5 text-rose-700 bg-rose-50/50 min-w-[180px]">
                  <div class="text-[11px] font-semibold">${escapeHtml(warningText)}</div>
                </td>
              `;
            }
            
            const val = cell.reportable_value !== null ? cell.reportable_value : cell.preview_value;
            const displayVal = val !== null ? val : "—";
            const badge = cell.status === "calculable"
              ? `<span class="inline-flex items-center rounded bg-emerald-50 px-1 py-0.5 text-[9px] font-bold text-emerald-600 border border-emerald-100">Approved</span>`
              : `<span class="inline-flex items-center rounded bg-blue-50 px-1 py-0.5 text-[9px] font-bold text-blue-600 border border-blue-100">Preview</span>`;
              
            return `
              <td class="border border-slate-300 px-3 py-2.5 font-semibold text-slate-900 bg-slate-50 min-w-[180px]">
                <div class="flex items-center justify-between gap-2">
                  <span>${escapeHtml(displayVal)}</span>
                  ${badge}
                </div>
              </td>
            `;
          }).join("")}
        </tr>
      `;
    }).join("");


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

    const field = state.workbook.fields.find(f => f.field_code === input.dataset.fieldCode);
    if (field && window.WorkbookSheet.isFieldNonMonthly(field, state.workbook)) return;

    if (!row.values) row.values = {};
    row.values[input.dataset.fieldCode] = input.type === "checkbox" ? input.checked : input.value;
    state.selectedRowKey = input.dataset.rowKey;
    state.dirtyRows.add(input.dataset.rowKey);
    const cell = input.closest("td[data-field-code]");
    if (cell) {
      const rawValue = input.type === "checkbox" ? input.checked : input.value;
      const visualState = rawValue === "" || rawValue === null || rawValue === undefined ? "blank_editable" : "draft_filled";
      cell.dataset.cellState = visualState;
      cell.title = `${visualState === "draft_filled" ? "Draft saved" : "Blank editable"}${cell.dataset.hasIssues === "true" ? " · Issue/comment exists" : ""}`;
    }
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
    const [optsRes, sheetsRes] = await Promise.all([
      fetch("/module/SUBMIT/api/annual-workbook/options"),
      fetch("/module/SUBMIT/api/sheets")
    ]);
    if (!optsRes.ok) throw new Error("Could not load assigned sites and sheets.");
    state.options = await optsRes.json();
    state.dashboardData = sheetsRes.ok ? await sheetsRes.json() : null;

    renderFyOptions();
    renderSiteOptions();

    const hasRequestedContext = Boolean(state.requestedSiteId && state.requestedWorkbookId);
    const hasAnyWorkbook = Object.values(state.options.workbooks_by_site || {}).some(items => Array.isArray(items) && items.length);
    if (!state.options.sites.length || !hasAnyWorkbook) {
      if (hasRequestedContext) {
        setEmpty(
          "You are not assigned to this workbook for this site.",
          "Ask an admin to add you as a submitter for this workbook/site."
        );
      } else {
        setEmpty(
          "No annual workbook is available.",
          "Ask an admin to assign you as a submitter for a workbook and site."
        );
      }
      return;
    }

    if (!state.requestedWorkbookId) {
      setEmpty(
        "Missing workbook context.",
        "Open this workbook from My Workbooks so the workbook link includes a workbook ID."
      );
      return;
    }

    const requestedSite = state.options.sites.find(site => parseInt(site.id) === state.requestedSiteId);
    if (state.requestedSiteId && !requestedSite) {
      setEmpty(
        "You are not assigned to this workbook for this site.",
        "Ask an admin to add you as a submitter for this workbook/site."
      );
      return;
    }
    state.selectedSiteId = requestedSite
      ? requestedSite.id
      : (state.options.sites[0] ? state.options.sites[0].id : null);
    const workbooks = workbooksForSelectedSite();
    const requestedWorkbook = workbooks.find(workbook => parseInt(workbook.id || workbook.workbook_id) === state.requestedWorkbookId);
    if (!requestedWorkbook) {
      setEmpty(
        "You are not assigned to this workbook for this site.",
        "Ask an admin to add you as a submitter for this workbook/site."
      );
      return;
    }
    state.selectedWorkbookId = requestedWorkbook
      ? (requestedWorkbook.id || requestedWorkbook.workbook_id)
      : (workbooks[0] ? (workbooks[0].id || workbooks[0].workbook_id) : null);
    const firstForms = formsForSelectedSite();
    const requestedForm = firstForms.find(form => parseInt(form.id) === state.requestedFormId);
    state.selectedFormId = requestedForm
      ? requestedForm.id
      : (firstForms[0] ? firstForms[0].id : null);
    renderSiteOptions();
    renderFormTabs();
    await loadWorkbook();
  }

  async function loadWorkbook() {
    hideAlert();
    const previousRowKey = state.selectedRowKey;
    state.workbook = null;
    state.calculationResults = null;
    state.dirtyRows.clear();
    state.dirtyWorkbookFields.clear();
    renderFormTabs();
    renderHeader();

    const forms = formsForSelectedSite();
    if (!state.selectedSiteId) {
      setEmpty("No assigned sites", "You do not have site access for submissions.");
      return;
    }
    if (!state.selectedWorkbookId) {
      setEmpty("No assigned workbooks", "Published workbooks assigned to you for this site will appear from My Workbooks.");
      return;
    }
    if (!forms.length && state.selectedFormId !== "calc_results") {
      setEmpty("No sheets assigned", "Published sheets assigned to this site will appear as tabs.");
      return;
    }
    if (!state.selectedFormId) {
      state.selectedFormId = forms[0] ? forms[0].id : "calc_results";
    }

    let wbUrl = "";
    let calcUrl = `/module/SUBMIT/api/annual-workbook/calculation-results?site_id=${state.selectedSiteId}&workbook_id=${state.selectedWorkbookId}&fy=${state.selectedFy}`;
    
    if (state.selectedFormId === "calc_results") {
      wbUrl = calcUrl;
    } else {
      wbUrl = `/module/SUBMIT/api/annual-workbook?site_id=${state.selectedSiteId}&workbook_id=${state.selectedWorkbookId}&form_id=${state.selectedFormId}&fy=${state.selectedFy}`;
    }

    const [wbRes, calcRes] = await Promise.all([
      fetch(wbUrl),
      fetch(calcUrl)
    ]);
    
    const wbData = await parseJsonResponse(wbRes, "Could not load annual workbook.");
    if (!wbRes.ok) {
      const message = wbData.error || "Could not load annual workbook.";
      setEmpty("Could not load annual workbook.", message);
      showAlert(message, "error");
      return;
    }

    state.workbook = wbData;
    state.calculationResults = calcRes.ok ? await calcRes.json() : null;

    const requestedRow = state.requestedMonth
      ? wbData.rows.find(row => parseInt(row.month) === state.requestedMonth)
      : null;
    const previousRow = previousRowKey
      ? wbData.rows.find(row => rowKey(row) === previousRowKey)
      : null;
    state.selectedRowKey = requestedRow
      ? rowKey(requestedRow)
      : (previousRow ? rowKey(previousRow) : (wbData.rows[0] ? rowKey(wbData.rows[0]) : null));
    
    renderTable();
    if (state.calculationResults) {
      renderCalculatedResultsSection(state.calculationResults);
    }
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
            workbook_id: state.workbook.workbook.id,
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
              workbook_id: state.workbook.workbook.id,
              form_id: state.workbook.selected_form.id,
              reporting_period_id: row.period_id
            })
          });
          const createData = await parseJsonResponse(createResponse, "Could not create draft.");
          if (createResponse.status === 409 && createData.existing_id) {
            submissionId = createData.existing_id;
          } else if (!createResponse.ok) {
            throw new Error(createData.error || "Could not create draft.");
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
      
      // Reload calculations results to update calculated section
      const calcUrl = `/module/SUBMIT/api/annual-workbook/calculation-results?site_id=${state.selectedSiteId}&workbook_id=${state.selectedWorkbookId}&fy=${state.selectedFy}`;
      const calcRes = await fetch(calcUrl);
      state.calculationResults = calcRes.ok ? await calcRes.json() : null;

      renderTable();
      if (state.calculationResults) {
        renderCalculatedResultsSection(state.calculationResults);
      }
      renderHeader();
    } catch (error) {
      showAlert(error.message, "error");
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
          workbook_id: state.workbook.workbook.id,
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
      
      // Update sheets status dots data
      const sheetsRes = await fetch("/module/SUBMIT/api/sheets");
      state.dashboardData = sheetsRes.ok ? await sheetsRes.json() : null;
      
      await loadWorkbook();
    } catch (error) {
      showAlert(error.message, "error");
    } finally {
      const sheetName = state.workbook ? state.workbook.selected_form.name : "Sheet";
      btnSubmit.textContent = `Submit ${sheetName}`;
      renderHeader();
    }
  }

  // Handle hidden file uploader programmatical changes
  const inlineUploader = document.getElementById("inline-file-uploader");
  if (inlineUploader) {
    inlineUploader.addEventListener("change", async function () {
      const file = inlineUploader.files[0];
      if (!file || !state.workbook) return;

      const rowKeyVal = inlineUploader.dataset.targetRowKey;
      const fieldCode = inlineUploader.dataset.targetFieldCode;
      const row = state.workbook.rows.find(r => rowKey(r) === rowKeyVal);
      if (!row) return;

      try {
        showAlert("Uploading proof document...", "info");
        
        let submissionId = row.submission_id;
        if (!submissionId) {
          if (!row.period_id) {
            throw new Error("A reporting period must exist before a document can be uploaded.");
          }
          const createResponse = await fetch("/module/SUBMIT/api/submissions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              site_id: state.workbook.site.id,
              workbook_id: state.workbook.workbook.id,
              form_id: state.workbook.selected_form.id,
              reporting_period_id: row.period_id
            })
          });
          const createData = await parseJsonResponse(createResponse, "Could not create draft.");
          if (createResponse.status === 409 && createData.existing_id) {
            submissionId = createData.existing_id;
          } else if (!createResponse.ok) {
            throw new Error(createData.error || "Could not create draft.");
          } else {
            submissionId = createData.data.submission_id;
          }
          row.submission_id = submissionId;
          row.submission_status = "Draft";
        }

        const formData = new FormData();
        formData.append("file", file);

        const uploadResponse = await fetch(`/module/SUBMIT/api/submissions/${submissionId}/proof/${fieldCode}`, {
          method: "POST",
          body: formData
        });
        const uploadData = await parseJsonResponse(uploadResponse, "Could not upload file.");
        if (!uploadResponse.ok) {
          throw new Error(uploadData.error || "Could not upload file.");
        }

        showAlert("Proof uploaded successfully.", "success");
        
        // Refresh workbook data
        await loadWorkbook();
      } catch (error) {
        showAlert(error.message, "error");
      }
    });
  }

  siteSelect.addEventListener("change", function () {
    state.selectedSiteId = siteSelect.value;
    const workbooks = workbooksForSelectedSite();
    state.selectedWorkbookId = workbooks[0] ? (workbooks[0].id || workbooks[0].workbook_id) : null;
    state.workbook = null;
    const forms = formsForSelectedSite();
    state.selectedFormId = forms[0] ? forms[0].id : null;
    renderSiteOptions();
    loadWorkbook().catch(error => showAlert(error.message, "error"));
  });

  fySelect.addEventListener("change", function () {
    state.selectedFy = parseInt(fySelect.value, 10);
    loadWorkbook().catch(error => showAlert(error.message, "error"));
  });

  btnSave.addEventListener("click", async function() {
    await saveSelectedRow();
    showAlert("Workbook draft saved.", "success");
  });
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
