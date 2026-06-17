document.addEventListener("DOMContentLoaded", function () {
  let selectedValSetId = null;
  let selectedVersionId = null;
  let currentPermissions = {};
  let currentVersionStatus = null;
  let entries = []; // working copy of current version entries

  // ── URL params ────────────────────────────────────────────────────────
  const _vsUrlParams = new URLSearchParams(window.location.search);
  const _vsReturnTo = _vsUrlParams.get("return_to");
  const _vsReturnFormId = _vsUrlParams.get("form_id");
  const _vsReturnVersionId = _vsUrlParams.get("version_id");
  const _vsReturnFieldId = _vsUrlParams.get("field_id");
  const _vsContext = _vsUrlParams.get("context");
  const _vsDebug = _vsUrlParams.get("vs_debug") === "1";

  // Show back link / banner based on context
  if (_vsReturnTo) {
    if (_vsContext === "formula") {
      const banner = document.getElementById("vs-formula-banner");
      const backLink = document.getElementById("vs-formula-back-link");
      if (banner && backLink) {
        backLink.href = _vsReturnTo;
        banner.classList.remove("hidden");
      }
    } else {
      const bar = document.getElementById("vs-return-link-bar");
      const link = document.getElementById("vs-return-link");
      if (bar && link) {
        const returnParams = new URLSearchParams();
        if (_vsReturnFormId) returnParams.set("form_id", _vsReturnFormId);
        if (_vsReturnVersionId) returnParams.set("version_id", _vsReturnVersionId);
        if (_vsReturnFieldId) returnParams.set("field_id", _vsReturnFieldId);
        link.href = returnParams.toString() ? _vsReturnTo + "?" + returnParams.toString() : _vsReturnTo;
        bar.classList.remove("hidden");
      }
    }
  }

  // ── Element refs ──────────────────────────────────────────────────────
  const listContainer    = document.getElementById("valset-list");
  const detailsPanel     = document.getElementById("details-panel");
  const emptyState       = document.getElementById("details-empty-state");
  const versionSelect    = document.getElementById("version-select");
  const statusBadge      = document.getElementById("version-status-badge");
  const btnSaveDraft     = document.getElementById("btn-save-draft");
  const btnPublish       = document.getElementById("btn-publish");
  const btnReject        = document.getElementById("btn-reject");
  const btnAddEntry      = document.getElementById("btn-add-entry");
  const btnCreateDraft   = document.getElementById("btn-create-draft");
  const publishedNotice  = document.getElementById("published-notice");
  const rejectionNotice  = document.getElementById("rejection-notice");
  const entriesTbody     = document.getElementById("entries-tbody");
  const btnCreateValSet  = document.getElementById("btn-create-valset");
  const modalCreate      = document.getElementById("modal-create");
  const btnCloseModal    = document.getElementById("btn-close-modal");
  const btnCancelModal   = document.getElementById("btn-cancel-modal");
  const formCreateValSet = document.getElementById("form-create-valset");
  const valsetNameInput  = document.getElementById("valset-name");
  const valsetCodePreview = document.getElementById("valset-code-preview");
  const modalReject      = document.getElementById("modal-reject");
  const btnCloseReject   = document.getElementById("btn-close-reject");
  const btnCancelReject  = document.getElementById("btn-cancel-reject");
  const formRejectVersion = document.getElementById("form-reject-version");

  // ── Helpers ───────────────────────────────────────────────────────────
  function showToast(message, type = "success") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "fixed top-5 right-5 z-50 space-y-2 pointer-events-none";
      document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = [
      "p-4 rounded-xl shadow-lg border text-xs font-bold",
      "transition-all duration-300 transform translate-y-2 opacity-0",
      "flex items-center justify-between pointer-events-auto",
      type === "success" ? "bg-emerald-50 border-emerald-200 text-emerald-800"
        : type === "warning" ? "bg-amber-50 border-amber-200 text-amber-800"
        : "bg-rose-50 border-rose-200 text-rose-800"
    ].join(" ");
    toast.innerHTML = `<span>${message}</span><button class="ml-4 font-normal text-slate-400 hover:text-slate-600">✕</button>`;
    toast.querySelector("button").onclick = () => toast.remove();
    container.appendChild(toast);
    setTimeout(() => toast.classList.remove("translate-y-2", "opacity-0"), 10);
    setTimeout(() => {
      toast.classList.add("translate-y-2", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function slugify(str) {
    return (str || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  }

  function displayStatus(status) {
    const normalized = normalizeStatus(status);
    if (normalized === "approved") return "Published";
    if (normalized === "draft") return "Draft";
    if (normalized === "rejected") return "Rejected";
    if (normalized === "submitted") return "Submitted";
    return status || "Draft";
  }

  function normalizeStatus(status) {
    return String(status || "").trim().toLowerCase();
  }

  function isEditableVersion(version) {
    return !!(version && version.id);
  }

  function entryValue(entry) {
    if (!entry) return "";
    if (entry.entry_value !== undefined && entry.entry_value !== null) return entry.entry_value;
    if (entry.value !== undefined && entry.value !== null) return entry.value;
    if (entry.numeric_value !== undefined && entry.numeric_value !== null) return entry.numeric_value;
    return entry.entry_label || "";
  }

  function setEntryValue(entry, value) {
    entry.entry_label = value;
    if (entry.entry_value !== undefined) entry.entry_value = value;
    if (entry.value !== undefined) entry.value = value;
    if (entry.numeric_value !== undefined) entry.numeric_value = value;
  }

  function debugLog(label, data) {
    if (_vsDebug) console.debug(`[VALSET] ${label}`, data);
  }

  function esc(str) {
    return (str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ── Inline entries table ──────────────────────────────────────────────

  const ENTRY_INPUT_STYLE = "border:1px solid #c4d4e8;padding:6px 10px;width:100%;font-size:14px;background:white;box-sizing:border-box;outline:none;";

  // Read current DOM input values back into entries[] before any mutation.
  function syncEntries() {
    entriesTbody.querySelectorAll("tr.entry-row").forEach(row => {
      const idx = parseInt(row.dataset.idx, 10);
      if (idx >= 0 && idx < entries.length) {
        const ci = row.querySelector(".entry-code-input");
        const vi = row.querySelector(".entry-value-input");
        if (ci) entries[idx].entry_code  = ci.value;
        if (vi) setEntryValue(entries[idx], vi.value);
      }
    });
  }

  function makeInput(type, value, className, idx) {
    const inp = document.createElement("input");
    inp.type        = type;
    inp.value       = value || "";
    inp.className   = className;
    inp.dataset.idx = String(idx);
    inp.style.cssText = ENTRY_INPUT_STYLE;
    if (type === "text") inp.style.fontFamily = "monospace";
    if (type === "number") inp.step = "any";
    inp.placeholder = type === "number" ? "0.000" : "entry_code";
    inp.addEventListener("focus", () => { inp.style.outline = "2px solid #1a3a6b"; });
    inp.addEventListener("blur",  () => { inp.style.outline = "none"; });
    return inp;
  }

  function renderEntries(canEdit) {
    debugLog("entries before render", entries);
    while (entriesTbody.firstChild) entriesTbody.removeChild(entriesTbody.firstChild);

    // Empty state
    if (entries.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 3;
      if (canEdit) {
        td.style.cssText = "padding:20px 16px;";
        td.innerHTML =
          "<p style='font-size:12px;font-weight:600;color:#475569;margin:0 0 8px;'>No entries yet. Add your first reference constant below.</p>" +
          "<p style='font-size:11px;color:#94a3b8;margin:0 0 6px;'>Common examples:</p>" +
          "<table style='font-size:11px;color:#94a3b8;border-collapse:collapse;'>" +
            "<tr><td style='font-family:monospace;padding:1px 20px 1px 0;'>diesel_ef</td><td style='padding-right:20px;'>Diesel emission factor</td><td style='font-family:monospace;'>2.68</td></tr>" +
            "<tr><td style='font-family:monospace;padding:1px 20px 1px 0;'>grid_ef</td><td style='padding-right:20px;'>Grid electricity factor</td><td style='font-family:monospace;'>0.713</td></tr>" +
            "<tr><td style='font-family:monospace;padding:1px 20px 1px 0;'>gwp_ch4</td><td style='padding-right:20px;'>Methane GWP</td><td style='font-family:monospace;'>28</td></tr>" +
          "</table>" +
          "<p style='font-size:10px;color:#cbd5e1;margin:8px 0 0;font-style:italic;'>Display examples only — not inserted into the database.</p>";
      } else {
        td.style.cssText = "padding:32px 12px;text-align:center;font-size:12px;color:#94a3b8;font-style:italic;";
        td.textContent = "No entries.";
      }
      tr.appendChild(td);
      entriesTbody.appendChild(tr);
      return;
    }

    entries.forEach((entry, idx) => {
      const tr = document.createElement("tr");
      tr.className    = "entry-row";
      tr.dataset.idx  = String(idx);
      tr.style.borderBottom = "1px solid #f1f5f9";

      // Code cell
      const tdCode = document.createElement("td");
      if (canEdit) {
        tdCode.style.padding = "4px 8px";
        const inp = makeInput("text", entry.entry_code, "entry-code-input", idx);
        inp.addEventListener("input", () => { entries[idx].entry_code = inp.value; });
        tdCode.appendChild(inp);
      } else {
        tdCode.style.cssText = "padding:10px 12px;font-family:monospace;font-size:12px;color:#475569;";
        tdCode.textContent = entry.entry_code || "";
      }

      // Value cell
      const tdVal = document.createElement("td");
      if (canEdit) {
        tdVal.style.padding = "4px 8px";
        const inp = makeInput("number", entryValue(entry), "entry-value-input", idx);
        inp.addEventListener("input", () => {
          setEntryValue(entries[idx], inp.value);
          const v = inp.value.trim();
          const ok = v === "" || (!isNaN(parseFloat(v)) && isFinite(Number(v)));
          inp.style.borderColor = ok ? "#c4d4e8" : "#c8102e";
        });
        tdVal.appendChild(inp);
      } else {
        tdVal.style.cssText = "padding:10px 12px;font-size:12px;color:#334155;";
        tdVal.textContent = entryValue(entry);
      }

      // Remove cell
      const tdDel = document.createElement("td");
      tdDel.style.cssText = "padding:4px 8px;text-align:right;width:40px;";
      if (canEdit) {
        const btn = document.createElement("button");
        btn.type      = "button";
        btn.className = "remove-entry-btn";
        btn.dataset.idx = String(idx);
        btn.title     = "Remove";
        btn.textContent = "×";
        btn.style.cssText = "background:none;border:none;cursor:pointer;font-size:20px;font-weight:bold;line-height:1;padding:0 4px;color:#cbd5e1;";
        btn.addEventListener("mouseenter", () => { btn.style.color = "#ef4444"; });
        btn.addEventListener("mouseleave", () => { btn.style.color = "#cbd5e1"; });
        btn.addEventListener("click", () => {
          syncEntries();
          entries.splice(idx, 1);
          renderEntries(canEdit);
        });
        tdDel.appendChild(btn);
      }

      tr.appendChild(tdCode);
      tr.appendChild(tdVal);
      tr.appendChild(tdDel);
      entriesTbody.appendChild(tr);
    });
    debugLog("rendered entry inputs", {
      codeInputs: entriesTbody.querySelectorAll(".entry-code-input").length,
      valueInputs: entriesTbody.querySelectorAll(".entry-value-input").length,
    });
  }

  // ── Add entry button ──────────────────────────────────────────────────
  btnAddEntry.onclick = function () {
    syncEntries();
    const maxOrder = entries.reduce((m, e) => Math.max(m, e.display_order || 0), 0);
    entries.push({ entry_code: "", entry_label: "", display_order: maxOrder + 1, is_active: true });
    renderEntries(true);
    // Focus code input of the new row
    const rows = entriesTbody.querySelectorAll("tr.entry-row");
    const last = rows[rows.length - 1];
    if (last) {
      const inp = last.querySelector(".entry-code-input");
      if (inp) setTimeout(() => inp.focus(), 0);
    }
  };

  // ── Panel state ───────────────────────────────────────────────────────
  function updatePanelState(version, permissions) {
    currentVersionStatus = version.status;
    currentPermissions = permissions;

    const ds = displayStatus(version.status);
    const colors = {
      Draft: "bg-amber-100 text-amber-800",
      Published: "bg-emerald-100 text-emerald-800",
    };
    statusBadge.className = `px-2 py-0.5 rounded-full font-bold text-[9px] uppercase ${colors[ds] || "bg-slate-100 text-slate-700"}`;
    statusBadge.textContent = ds;

    const status = normalizeStatus(version.status);
    const canEdit = !!permissions.can_edit && isEditableVersion(version);
    debugLog("version state", {
      version,
      status: version.status,
      normalizedStatus: status,
      canEdit,
      permissions,
    });

    btnSaveDraft.classList.toggle("hidden", !canEdit);
    btnSaveDraft.textContent = "Save Changes";
    btnAddEntry.classList.toggle("hidden", !canEdit);
    btnReject.classList.toggle("hidden", !permissions.can_approve);
    btnPublish.classList.toggle("hidden", !permissions.can_publish);
    publishedNotice.classList.toggle("hidden", !permissions.can_create_version);
    
    if (status === "rejected" && version.rejection_reason) {
      rejectionNotice.textContent = `Rejection reason: ${version.rejection_reason}`;
      rejectionNotice.classList.remove("hidden");
    } else {
      rejectionNotice.classList.add("hidden");
      rejectionNotice.innerHTML = "";
    }

    renderEntries(canEdit);
  }

  // ── Load value sets list ──────────────────────────────────────────────
  function loadValueSets(selectId = null) {
    if (selectId !== null && selectId !== undefined) {
      selectedValSetId = selectId;
    }
    listContainer.innerHTML = '<li class="p-6 text-center text-slate-400 italic text-sm">Loading...</li>';

    fetch("/module/VALSET/api")
      .then(res => res.json())
      .then(data => {
        listContainer.innerHTML = "";
        if (data.length === 0) {
          listContainer.innerHTML = `
            <li class="px-5 py-7 text-center space-y-3">
              <p class="text-sm font-semibold text-slate-600">No reference tables yet.</p>
              <p class="text-xs text-slate-400">Create reusable constants for your formulas:</p>
              <ul class="text-xs text-slate-400 space-y-0.5 inline-block text-left">
                <li>· Emission factors</li>
                <li>· GWP values</li>
                <li>· Conversion factors</li>
              </ul>
              <div class="pt-1">
                <button id="vs-empty-create-btn"
                  class="inline-flex items-center px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow transition">
                  + Create your first Value Set
                </button>
              </div>
            </li>`;
          const emptyBtn = document.getElementById("vs-empty-create-btn");
          if (emptyBtn) emptyBtn.onclick = () => btnCreateValSet.click();
          return;
        }

        let autoLoadId = null;
        data.forEach(item => {
          const isSelected = item.id === selectedValSetId;
          const li = document.createElement("li");
          li.className = `cursor-pointer transition-colors ${
            isSelected
              ? "px-3 py-3.5 bg-indigo-50/50 border-l-4 border-indigo-600 hover:bg-indigo-50"
              : "px-4 py-3.5 hover:bg-slate-50"
          }`;

          const ds = displayStatus(item.selected_version_status || item.current_version_status || item.latest_version_status);
          const badgeColor = ds === "Published" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700";

          li.innerHTML = `
            <div class="flex items-start justify-between gap-2">
              <span class="font-semibold text-sm text-slate-800 leading-snug">${esc(item.name)}</span>
              <span class="shrink-0 text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${badgeColor}">${ds}</span>
            </div>
            <span class="text-[10px] font-mono text-slate-400 mt-0.5 block">${esc(item.code)}</span>
          `;

          li.onclick = () => {
            selectedValSetId = item.id;
            debugLog("selected value set", item);
            // Re-apply highlight
            Array.from(listContainer.children).forEach(c => {
              c.className = "px-4 py-3.5 cursor-pointer transition-colors hover:bg-slate-50";
            });
            li.className = "px-3 py-3.5 cursor-pointer transition-colors bg-indigo-50/50 border-l-4 border-indigo-600 hover:bg-indigo-50";
            loadVersion(item.selected_version_id || item.current_version_id || item.latest_version_id);
          };

          listContainer.appendChild(li);

          if (isSelected) autoLoadId = item.selected_version_id || item.current_version_id || item.latest_version_id;
        });

        if (autoLoadId) loadVersion(autoLoadId);
      })
      .catch(() => showToast("Failed to load value sets.", "error"));
  }

  // ── Load version ──────────────────────────────────────────────────────
  function loadVersion(versionId) {
    if (!versionId) return;

    fetch(`/module/VALSET/api/version/${versionId}`)
      .then(res => {
        if (!res.ok) throw new Error("Failed to load version.");
        return res.json();
      })
      .then(data => {
        selectedVersionId = data.version.id;
        debugLog("selected version response", data);

        emptyState.classList.add("hidden");
        detailsPanel.classList.remove("hidden");

        // Identity
        document.getElementById("detail-name").textContent = data.value_set.name;
        document.getElementById("detail-code").textContent = "code: " + data.value_set.code;
        const descEl = document.getElementById("detail-desc");
        if (data.value_set.description) {
          descEl.textContent = data.value_set.description;
          descEl.classList.remove("hidden");
        } else {
          descEl.classList.add("hidden");
        }

        // Version selector
        versionSelect.innerHTML = "";
        (data.all_versions || []).forEach(v => {
          const opt = document.createElement("option");
          opt.value = v.id;
          opt.textContent = `v${v.version_number} (${displayStatus(v.status)})`;
          opt.selected = v.id === selectedVersionId;
          versionSelect.appendChild(opt);
        });

        // Entries
        entries = (data.entries || []).map(e => ({ ...e }));
        debugLog("selected version entries", entries);

        // Update panel state + render entries
        updatePanelState(data.version, data.permissions || {});
      })
      .catch(err => showToast(err.message || "Error loading version.", "error"));
  }

  versionSelect.onchange = () => loadVersion(parseInt(versionSelect.value));

  // ── Save Changes ──────────────────────────────────────────────────────
  btnSaveDraft.onclick = async function () {
    if (!selectedVersionId) return;
    syncEntries();

    if (entries.some(e => !e.entry_code || !e.entry_code.trim())) {
      showToast("All entries must have a code.", "error");
      return;
    }

    btnSaveDraft.disabled = true;
    const orig = btnSaveDraft.textContent;
    btnSaveDraft.textContent = "Saving…";

    try {
      const payload = entries.map((e, idx) => ({
        entry_code: e.entry_code.trim(),
        entry_label: String(entryValue(e)).trim(),
        display_order: idx + 1,
        is_active: true,
      }));
      debugLog("save payload", { versionId: selectedVersionId, entries: payload });
      const res = await fetch(`/module/VALSET/api/version/${selectedVersionId}/entries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entries: payload }),
      });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("Changes saved.");
        loadVersion(selectedVersionId);
      }
    } catch {
      showToast("Failed to save changes.", "error");
    } finally {
      btnSaveDraft.disabled = false;
      btnSaveDraft.textContent = orig;
    }
  };

  // ── Publish ───────────────────────────────────────────────────────────
  btnPublish.onclick = async function () {
    if (!selectedVersionId) return;
    if (!confirm("Publish this value set version? It will be available in formula builder.")) return;

    btnPublish.disabled = true;
    btnPublish.textContent = "Publishing…";

    try {
      const res = await fetch(`/module/VALSET/api/version/${selectedVersionId}/publish`, { method: "POST" });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("Value set published.");
        if (_vsReturnTo) {
          window.location.href = _vsReturnTo;
        } else {
          loadVersion(selectedVersionId);
          loadValueSets(selectedValSetId);
        }
      }
    } catch {
      showToast("Action failed. Please try again.", "error");
    } finally {
      btnPublish.disabled = false;
      btnPublish.textContent = "Publish Version";
    }
  };

  // ── Reject ────────────────────────────────────────────────────────────
  btnReject.onclick = () => modalReject.classList.remove("hidden");
  btnCloseReject.onclick = () => modalReject.classList.add("hidden");
  btnCancelReject.onclick = () => modalReject.classList.add("hidden");

  formRejectVersion.onsubmit = async function (e) {
    e.preventDefault();
    if (!selectedVersionId) return;
    const reason = document.getElementById("reject-reason").value;
    const submitBtn = this.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    submitBtn.textContent = "Rejecting…";
    try {
      const res = await fetch(`/module/VALSET/api/version/${selectedVersionId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("Version rejected.", "warning");
        modalReject.classList.add("hidden");
        document.getElementById("reject-reason").value = "";
        loadVersion(selectedVersionId);
        loadValueSets();
      }
    } catch {
      showToast("Failed to reject.", "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit Rejection";
    }
  };

  // ── Create new draft from Approved ───────────────────────────────────
  btnCreateDraft.onclick = async function () {
    if (!selectedValSetId) return;
    if (!confirm("Create a new draft version from the current published entries?")) return;
    try {
      const res = await fetch(`/module/VALSET/api/${selectedValSetId}/new-version`, { method: "POST" });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("New draft version created.");
        loadVersion(resData.data.version_id);
        loadValueSets(selectedValSetId);
      }
    } catch {
      showToast("Failed to create new draft.", "error");
    }
  };

  // ── Create modal ──────────────────────────────────────────────────────
  valsetNameInput.addEventListener("input", function () {
    const code = slugify(this.value);
    valsetCodePreview.textContent = code ? "Code: " + code : "";
  });

  btnCreateValSet.onclick = () => {
    valsetNameInput.value = "";
    valsetCodePreview.textContent = "";
    modalCreate.classList.remove("hidden");
    setTimeout(() => valsetNameInput.focus(), 50);
  };
  btnCloseModal.onclick = () => modalCreate.classList.add("hidden");
  btnCancelModal.onclick = () => modalCreate.classList.add("hidden");

  formCreateValSet.onsubmit = async function (e) {
    e.preventDefault();
    const name = valsetNameInput.value.trim();
    if (!name) return;
    const code = slugify(name);
    if (!code) { showToast("Could not generate a code from that name.", "error"); return; }

    const submitBtn = this.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    submitBtn.textContent = "Creating…";

    try {
      const res = await fetch("/module/VALSET/api", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, code, description: "" }),
      });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        modalCreate.classList.add("hidden");
        valsetNameInput.value = "";
        valsetCodePreview.textContent = "";
        showToast("Value set created.");
        selectedValSetId = resData.data.id;
        if (resData.data.version_id) loadVersion(resData.data.version_id);
        loadValueSets(resData.data.id);
      }
    } catch {
      showToast("Failed to create value set.", "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Create →";
    }
  };

  // ── Initial load ──────────────────────────────────────────────────────
  loadValueSets();
});
