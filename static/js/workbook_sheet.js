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

  function cellStateBadge(state) {
    const meta = CELL_STATE_META[state] || {
      label: state || "Unknown",
      className: "bg-slate-100 text-slate-600 border-slate-200",
    };
    return `<span class="inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold ${meta.className}">${escapeHtml(meta.label)}</span>`;
  }

  function formatReadonlyValue(field, row) {
    const cell = cellObject(row, field);
    const proof = proofFor(row, field);

    if (field.field_type === "file") {
      if (proof && proof.storage_key) {
        const href = `/module/SUBMIT/submissions/download/${encodeURIComponent(proof.storage_key)}`;
        const label = proof.original_name || "Download file";
        return `<a href="${href}" class="font-semibold text-indigo-600 hover:text-indigo-700">${escapeHtml(label)}</a>`;
      }
      return '<span class="text-slate-400">—</span>';
    }

    const value = primitiveValue(cell);
    if (field.field_type === "boolean") {
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
      "text-sm", "text-slate-900", "outline-none", "focus:ring-0",
      disabled ? "cursor-not-allowed text-slate-500" : ""
    ].join(" ");
  }

  function renderEditableControl(field, row, disabled) {
    const value = primitiveValue(cellObject(row, field));
    const common = `data-row-key="${escapeHtml(rowKey(row))}" data-field-code="${escapeHtml(field.field_code)}" class="${inputClass(disabled)}" ${disabled ? "disabled" : ""}`;

    if (field.field_type === "boolean") {
      const checked = value === true || value === "true" || value === "1" || value === 1 || value === "on";
      return `<input type="checkbox" data-row-key="${escapeHtml(rowKey(row))}" data-field-code="${escapeHtml(field.field_code)}" class="h-5 w-5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}>`;
    }
    if (field.field_type === "date") {
      return `<input type="date" value="${escapeHtml(value)}" ${common}>`;
    }
    if (field.field_type === "dropdown") {
      const options = Array.isArray(field.field_config && field.field_config.options)
        ? field.field_config.options
        : [];
      return `
        <select ${common}>
          <option value="">Select...</option>
          ${options.map((option) => {
            const optionValue = option.entry_code || option.code || option.value || "";
            const optionLabel = option.entry_label || option.label || optionValue;
            return `<option value="${escapeHtml(optionValue)}" ${String(value) === String(optionValue) ? "selected" : ""}>${escapeHtml(optionLabel)}</option>`;
          }).join("")}
        </select>
      `;
    }
    if (field.field_type === "file") {
      const proof = proofFor(row, field);
      if (proof && proof.storage_key) {
        return formatReadonlyValue(field, row);
      }
      return row.submission_id
        ? `<a href="/module/SUBMIT/submissions/${row.submission_id}" class="px-2 py-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-700">Open monthly sheet</a>`
        : '<span class="px-2 py-1.5 text-sm text-slate-400">Create draft to upload</span>';
    }
    const type = field.field_type === "number" || field.field_type === "calculated" ? "number" : "text";
    return `<input type="${type}" value="${escapeHtml(value)}" ${common}>`;
  }

  function renderCell(row, field, options) {
    const editable = options.mode === "entry" && row.editable && !cellLocked(row, field);
    const disabled = !editable || field.field_type === "calculated" || field.field_type === "file";
    const state = cellState(row, field);
    const proof = proofFor(row, field);
    const remark = cellRemark(row, field);
    const locked = cellLocked(row, field);
    const stateClass = state === "approved_locked"
      ? "bg-emerald-50/40"
      : state === "changes_requested"
        ? "bg-amber-50/60"
        : state === "submitted"
          ? "bg-indigo-50/40"
          : "bg-white";

    return `
      <td class="min-w-[180px] border border-slate-200 align-top ${stateClass}">
        <div class="relative min-h-[56px]">
          <div class="pr-2">
            ${options.mode === "entry"
              ? renderEditableControl(field, row, disabled)
              : `<div class="px-2 py-2 text-sm text-slate-800">${formatReadonlyValue(field, row)}</div>`}
          </div>
          <div class="flex flex-wrap items-center gap-1 border-t border-slate-100 px-2 py-1">
            ${cellStateBadge(state)}
            ${locked ? '<span class="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-700">Locked</span>' : ""}
            ${proof ? '<span class="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-700">Proof</span>' : ""}
          </div>
          ${remark ? `<div class="border-t border-slate-100 px-2 py-1 text-xs text-slate-500">${escapeHtml(remark)}</div>` : ""}
        </div>
      </td>
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
    const fields = [...(options.fields || [])].sort((a, b) => (a.display_order || 0) - (b.display_order || 0));
    const rows = options.rows || [];
    const headEl = options.headEl;
    const bodyEl = options.bodyEl;
    if (!headEl || !bodyEl) return;

    headEl.innerHTML = `
      <tr>
        <th class="sticky left-0 z-20 min-w-[150px] border border-slate-200 bg-slate-50 px-3 py-2 text-left">Month</th>
        <th class="min-w-[160px] border border-slate-200 bg-slate-50 px-3 py-2 text-left">Status</th>
        ${fields.map((field) => `
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
          ${fields.map((field) => renderCell(row, field, options)).join("")}
        </tr>
      `;
    }).join("");

    bodyEl.querySelectorAll("tr[data-row-key]").forEach((tr) => {
      tr.addEventListener("click", function (event) {
        if (event.target && ["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A"].includes(event.target.tagName)) return;
        if (typeof options.onRowSelect === "function") options.onRowSelect(tr.dataset.rowKey);
      });
    });

    bodyEl.querySelectorAll("[data-field-code]").forEach((input) => {
      input.addEventListener("input", options.onCellChange || function () {});
      input.addEventListener("change", options.onCellChange || function () {});
    });
  }

  window.WorkbookSheet = {
    CELL_STATE_META,
    escapeHtml,
    rowKey,
    primitiveValue,
    render,
  };
})();
