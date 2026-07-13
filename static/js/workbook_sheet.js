(function () {
  const CELL_STATE_META = {
    blank_editable: { label: "Blank editable", className: "bg-white text-slate-600 border-slate-200" },
    draft_filled: { label: "Draft saved", className: "bg-blue-50 text-blue-700 border-blue-200" },
    submitted: { label: "Submitted for review", className: "bg-indigo-50 text-indigo-700 border-indigo-200" },
    approved_locked: { label: "Approved and locked", className: "bg-slate-100 text-slate-600 border-slate-200" },
    changes_requested: { label: "Changes requested", className: "bg-rose-50 text-rose-700 border-rose-200" },
    late_entry: { label: "Late entry", className: "bg-violet-50 text-violet-700 border-violet-200" },
  };

  const escapeHtml = window.UIHelpers.escapeHtml;

  function getMonthName(month) {
    const months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return months[parseInt(month, 10)] || "";
  }

  function getFullMonthYear(month, year) {
    const full = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    const name = full[parseInt(month, 10)] || "";
    return year ? name + " " + year : name;
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

  function cellStateLabel(state) {
    const meta = CELL_STATE_META[state] || { label: state || "Unknown" };
    return meta.label;
  }

  function cellStateTitle(state, rowLocked, issues, extraParts) {
    const parts = [cellStateLabel(state)];
    if (Array.isArray(extraParts)) {
      extraParts.filter(Boolean).forEach(part => parts.push(part));
    }
    if (rowLocked) parts.push("Locked period");
    if (issues && issues.length) parts.push("Issue/comment exists");
    return parts.join(" · ");
  }

  function getRowStatusState(row) {
    const status = row.submission_status || row.status || row.period_status || "Not Started";
    if (status === "Approved") return "approved";
    if (row.is_locked || status === "Locked") return "locked";
    if (["Submitted", "Resubmitted", "Under Review"].includes(status)) return "submitted";
    if (status === "Rejected") return "rejected";
    if (status === "Changes Requested" || status === "Changes requested") return "changes_requested";
    if (status === "Draft") return "draft";
    if (!row.period_id) return "not_open";
    if (row.period_status === "LOCKED") return "not_open";
    if (row.period_status === "SUBMISSION_CLOSED") return "not_open";
    if (row.period_status === "OPEN") return "not_started";
    return "not_started";
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

    if (fieldType === "calculated") {
      const unit = field.unit || (field.field_config && field.field_config.unit) || "";
      if (value === "") return '<span class="workbook-calc-empty">—</span>';
      return unit
        ? `${escapeHtml(value)} <span class="text-xs text-slate-400">${escapeHtml(unit)}</span>`
        : escapeHtml(value);
    }

    if (value === "") return '<span class="text-slate-400">—</span>';
    return escapeHtml(value);
  }

  function inputClass(disabled) {
    return [
      "workbook-cell-control",
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
    const config = field && field.field_config ? field.field_config : {};
    if (
      config.field_scope === "annual_result" ||
      config.result_role === "aggregate_result" ||
      config.result_role === "formula_result" ||
      config.display_region === "below_monthly_table" ||
      config.display_region === "under_input_column"
    ) {
      return true;
    }
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

  // annual setup fields are read-only monthly grid fields edited below
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
    if (options.mode === "calc_results") {
      const cell = cellObject(row, field);
      if (!cell) {
        return `<td class="border px-3 py-3 bg-slate-50 text-slate-400 text-xs text-center italic" title="No calculated value">—</td>`;
      }
      if (cell.status === "not_configured") {
        return `
          <td class="border px-3 py-2 bg-slate-100 text-slate-400 text-xs align-top" title="Not configured for this period">
            <div class="font-semibold text-slate-500">Not configured</div>
          </td>
        `;
      }
      if (cell.status === "missing_input") {
        return `
          <td class="border px-3 py-2 bg-slate-50 text-slate-500 text-xs align-top" title="Missing input">
            <div class="text-slate-400 font-bold">—</div>
            ${Array.isArray(cell.warnings) ? cell.warnings.map(w => `<div class="mt-1 text-[10px] text-amber-600 bg-amber-50 px-1 py-0.5 rounded border border-amber-100 w-max max-w-[200px] whitespace-normal" title="${escapeHtml(w)}">${escapeHtml(w)}</div>`).join("") : ""}
          </td>
        `;
      }
      if (cell.status === "pending_approval" || cell.status === "preview_only") {
        const valPreview = cell.preview_value !== null ? `${cell.preview_value} ${field.field_config && field.field_config.unit ? escapeHtml(field.field_config.unit) : ""}` : "—";
        return `
          <td class="border px-3 py-2 bg-blue-50/20 text-xs align-top" title="${cell.status === "pending_approval" ? "Submitted for review" : "Preview only"}">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="font-bold text-blue-700 text-sm">${escapeHtml(valPreview)}</span>
              <span class="inline-flex items-center rounded bg-blue-50 px-1 py-0.5 text-[9px] font-bold text-blue-600 border border-blue-100">Preview</span>
            </div>
            <div class="mt-1 text-[10px] text-slate-500">
              Reportable: <span class="italic text-slate-400">— (unapproved)</span>
            </div>
            ${Array.isArray(cell.warnings) ? cell.warnings.map(w => `<div class="mt-1 text-[10px] text-amber-600 bg-amber-50 px-1 py-0.5 rounded border border-amber-100 w-max max-w-[200px] whitespace-normal" title="${escapeHtml(w)}">${escapeHtml(w)}</div>`).join("") : ""}
          </td>
        `;
      }
      if (cell.status === "calculable") {
        const valReportable = cell.reportable_value !== null ? `${cell.reportable_value} ${field.field_config && field.field_config.unit ? escapeHtml(field.field_config.unit) : ""}` : "—";
        return `
          <td class="border px-3 py-2 bg-emerald-50/20 text-xs align-top" title="Calculated field">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="font-bold text-emerald-700 text-sm">${escapeHtml(valReportable)}</span>
              <span class="inline-flex items-center rounded bg-emerald-50 px-1 py-0.5 text-[9px] font-bold text-emerald-600 border border-emerald-100">Approved</span>
            </div>
            <div class="mt-1 text-[10px] text-slate-500">
              Reportable: <span class="font-semibold text-slate-700">${escapeHtml(valReportable)}</span>
            </div>
          </td>
        `;
      }
      if (cell.status === "evaluation_error") {
        return `
          <td class="border px-3 py-2 bg-rose-50/50 text-xs align-top" title="Evaluation error">
            <div class="font-bold text-rose-700">Calculation error</div>
            ${Array.isArray(cell.warnings) ? cell.warnings.map(w => `<div class="mt-1 text-[10px] text-rose-600 bg-rose-50 px-1 py-0.5 rounded border border-rose-100 w-max max-w-[200px] whitespace-normal" title="${escapeHtml(w)}">${escapeHtml(w)}</div>`).join("") : ""}
          </td>
        `;
      }
      return `<td class="border px-3 py-3 bg-slate-50 text-slate-400 text-xs text-center italic" title="No calculated value">—</td>`;
    }

    const rowLocked = row.is_locked || row.submission_status === "Approved";
    const editable = options.mode === "entry" && row.editable && !cellLocked(row, field) && !rowLocked;
    const fieldType = normalizedFieldType(field);
    const disabled = !editable || fieldType === "calculated" || fieldType === "file";
    const state = cellState(row, field);
    const proof = proofFor(row, field);
    const issues = cellIssues(row, field);
    const valueId = submissionValueId(row, field);
    const openHandler = options.onCellOpen || options.onIssueClick;
    const canOpen = typeof openHandler === "function";

    let stateClass = (CELL_STATE_META[state] || CELL_STATE_META.blank_editable).className;
    if (state === "late_entry") {
      stateClass += " border-dashed";
    }
    if (issues.length && state !== "changes_requested") {
      stateClass += " border-l-2 border-l-[#c8102e]";
    }

    const interactiveClass = canOpen && options.mode !== "entry"
      ? "cursor-pointer hover:ring-2 hover:ring-indigo-200"
      : "";
    const stateTitle = cellStateTitle(
      state,
      rowLocked,
      issues,
      disabled && fieldType === "calculated" ? ["Calculated field"] : []
    );
    const calcCellClass = fieldType === "calculated" ? " workbook-cell-calculated" : "";

    return `
      <td class="border align-top ${stateClass} ${interactiveClass}${calcCellClass}" data-cell-state="${escapeHtml(state)}" data-has-issues="${issues.length ? "true" : "false"}" data-row-locked="${rowLocked ? "true" : "false"}" data-submission-value-id="${valueId ? escapeHtml(valueId) : ""}" data-field-code="${escapeHtml(field.field_code)}" title="${escapeHtml(stateTitle)}">
        <div class="relative min-h-[48px]">
          ${issues.length ? '<span class="absolute right-1 top-1 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-white" data-cell-open="true" title="Cell has issues/comments"></span>' : ""}
          ${proof && fieldType !== "file" ? '<span class="absolute bottom-1 left-1 h-1.5 w-1.5 rounded-full bg-indigo-500" title="Proof attached"></span>' : ""}
          <div class="${issues.length || rowLocked ? "pr-5" : "pr-2"}">
            ${editable
              ? renderEditableControl(field, row, disabled, options)
              : `<div class="px-2 py-2 text-sm text-slate-800 font-medium">${formatReadonlyValue(field, row)}</div>`}
          </div>
        </div>
      </td>
    `;
  }

  function renderRemarksCell(row, fileField, options) {
    const key = rowKey(row);
    const proof = fileField ? proofFor(row, fileField) : null;
    const rowLocked = row.is_locked || row.submission_status === "Approved";

    let content = "";
    if (fileField) {
      if (proof && proof.storage_key) {
        content = `
          <div class="flex flex-col gap-1.5">
            <div class="flex items-center gap-1.5 text-xs text-emerald-700 font-bold">
              <span>✓ Proof</span>
              ${!rowLocked ? `<a href="#" class="text-indigo-600 hover:text-indigo-800 hover:underline trigger-upload" data-row-key="${escapeHtml(key)}" data-field-code="${escapeHtml(fileField.field_code)}">Replace</a>` : ""}
            </div>
            <a href="/module/SUBMIT/submissions/download/${encodeURIComponent(proof.storage_key)}" class="text-[11px] text-slate-500 truncate max-w-[150px] font-semibold hover:underline" title="${escapeHtml(proof.original_name)}">
              ${escapeHtml(proof.original_name)}
            </a>
          </div>
        `;
      } else {
        content = rowLocked
          ? '<span class="text-slate-400 italic">No proof</span>'
          : `<button type="button" class="text-indigo-600 hover:text-indigo-800 font-bold text-xs flex items-center gap-1 trigger-upload" data-row-key="${escapeHtml(key)}" data-field-code="${escapeHtml(fileField.field_code)}">
              <span>📤 Upload</span>
             </button>`;
      }
    } else {
      content = '<span class="text-slate-400">—</span>';
    }

    return `
      <td class="w-[140px] min-w-[140px] max-w-[140px] border align-middle bg-slate-50/50">
        ${content}
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
    let stateClass = (CELL_STATE_META[state] || CELL_STATE_META.blank_editable).className;
    if (state === "late_entry") {
      stateClass += " border-dashed";
    }
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
        <td colspan="${options.totalColumns || 3}" class="border border-slate-200 px-4 py-4">
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

  function aggregateOperandNames(expression) {
    const source = expression || "";
    const names = new Set();
    const pattern = /\bSUM_MONTHS\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)/g;
    let match;
    while ((match = pattern.exec(source)) !== null) {
      names.add(match[1]);
    }
    return Array.from(names);
  }

  function formatSheetResultValue(result) {
    if (!result || result.value === null || result.value === undefined || result.value === "") {
      return "—";
    }
    const numeric = Number(result.value);
    const value = Number.isFinite(numeric)
      ? numeric.toLocaleString("en-IN", { maximumFractionDigits: 6 })
      : String(result.value);
    return result.unit ? `${value} ${result.unit}` : value;
  }

  function normalizeFieldCode(code) {
    return String(code || "").trim().toLowerCase();
  }

  function splitSheetResults(sheetResults) {
    // All sheet results render in the column footer; overflow strip is unused.
    return { footerResults: sheetResults || [], overflowResults: [] };
  }

  function renderSheetResultFooterCell(result, showLabel) {
    const calculated = result.status === "calculated";
    const partial = result.status === "partial";
    // Partial keeps the same navy identity as a full "calculated" result
    // (it's a real, trustworthy number, just not from every month yet) but
    // at a lighter weight so it doesn't read as a settled final total.
    const valueClass = calculated
      ? "text-[#1a3a6b] font-bold"
      : partial
        ? "text-[#1a3a6b] font-medium"
        : "text-slate-400";
    const statusClass = calculated
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : partial
        ? "border-blue-200 bg-blue-50 text-blue-700"
        : result.status === "not_configured"
          ? "border-rose-200 bg-rose-50 text-rose-700"
          : "border-amber-200 bg-amber-50 text-amber-700";
    const statusLabel = calculated
      ? "Calculated"
      : partial
        ? "Partial"
        : result.status === "not_configured"
          ? "Not configured"
          : "Needs input";
    // The fraction lives in the badge for a partial result ("PARTIAL · 7/12")
    // instead of repeating three times across the card -- next to the value,
    // in the badge, and again as a full sentence. A full "calculated" result
    // never shows a fraction since 12/12 is implied.
    const badgeText = partial && result.months_total
      ? `${statusLabel} · ${result.months_entered}/${result.months_total}`
      : statusLabel;
    // Full detail (the "7 of 12 months entered." sentence, plus whatever
    // else the result carries) moves to a hover tooltip instead of staying
    // permanently visible on the card.
    const tooltipParts = [statusLabel];
    if (result.message) tooltipParts.push(result.message);
    const tooltipTitle = escapeHtml(tooltipParts.join(" · "));
    return `
      <div class="px-2 py-1.5 text-right" title="${tooltipTitle}">
        ${showLabel ? `<div class="mb-0.5 truncate text-[10px] font-semibold uppercase tracking-wide text-slate-500">${escapeHtml(result.label || result.field_code || "Result")}</div>` : ""}
        <div class="tabular-nums text-sm ${valueClass}">${escapeHtml(formatSheetResultValue(result))}</div>
        <div class="mt-1 flex justify-end">
          <span class="whitespace-nowrap rounded-full border px-1.5 py-0.5 text-[9px] font-bold uppercase ${statusClass}">${escapeHtml(badgeText)}</span>
        </div>
        ${result.message && !partial ? `<div class="mt-1 text-left text-[10px] font-medium text-amber-700">${escapeHtml(result.message)}</div>` : ""}
      </div>
    `;
  }

  function renderSheetResultFooter(displayFields, sheetResults, options) {
    const allResults = Array.isArray(sheetResults) ? sheetResults : [];
    if (!allResults.length) return "";

    const isCalcMode = options.mode === "calc_results";
    const fieldByCode = {};
    displayFields.forEach((field) => {
      fieldByCode[normalizeFieldCode(field.field_code)] = field;
    });

    // "below_monthly_table" results (explicit, multi-source combined totals
    // like TOTAL NON COASTAL) never belong to a single column -- they always
    // render in their own dedicated row below, regardless of how many source
    // fields they touch or whether the first one alphabetically/positionally
    // happens to match a display column. Everything else ("under_input_column",
    // covering both manual per-field totals and every automatic one) aggregates
    // exactly one source field by construction, so it's safe to bucket by column.
    const combinedResults = allResults.filter((result) => result.display_region === "below_monthly_table");
    const perColumnResults = allResults.filter((result) => result.display_region !== "below_monthly_table");

    // Each column now holds at most one result, so no per-result label is
    // needed -- the column header above it already identifies the field.
    const showLabels = false;

    const resultsBySource = {};
    perColumnResults.forEach((result) => {
      const sourceCodes = Array.isArray(result.source_field_codes) && result.source_field_codes.length
        ? result.source_field_codes
        : [];
      const primarySource = sourceCodes[0];
      if (!primarySource) return;
      const key = normalizeFieldCode(primarySource);
      if (!resultsBySource[key]) resultsBySource[key] = [];
      resultsBySource[key].push(result);
    });

    // Still possible for a per-field result: a legacy manually-built
    // under-input-column field with no formula attached yet has no source
    // field code at all, so it can't be placed under any column.
    const unmappedResults = perColumnResults.filter((result) => {
      const sourceCodes = Array.isArray(result.source_field_codes) ? result.source_field_codes : [];
      if (!sourceCodes.length) return true;
      return !fieldByCode[normalizeFieldCode(sourceCodes[0])];
    });

    return `
      <tr class="sheet-aggregate-row bg-slate-100 border-t-2 border-slate-300">
        <td class="sticky left-0 z-10 border border-slate-200 bg-slate-200 px-3 py-2 text-xs font-bold uppercase tracking-wide text-slate-700">
          FY total
        </td>
        ${displayFields.map((field) => {
          const columnResults = resultsBySource[normalizeFieldCode(field.field_code)] || [];
          if (!columnResults.length) {
            return `<td class="border border-slate-200 bg-slate-50 align-top"></td>`;
          }
          return `<td class="border border-slate-200 bg-slate-50 align-top">${columnResults.map((result) => renderSheetResultFooterCell(result, showLabels)).join("")}</td>`;
        }).join("")}
        ${!isCalcMode ? '<td class="border border-slate-200 bg-slate-50"></td>' : ""}
      </tr>
      ${combinedResults.length ? `
        <tr class="sheet-aggregate-row bg-slate-50 border-t border-slate-200">
          <td colspan="${displayFields.length + (isCalcMode ? 1 : 2)}" class="border border-slate-200 px-4 py-3">
            <div class="mb-2 text-[10px] font-bold uppercase tracking-wide text-slate-600">Combined totals</div>
            <div class="flex flex-wrap gap-4">
              ${combinedResults.map((result) => `
                <div class="min-w-[160px] rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm">
                  ${renderSheetResultFooterCell(result, true)}
                </div>
              `).join("")}
            </div>
          </td>
        </tr>
      ` : ""}
      ${unmappedResults.length ? `
        <tr class="sheet-aggregate-row bg-amber-50/80 border-t border-amber-200">
          <td colspan="${displayFields.length + (isCalcMode ? 1 : 2)}" class="border border-amber-200 px-4 py-3">
            <div class="mb-2 text-[10px] font-bold uppercase tracking-wide text-amber-800">Sheet results (no matching column)</div>
            <div class="flex flex-wrap gap-4">
              ${unmappedResults.map((result) => `
                <div class="min-w-[160px] rounded-lg border border-amber-200 bg-white px-3 py-2 shadow-sm">
                  ${renderSheetResultFooterCell(result, true)}
                </div>
              `).join("")}
            </div>
          </td>
        </tr>
      ` : ""}
    `;
  }

  function renderSheetResultsOverflowHtml(sheetResults) {
    const { overflowResults } = splitSheetResults(sheetResults);
    if (!overflowResults.length) return "";

    return `
      <div class="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
        <div class="mb-2 text-[10px] font-bold uppercase tracking-wide text-slate-600">Sheet results</div>
        <div class="flex flex-wrap gap-x-6 gap-y-2">
          ${overflowResults.map((result) => {
            const calculated = result.status === "calculated";
            const partial = result.status === "partial";
            const valueClass = calculated
              ? "text-[#1a3a6b] font-semibold"
              : partial
                ? "text-[#1a3a6b] font-medium"
                : "text-slate-400";
            const badgeSuffix = partial && result.months_total
              ? ` (${result.months_entered}/${result.months_total})`
              : "";
            const tooltipParts = [calculated ? "Calculated" : partial ? "Partial" : (result.status || "")];
            if (result.message) tooltipParts.push(result.message);
            const tooltipTitle = escapeHtml(tooltipParts.filter(Boolean).join(" · "));
            return `
              <div class="min-w-[160px]" title="${tooltipTitle}">
                <div class="text-[10px] font-semibold uppercase tracking-wide text-slate-500">${escapeHtml(result.label || result.field_code || "Result")}${escapeHtml(badgeSuffix)}</div>
                <div class="tabular-nums text-sm ${valueClass}">${escapeHtml(formatSheetResultValue(result))}</div>
                ${result.message && !partial ? `<div class="text-[10px] text-amber-700">${escapeHtml(result.message)}</div>` : ""}
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }

  function renderFieldHeader(field, isCalcMode) {
    const isCalc = !isCalcMode && normalizedFieldType(field) === "calculated";
    const unit = field.field_config && field.field_config.unit ? escapeHtml(field.field_config.unit) : "";
    return `<th class="border border-slate-200 bg-navy text-white px-3 py-2 text-left${isCalc ? " workbook-col-calculated" : ""}">
      <div class="font-bold">${escapeHtml(field.field_name)}</div>
      <div class="mt-0.5 text-[10px] normal-case text-slate-300">
        ${unit}
        ${field.field_config && field.field_config.is_required ? '<span class="ml-1 text-rose-400">*</span>' : ""}
      </div>
    </th>`;
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

    // Redesign Spoc month table around display fields (excluding file fields; calculated fields shown inline read-only)
    const isCalcMode = options.mode === "calc_results";
    const displayFields = isCalcMode
      ? monthlyFields
      : monthlyFields.filter(f => normalizedFieldType(f) !== "file");

    const fileField = isCalcMode ? null : monthlyFields.find(f => normalizedFieldType(f) === "file");

    const getGroupColspan = (group) => {
      return group.fields.filter(f =>
        isCalcMode || normalizedFieldType(f) !== "file"
      ).length;
    };

    const activeGroups = hasSections ? monthlyGroups.filter(g => getGroupColspan(g) > 0) : [];
    const hasVisibleGroups = activeGroups.some(g => g.name.toLowerCase() !== "ungrouped");

    if (hasSections && monthlyGroups.length > 0 && hasVisibleGroups) {
      headEl.innerHTML = `
        <tr>
          <th rowspan="2" class="sticky left-0 z-20 w-[100px] min-w-[100px] max-w-[100px] border border-slate-200 bg-navy text-white px-3 py-2 text-left">Month</th>
          ${activeGroups.map((group) => {
            const isUngrouped = group.name.toLowerCase() === "ungrouped";
            return `
              <th colspan="${getGroupColspan(group)}" class="${isUngrouped ? "bg-transparent border-0" : "border border-slate-200 font-extrabold"} px-3 py-1.5 text-center tracking-wide uppercase text-xs">
                ${isUngrouped ? "" : escapeHtml(group.name)}
              </th>
            `;
          }).join("")}
          ${!isCalcMode ? '<th rowspan="2" class="w-[140px] min-w-[140px] max-w-[140px] border border-slate-200 bg-navy text-white px-3 py-2 text-left whitespace-nowrap">REMARKS</th>' : ""}
        </tr>
        <tr>
          ${displayFields.map((field) => renderFieldHeader(field, isCalcMode)).join("")}
        </tr>
      `;
    } else {
      headEl.innerHTML = `
        <tr>
          <th class="sticky left-0 z-20 w-[100px] min-w-[100px] max-w-[100px] border border-slate-200 bg-navy text-white px-3 py-2 text-left">Month</th>
          ${displayFields.map((field) => renderFieldHeader(field, isCalcMode)).join("")}
          ${!isCalcMode ? '<th class="w-[140px] min-w-[140px] max-w-[140px] border border-slate-200 bg-navy text-white px-3 py-2 text-left whitespace-nowrap">REMARKS</th>' : ""}
        </tr>
      `;
    }

    let tbodyHtml = "";
    for (let idx = 0; idx < rows.length; idx++) {
      const row = rows[idx];
      const prevRow = idx > 0 ? rows[idx - 1] : null;
      const key = rowKey(row);
      const selected = key === options.selectedRowKey;
      const status = row.submission_status || row.status || row.period_status || "Unavailable";

      let rowClass = selected ? "bg-indigo-50/60" : "bg-white hover:bg-slate-50/60";
      if (row.is_active_period && row.period_status === "OPEN") {
        rowClass = "bg-white font-semibold active-reporting-row current-month-row";
      } else if (row.submission_status === "Approved" || row.is_locked) {
        rowClass = "bg-[#eef3fa]/50 opacity-85 text-slate-500";
      }

      const rowState = getRowStatusState(row);
      let monthBgClass = "";
      let lockSuffix = "";
      if (row.is_active_period && row.period_status === "OPEN") {
        monthBgClass = "bg-white text-[#1f2937]";
      } else if (rowState === "approved") {
        monthBgClass = "bg-[#e6f4ea] text-[#1f2937] border-l-4 border-l-[#137333]";
        lockSuffix = " 🔒";
      } else if (rowState === "locked") {
        monthBgClass = "bg-[#f1f3f4] text-[#1f2937] border-l-4 border-l-[#5f6368]";
        lockSuffix = " 🔒";
      } else if (rowState === "submitted") {
        monthBgClass = "bg-[#f3e8ff] text-[#1f2937] border-l-4 border-l-[#7000af]";
      } else if (rowState === "changes_requested") {
        monthBgClass = "bg-[#fce8e6] text-[#1f2937] border-l-4 border-l-[#c5221f]";
      } else if (rowState === "rejected") {
        monthBgClass = "bg-[#fff7ed] text-[#1f2937] border-l-4 border-l-[#ea580c]";
      } else if (rowState === "draft") {
        monthBgClass = "bg-[#e6fffa] text-[#1f2937] border-l-4 border-l-[#007a78]";
      } else if (rowState === "not_open") {
        monthBgClass = "bg-[#f8f9fa] text-[#1f2937] opacity-60 border-l-4 border-l-[#70757a]";
      } else {
        monthBgClass = "bg-white text-[#1f2937] border-l-4 border-l-slate-300";
      }

      const trExtraClasses = (rowState === "not_open" ? " aw-row-not-open" : "") + ((rowState === "approved" || rowState === "locked") ? " aw-row-approved" : "");
      tbodyHtml += `
        <tr data-row-key="${escapeHtml(key)}" class="${rowClass} transition${trExtraClasses}">
          <td class="sticky left-0 z-10 align-middle month-cell ${monthBgClass}">
            ${escapeHtml(getFullMonthYear(row.month, row.year))}${lockSuffix}
          </td>
          ${displayFields.map((field) => renderCell(row, field, options)).join("")}
          ${!isCalcMode ? renderRemarksCell(row, fileField, options) : ""}
        </tr>
      `;
    }

    const sheetResults = options.sheetResults || [];
    const footerHtml = renderSheetResultFooter(displayFields, sheetResults, options);

    bodyEl.innerHTML = tbodyHtml + footerHtml + (isCalcMode ? "" : nonMonthlyGroups.map((group) => renderWorkbookValueSection(group, {
      ...options,
      totalColumns: displayFields.length + 2,
    })).join(""));

    const overflowResults = splitSheetResults(sheetResults).overflowResults;

    // Event Bindings
    bodyEl.querySelectorAll("tr[data-row-key]").forEach((tr) => {
      tr.addEventListener("click", function (event) {
        if (event.target && ["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A"].includes(event.target.tagName)) return;
        if (event.target && event.target.closest(".trigger-upload")) return;
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

    // File Upload programmatical triggers
    bodyEl.querySelectorAll(".trigger-upload").forEach(btn => {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        const uploader = document.getElementById("inline-file-uploader");
        if (uploader) {
          uploader.dataset.targetRowKey = btn.dataset.rowKey;
          uploader.dataset.targetFieldCode = btn.dataset.fieldCode;
          uploader.value = ""; // Reset file picker
          uploader.click();
        }
      });
    });

    return { overflowResults };
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
    formatSheetResultValue,
    renderSheetResultsOverflowHtml,
    splitSheetResults,
    aggregateOperandNames,
    render,
  };
})();
