(function () {
  const CELL_STATE_META = {
    blank_editable: { label: "Blank", className: "bg-slate-100 text-slate-600 border-slate-200" },
    draft_filled: { label: "Draft", className: "bg-blue-50 text-blue-700 border-blue-200" },
    submitted: { label: "Pending review", className: "bg-indigo-50 text-indigo-700 border-indigo-200" },
    approved_locked: { label: "Approved", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    changes_requested: { label: "Changes requested", className: "bg-amber-50 text-amber-700 border-amber-200" },
    late_entry: { label: "Late entry", className: "bg-violet-50 text-violet-700 border-violet-200" },
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function rowKey(row) {
    return row.row_key || `${row.year || "row"}-${row.month || row.submission_id || "0"}`;
  }

  function cellObject(row, field) {
    const values = row.values || {};
    return values[field.field_code] ?? values[String(field.field_id)] ?? values[field.field_id] ?? null;
  }

  function primitiveValue(cell) {
    if (cell && typeof cell === "object" && !Array.isArray(cell)) {
      if (cell.raw_value !== null && cell.raw_value !== undefined && cell.raw_value !== "") return cell.raw_value;
      if (cell.calculated_value !== null && cell.calculated_value !== undefined) return cell.calculated_value;
      if (cell.original_name) return cell.original_name;
      return "";
    }
    return cell ?? "";
  }

  function proofFor(row, field) {
    const proofs = row.proofs || {};
    const explicitProof = proofs[field.field_id] || proofs[String(field.field_id)] || null;
    if (explicitProof) return explicitProof;
    const cell = cellObject(row, field);
    if (cell && typeof cell === "object" && cell.storage_key) return cell;
    return null;
  }

  function cellState(row, field) {
    const cell = cellObject(row, field);
    if (cell && typeof cell === "object" && cell.cell_state) return cell.cell_state;
    if (row.is_locked || row.submission_status === "Approved") return "approved_locked";
    if (row.submission_status === "Changes Requested") return "changes_requested";
    if (["Submitted", "Resubmitted", "Under Review"].includes(row.submission_status)) return "submitted";
    if (primitiveValue(cell) !== "") return "draft_filled";
    return "blank_editable";
  }

  function cellLocked(row, field) {
    const cell = cellObject(row, field);
    return Boolean((cell && typeof cell === "object" && cell.is_locked) || row.is_locked);
  }

  function cellRemark(row, field) {
    const cell = cellObject(row, field);
    return cell && typeof cell === "object" ? cell.remark : null;
  }

  function cellIssues(row, field) {
    const cell = cellObject(row, field);
    if (cell && typeof cell === "object" && Array.isArray(cell.issues)) return cell.issues;
    const rowIssues = row.issues || {};
    const issues = rowIssues[field.field_code] || rowIssues[String(field.field_id)] || rowIssues[field.field_id];
    return Array.isArray(issues) ? issues : [];
  }

  function submissionValueId(row, field) {
    const cell = cellObject(row, field);
    if (cell && typeof cell === "object" && cell.submission_value_id) return cell.submission_value_id;
    return null;
  }

  function cellStateBadge(state) {
    const meta = CELL_STATE_META[state] || {
      label: state || "Unknown",
      className: "bg-slate-100 text-slate-600 border-slate-200",
    };
    return `<span class="inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold ${meta.className}">${escapeHtml(meta.label)}</span>`;
  }

  function cellStateLabel(state) {
    const meta = CELL_STATE_META[state] || { label: state || "Unknown" };
    return meta.label;
  }

  function formatReadonlyValue(field, row) {
    const cell = cellObject(row, field);
    const proof = proofFor(row, field);
    const fieldType = normalizedFieldType(field);

    if (fieldType === "file") {
      if (proof && proof.storage_key) {
        const href = `/module/SUBMIT/submissions/download/${encodeURIComponent(proof.storage_key)}`;
        const label = proof.original_name || "Download file";
        return `<a href="${href}" class="font-semibold text-indigo-600 hover:text-indigo-700">${escapeHtml(label)}</a>`;
      }
      return '<span class="text-slate-400">—</span>';
    }

    const value = primitiveValue(cell);
    if (fieldType === "boolean") {
      if (value === true || value === "true" || value === "1" || value === 1 || value === "on") return "Yes";
      if (value === false || value === "false" || value === "0" || value === 0) return "No";
      return '<span class="text-slate-400">—</span>';
    }

    if (value === "") return '<span class="text-slate-400">—</span>';
    return escapeHtml(value);
  }

  function inputClass(disabled) {
    return [
      "min-h-9", "w-full", "border-0", "bg-transparent", "px-2", "py-1.5",
      "text-sm", "text-slate-900", "outline-none",
      disabled
        ? "cursor-not-allowed text-slate-500"
        : "focus:bg-white focus:ring-1 focus:ring-inset focus:ring-indigo-300"
    ].join(" ");
  }

  function normalizedFrequency(field) {
    return String((field && field.frequency) || "monthly").trim().toLowerCase();
  }

  function normalizedLayoutType(section) {
    return String((section && section.layout_type) || "monthly_table").trim().toLowerCase();
  }

  function normalizedFieldType(field) {
    return String((field && field.field_type) || "").trim().toLowerCase();
  }

  function isFieldNonMonthly(field, options) {
    const frequency = normalizedFrequency(field);
    if (frequency === "annual" || frequency === "static") {
      return true;
    }
    if (options && Array.isArray(options.sections) && field.section_id) {
      const section = options.sections.find(s => s.id === field.section_id);
      const layoutType = normalizedLayoutType(section);
      if (section && (layoutType === "annual_table" || layoutType === "reference_table")) {
        return true;
      }
    }
    return false;
  }

  function isEditableWorkbookField(field, options) {
    if (normalizedFrequency(field) !== "annual") return false;
    const fieldType = normalizedFieldType(field);
    if (fieldType === "calculated" || fieldType === "file") return false;
    if (options && Array.isArray(options.sections) && field.section_id) {
      const section = options.sections.find(s => s.id === field.section_id);
      if (section && normalizedLayoutType(section) === "reference_table") return false;
    }
    return true;
  }

  function renderEditableControl(field, row, disabled, options) {
    const value = primitiveValue(cellObject(row, field));
    const isNonMonthly = isFieldNonMonthly(field, options);
    let placeholderText = "";
    if (isNonMonthly) {
      const frequency = normalizedFrequency(field);
      if (frequency === "annual") {
        placeholderText = "Annual parameter";
      } else if (frequency === "static") {
        placeholderText = "Static parameter";
      } else if (options && Array.isArray(options.sections) && field.section_id) {
        const section = options.sections.find(s => s.id === field.section_id);
        const layoutType = normalizedLayoutType(section);
        if (section && layoutType === "annual_table") {
          placeholderText = "Annual parameter";
        } else if (section && layoutType === "reference_table") {
          placeholderText = "Reference parameter";
        }
      }
      if (!placeholderText) {
        placeholderText = "Read-only parameter";
      }
    }

    const common = `data-row-key="${escapeHtml(rowKey(row))}" data-field-code="${escapeHtml(field.field_code)}" class="${inputClass(disabled)}" ${placeholderText ? `placeholder="${escapeHtml(placeholderText)}"` : ""} ${disabled ? "disabled" : ""}`;

    const fieldType = normalizedFieldType(field);
    if (fieldType === "boolean") {
      const checked = value === true || value === "true" || value === "1" || value === 1 || value === "on";
      return `<input type="checkbox" data-row-key="${escapeHtml(rowKey(row))}" data-field-code="${escapeHtml(field.field_code)}" class="h-5 w-5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}>`;
    }
    if (fieldType === "date") {
      return `<input type="date" value="${escapeHtml(value)}" ${common}>`;
    }
    if (fieldType === "dropdown") {
      const dropdownOptions = Array.isArray(field.field_config && field.field_config.options)
        ? field.field_config.options
        : [];
      return `
        <select ${common}>
          <option value="">${placeholderText ? escapeHtml(placeholderText) : "Select..."}</option>
          ${dropdownOptions.map((option) => {
            const optionValue = option.entry_code || option.code || option.value || "";
            const optionLabel = option.entry_label || option.label || optionValue;
            return `<option value="${escapeHtml(optionValue)}" ${String(value) === String(optionValue) ? "selected" : ""}>${escapeHtml(optionLabel)}</option>`;
          }).join("")}
        </select>
      `;
    }
    if (fieldType === "file") {
      const proof = proofFor(row, field);
      if (proof && proof.storage_key) {
        return formatReadonlyValue(field, row);
      }
      return row.submission_id
        ? `<a href="/module/SUBMIT/submissions/${row.submission_id}" class="px-2 py-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-700">Open monthly sheet</a>`
        : '<span class="px-2 py-1.5 text-sm text-slate-400">Create draft to upload</span>';
    }
    const type = ["number", "integer", "decimal", "float", "numeric", "calculated"].includes(fieldType) ? "number" : "text";
    return `<input type="${type}" value="${escapeHtml(value)}" ${common}>`;
  }

  function displayValueText(field, row) {
    const cell = cellObject(row, field);
    const proof = proofFor(row, field);
    const fieldType = normalizedFieldType(field);
    if (fieldType === "file" && proof) return proof.original_name || "Uploaded file";
    const value = primitiveValue(cell);
    if (fieldType === "boolean") {
      if (value === true || value === "true" || value === "1" || value === 1 || value === "on") return "Yes";
      if (value === false || value === "false" || value === "0" || value === 0) return "No";
    }
    return value === "" ? "Empty" : String(value);
  }

  function cellInfo(row, field) {
    const state = cellState(row, field);
    const issues = cellIssues(row, field);
    return {
      rowKey: rowKey(row),
      rowLabel: row.label || row.period_label || row.sheet_name || "Row",
      fieldCode: field.field_code,
      fieldId: field.field_id,
      fieldName: field.field_name,
      fieldType: field.field_type,
      submissionId: row.submission_id || null,
      submissionValueId: submissionValueId(row, field),
      value: displayValueText(field, row),
      cellState: state,
      cellStateLabel: cellStateLabel(state),
      locked: cellLocked(row, field),
      remark: cellRemark(row, field),
      issues,
    };
  }

  function renderCell(row, field, options) {
    const editable = options.mode === "entry" && row.editable && !cellLocked(row, field);
    const fieldType = normalizedFieldType(field);
    const disabled = !editable || fieldType === "calculated" || fieldType === "file";
    const state = cellState(row, field);
    const proof = proofFor(row, field);
    const issues = cellIssues(row, field);
    const valueId = submissionValueId(row, field);
    const locked = cellLocked(row, field);
    const openHandler = options.onCellOpen || options.onIssueClick;
    const canOpen = typeof openHandler === "function";
    let stateClass = {
      blank_editable: "bg-white border-slate-200",
      draft_filled: "bg-blue-50/50 border-blue-100",
      submitted: "bg-indigo-50/60 border-indigo-100",
      approved_locked: "bg-emerald-50/60 border-emerald-100",
      changes_requested: "bg-amber-50/70 border-amber-200",
      late_entry: "bg-violet-50/60 border-violet-200 border-dashed",
    }[state] || "bg-white border-slate-200";

    const interactiveClass = canOpen && options.mode !== "entry"
      ? "cursor-pointer hover:ring-2 hover:ring-indigo-200"
      : "";
    const stateTitle = `${cellStateLabel(state)}${locked ? " · Locked" : ""}${issues.length ? ` · ${issues.length} issue${issues.length === 1 ? "" : "s"}` : ""}`;

    return `
      <td class="min-w-[180px] border align-top ${stateClass} ${interactiveClass}" data-submission-value-id="${valueId ? escapeHtml(valueId) : ""}" data-field-code="${escapeHtml(field.field_code)}" title="${escapeHtml(stateTitle)}">
        <div class="relative min-h-[48px]">
          ${issues.length ? '<span class="absolute right-1 top-1 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-white" data-cell-open="true" title="Cell has issues/comments"></span>' : ""}
          ${locked ? '<span class="absolute bottom-1 right-1 rounded-sm bg-emerald-100 px-1 text-[9px] font-bold text-emerald-700" title="Locked">LOCK</span>' : ""}
          ${proof && fieldType !== "file" ? '<span class="absolute bottom-1 left-1 h-1.5 w-1.5 rounded-full bg-indigo-500" title="Proof attached"></span>' : ""}
          <div class="${issues.length || locked ? "pr-5" : "pr-2"}">
            ${options.mode === "entry"
              ? renderEditableControl(field, row, disabled, options)
              : `<div class="px-2 py-2 text-sm text-slate-800">${formatReadonlyValue(field, row)}</div>`}
          </div>
        </div>
      </td>
    `;
  }

  function renderWorkbookValueControl(field, valueObj, editable) {
    const value = primitiveValue(valueObj);
    const common = `data-workbook-field-code="${escapeHtml(field.field_code)}" class="${inputClass(!editable)}" ${editable ? "" : "disabled"}`;
    if (!editable) {
      return `<div class="px-2 py-2 text-sm text-slate-800">${value === "" ? '<span class="text-slate-400">—</span>' : escapeHtml(value)}</div>`;
    }
    const fieldType = normalizedFieldType(field);
    if (fieldType === "boolean") {
      const checked = value === true || value === "true" || value === "1" || value === 1 || value === "on";
      return `<input type="checkbox" data-workbook-field-code="${escapeHtml(field.field_code)}" class="h-5 w-5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" ${checked ? "checked" : ""}>`;
    }
    if (fieldType === "date") {
      return `<input type="date" value="${escapeHtml(value)}" ${common}>`;
    }
    const type = ["number", "integer", "decimal", "float", "numeric", "calculated"].includes(fieldType) ? "number" : "text";
    return `<input type="${type}" value="${escapeHtml(value)}" ${common}>`;
  }

  function renderWorkbookValueField(field, options) {
    const values = options.workbookValues || {};
    const valueObj = values[field.field_code] || null;
    const state = valueObj && valueObj.cell_state ? valueObj.cell_state : "blank_editable";
    const locked = Boolean(valueObj && valueObj.is_locked);
    const editable = options.mode === "entry" && Boolean(options.canEditWorkbookValues) && isEditableWorkbookField(field, options) && !locked;
    const stateClass = {
      blank_editable: "bg-white border-slate-200",
      draft_filled: "bg-blue-50/50 border-blue-100",
      submitted: "bg-indigo-50/60 border-indigo-100",
      approved_locked: "bg-emerald-50/60 border-emerald-100",
      changes_requested: "bg-amber-50/70 border-amber-200",
      late_entry: "bg-violet-50/60 border-violet-200 border-dashed",
    }[state] || "bg-white border-slate-200";
    return `
      <div class="rounded-lg border ${stateClass} p-3">
        <div class="mb-2 flex items-start justify-between gap-3">
          <div>
            <div class="text-xs font-bold uppercase tracking-wider text-slate-500">${escapeHtml(field.field_name)}</div>
            ${field.field_config && field.field_config.unit ? `<div class="mt-0.5 text-[10px] text-slate-400">${escapeHtml(field.field_config.unit)}</div>` : ""}
          </div>
          <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">${escapeHtml(field.frequency || "context")}</span>
        </div>
        ${renderWorkbookValueControl(field, valueObj, editable)}
        ${!editable && normalizedFrequency(field) !== "annual" ? '<div class="mt-2 text-xs text-slate-400">Read-only context value</div>' : ""}
      </div>
    `;
  }

  function renderWorkbookValueSection(group, options) {
    const label = group.layout_type === "annual_table"
      ? "FY-level values"
      : group.layout_type === "reference_table"
        ? "Reference/context values"
        : "Context values";
    return `
      <tr class="bg-slate-50/70">
        <td colspan="${Math.max(3, (options.monthlyColumnCount || 0) + 2)}" class="border border-slate-200 px-4 py-4">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <div class="text-sm font-bold text-slate-900">${escapeHtml(group.name)}</div>
              <div class="text-xs text-slate-500">${label}</div>
            </div>
          </div>
          <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            ${group.fields.map((field) => renderWorkbookValueField(field, options)).join("")}
          </div>
        </td>
      </tr>
    `;
  }

  function statusClass(row) {
    const status = row.submission_status || row.status || row.period_status || "Unavailable";
    if (status === "Approved") return "bg-emerald-100 text-emerald-700 border-emerald-200";
    if (status === "Changes Requested") return "bg-amber-100 text-amber-700 border-amber-200";
    if (["Submitted", "Resubmitted", "Under Review"].includes(status)) return "bg-indigo-100 text-indigo-700 border-indigo-200";
    if (row.editable) return "bg-blue-100 text-blue-700 border-blue-200";
    return "bg-slate-100 text-slate-600 border-slate-200";
  }

  function render(options) {
    const fields = options.fields || [];
    const rows = options.rows || [];
    const headEl = options.headEl;
    const bodyEl = options.bodyEl;
    if (!headEl || !bodyEl) return;

    const hasSections = Array.isArray(options.sections) && options.sections.length > 0;
    let orderedFields = [];
    let groups = [];

    if (hasSections) {
      // Group fields by section
      options.sections.forEach(section => {
        const sectionFields = fields.filter(f => f.section_id === section.id);
        if (sectionFields.length > 0) {
          groups.push({
            id: section.id,
            name: section.name,
            layout_type: section.layout_type || "monthly_table",
            fields: sectionFields.sort((a, b) => (a.display_order || 0) - (b.display_order || 0))
          });
        }
      });

      // Find any fields not in any of the active sections
      const sectionIds = new Set(options.sections.map(s => s.id));
      const ungroupedFields = fields.filter(f => !f.section_id || !sectionIds.has(f.section_id));
      if (ungroupedFields.length > 0) {
        groups.push({
          id: null,
          name: "Ungrouped",
          layout_type: "monthly_table",
          fields: ungroupedFields.sort((a, b) => (a.display_order || 0) - (b.display_order || 0))
        });
      }

      groups.forEach(g => {
        orderedFields.push(...g.fields);
      });
    } else {
      orderedFields = [...fields].sort((a, b) => (a.display_order || 0) - (b.display_order || 0));
    }

    const monthlyFields = orderedFields.filter(field => !isFieldNonMonthly(field, options));
    const nonMonthlyGroups = groups
      .map(group => ({
        ...group,
        fields: group.fields.filter(field => isFieldNonMonthly(field, options)),
      }))
      .filter(group => group.fields.length > 0);
    const monthlyGroups = groups
      .map(group => ({
        ...group,
        fields: group.fields.filter(field => !isFieldNonMonthly(field, options)),
      }))
      .filter(group => group.fields.length > 0);

    if (hasSections && monthlyGroups.length > 0) {
      headEl.innerHTML = `
        <tr>
          <th rowspan="2" class="sticky left-0 z-20 min-w-[150px] border border-slate-200 bg-slate-50 px-3 py-2 text-left">Month</th>
          <th rowspan="2" class="min-w-[160px] border border-slate-200 bg-slate-50 px-3 py-2 text-left">Status</th>
          ${monthlyGroups.map((group) => `
            <th colspan="${group.fields.length}" class="border border-slate-200 bg-slate-100 px-3 py-1.5 text-center font-extrabold text-slate-700 tracking-wide uppercase text-xs">
              ${escapeHtml(group.name)}
              ${group.layout_type !== "monthly_table" ? `<span class="ml-1.5 text-[9px] font-normal lowercase text-slate-500 bg-slate-200 px-1.5 py-0.5 rounded">(${group.layout_type.replace("_table", "")})</span>` : ""}
            </th>
          `).join("")}
        </tr>
        <tr>
          ${monthlyFields.map((field) => `
            <th class="min-w-[190px] border border-slate-200 bg-slate-50 px-3 py-2 text-left">
              <div class="font-bold text-slate-600">${escapeHtml(field.field_name)}</div>
              <div class="mt-0.5 text-[10px] normal-case text-slate-400">
                ${field.field_config && field.field_config.unit ? escapeHtml(field.field_config.unit) : ""}
                ${field.field_config && field.field_config.is_required ? '<span class="ml-1 text-rose-500">*</span>' : ""}
              </div>
            </th>
          `).join("")}
        </tr>
      `;
    } else {
      headEl.innerHTML = `
        <tr>
          <th class="sticky left-0 z-20 min-w-[150px] border border-slate-200 bg-slate-50 px-3 py-2 text-left">Month</th>
          <th class="min-w-[160px] border border-slate-200 bg-slate-50 px-3 py-2 text-left">Status</th>
          ${monthlyFields.map((field) => `
            <th class="min-w-[190px] border border-slate-200 bg-slate-50 px-3 py-2 text-left">
              <div class="font-bold text-slate-600">${escapeHtml(field.field_name)}</div>
              <div class="mt-0.5 text-[10px] normal-case text-slate-400">
                ${field.field_config && field.field_config.unit ? escapeHtml(field.field_config.unit) : ""}
                ${field.field_config && field.field_config.is_required ? '<span class="ml-1 text-rose-500">*</span>' : ""}
              </div>
            </th>
          `).join("")}
        </tr>
      `;
    }

    bodyEl.innerHTML = rows.map((row) => {
      const key = rowKey(row);
      const selected = key === options.selectedRowKey;
      const rowClass = selected ? "bg-indigo-50/60" : "bg-white hover:bg-slate-50/60";
      const status = row.submission_status || row.status || row.period_status || "Unavailable";
      return `
        <tr data-row-key="${escapeHtml(key)}" class="${rowClass} transition">
          <td class="sticky left-0 z-10 border border-slate-200 bg-inherit px-3 py-3 align-top">
            <div class="font-bold text-slate-900">${escapeHtml(row.label || row.period_label || "Row")}</div>
            <div class="text-xs text-slate-500">${escapeHtml(row.period_label || row.sheet_name || "")}</div>
          </td>
          <td class="border border-slate-200 px-3 py-3 align-top">
            <span class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClass(row)}">${escapeHtml(status)}</span>
            ${row.reason ? `<div class="mt-1 max-w-[180px] text-xs text-slate-400">${escapeHtml(row.reason)}</div>` : ""}
          </td>
          ${monthlyFields.map((field) => renderCell(row, field, options)).join("")}
        </tr>
      `;
    }).join("") + nonMonthlyGroups.map((group) => renderWorkbookValueSection(group, {
      ...options,
      monthlyColumnCount: monthlyFields.length,
    })).join("");

    bodyEl.querySelectorAll("tr[data-row-key]").forEach((tr) => {
      tr.addEventListener("click", function (event) {
        if (event.target && ["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A"].includes(event.target.tagName)) return;
        if (typeof options.onRowSelect === "function") options.onRowSelect(tr.dataset.rowKey);
      });
    });

    bodyEl.querySelectorAll("input[data-field-code], select[data-field-code], textarea[data-field-code]").forEach((input) => {
      input.addEventListener("input", options.onCellChange || function () {});
      input.addEventListener("change", options.onCellChange || function () {});
    });

    const openHandler = options.onCellOpen || options.onIssueClick;
    if (typeof openHandler === "function") {
      bodyEl.querySelectorAll("td[data-field-code]").forEach((cell) => {
        cell.addEventListener("click", function (event) {
          const tagName = event.target ? event.target.tagName : "";
          const isControl = ["INPUT", "SELECT", "TEXTAREA", "A"].includes(tagName);
          if (isControl) return;
          if (options.mode === "entry" && !event.target.closest("[data-cell-open='true']")) return;
          const rowEl = cell.closest("tr[data-row-key]");
          const row = rows.find((item) => rowKey(item) === (rowEl ? rowEl.dataset.rowKey : ""));
          const field = monthlyFields.find((item) => String(item.field_code) === String(cell.dataset.fieldCode));
          if (!row || !field) return;
          openHandler(cellInfo(row, field));
        });
      });
    }

    bodyEl.querySelectorAll("[data-workbook-field-code]").forEach((input) => {
      input.addEventListener("input", options.onWorkbookValueChange || function () {});
      input.addEventListener("change", options.onWorkbookValueChange || function () {});
    });
  }

  window.WorkbookSheet = {
    CELL_STATE_META,
    escapeHtml,
    rowKey,
    primitiveValue,
    cellStateLabel,
    cellIssues,
    isFieldNonMonthly,
    isEditableWorkbookField,
    render,
  };
})();
