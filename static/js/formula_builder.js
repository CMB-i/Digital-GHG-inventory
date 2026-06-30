document.addEventListener("DOMContentLoaded", function () {
  let formulasList = [];
  let selectedFormulaId = null;
  let selectedVersionId = null;
  let isPublished = false;

  // code → friendly display name, populated from field palette + valset palette
  const fieldNameMap = {};

  // All valset codes (for chip type detection on refreshDisplay)
  const valsetCodeSet = new Set();

  // Track valset codes inserted this session (for token building on save)
  const insertedValsetCodes = new Set();

  // Saved cursor range for operator/chip insertion into contenteditable
  let savedRange = null;
  let pendingAggregateHelper = null;
  let selectedChip = null;

  // ── Return-to params ──────────────────────────────────────────────────
  const _fbUrlParams = new URLSearchParams(window.location.search);
  const _returnTo = _fbUrlParams.get("return_to");
  const _returnFieldId = _fbUrlParams.get("field_id");
  const _returnFormId = _fbUrlParams.get("form_id");
  const _returnVersionId = _fbUrlParams.get("version_id");
  const _openFormulaId = parseInt(_fbUrlParams.get("open_formula_id")) || null;
  const _openVersionId = parseInt(_fbUrlParams.get("open_version_id")) || null;

  function returnToUrl() {
    if (!_returnTo) return "/module/FRMULA/";
    const backParams = new URLSearchParams();
    if (_returnFormId) backParams.set("form_id", _returnFormId);
    if (_returnVersionId) backParams.set("version_id", _returnVersionId);
    if (_returnFieldId) backParams.set("field_id", _returnFieldId);
    return backParams.toString() ? _returnTo + "?" + backParams.toString() : _returnTo;
  }

  // ── Element refs ──────────────────────────────────────────────────────
  const listView = document.getElementById("list-view");
  const editorView = document.getElementById("editor-view");
  const formulasListBody = document.getElementById("formulas-list-body");
  const editorStatusBadge = document.getElementById("editor-status-badge");
  const btnSaveFormula = document.getElementById("btn-save-formula");
  const btnPublishFormula = document.getElementById("btn-publish-formula");
  const dfName = document.getElementById("df-name");
  const dfCodeDisplay = document.getElementById("df-code-display");
  const expressionDisplay = document.getElementById("expression-display");
  const expressionTextarea = document.getElementById("expression");
  const btnValidate = document.getElementById("btn-validate-formula");
  const validationResultContainer = document.getElementById("validation-result-container");
  const validationResult = document.getElementById("validation-result");
  const previewInputsGrid = document.getElementById("preview-inputs-grid");
  const previewResultValue = document.getElementById("preview-result-value");
  const formVersionSelect = document.getElementById("form-version-select");
  const modalCreate = document.getElementById("modal-create");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const btnCancelModal = document.getElementById("btn-cancel-modal");
  const formCreateFormula = document.getElementById("form-create-formula");
  const btnInsertSumMonths = document.getElementById("btn-insert-sum-months");

  // ── Help Manual Drawer Refs ───────────────────────────────────────────
  const btnOpenHelp = document.getElementById("btn-open-help");
  const btnCloseHelp = document.getElementById("btn-close-help");
  const helpDrawer = document.getElementById("help-drawer");

  if (btnOpenHelp && helpDrawer) {
    btnOpenHelp.onclick = function (e) {
      e.preventDefault();
      helpDrawer.classList.add("open");
    };
  }
  if (btnCloseHelp && helpDrawer) {
    btnCloseHelp.onclick = function (e) {
      e.preventDefault();
      helpDrawer.classList.remove("open");
    };
  }

  // ── Back button ───────────────────────────────────────────────────────
  const btnEditorBack = document.getElementById("btn-editor-back");
  if (btnEditorBack) {
    if (_returnTo) {
      btnEditorBack.textContent = _returnTo.includes("/module/FORMBLD/")
        ? "← Back to workbook"
        : "← Formula Builder";
      btnEditorBack.onclick = function () {
        window.location.href = returnToUrl();
      };
    } else {
      btnEditorBack.textContent = "← Formula Builder";
      btnEditorBack.onclick = function () {
        window.location.href = "/module/FRMULA/";
      };
    }
  }

  // ── Toast ─────────────────────────────────────────────────────────────
  function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `p-4 rounded shadow-lg border text-xs font-bold transition-all duration-300 transform translate-y-2 opacity-0 flex items-center justify-between ${
      type === "success"
        ? "bg-emerald-50 border-emerald-200 text-emerald-800"
        : "bg-rose-50 border-rose-200 text-rose-800"
    }`;
    toast.innerHTML = `<span>${message}</span><button class="ml-4 font-normal text-slate-400 hover:text-slate-600">✕</button>`;
    toast.querySelector("button").onclick = () => toast.remove();
    container.appendChild(toast);
    setTimeout(() => toast.classList.remove("translate-y-2", "opacity-0"), 10);
    setTimeout(() => {
      toast.classList.add("translate-y-2", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // ── Code slug ─────────────────────────────────────────────────────────
  function slugify(name) {
    return (name || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function updateCodeDisplay(name) {
    if (!dfCodeDisplay) return;
    const code = slugify(name);
    dfCodeDisplay.textContent = code ? "Code: " + code : "";
  }

  // ════════════════════════════════════════════════════════════════════
  // CHIP ENGINE — contenteditable expression display
  // ════════════════════════════════════════════════════════════════════

  // Build a chip element for a known field/valset code
  function makeChip(code, displayName, type) {
    const span = document.createElement("span");
    span.className = type === "valset" ? "formula-chip formula-chip-valset" : "formula-chip";
    span.dataset.code = code;
    span.contentEditable = "false";
    span.textContent = displayName;
    return span;
  }

  // Save the cursor range whenever the selection is inside expressionDisplay.
  // Saved before operator/chip button clicks steal focus.
  document.addEventListener("selectionchange", function () {
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0 && expressionDisplay.contains(sel.anchorNode)) {
      try { savedRange = sel.getRangeAt(0).cloneRange(); } catch (_) {}
    }
  });
  expressionDisplay.addEventListener("blur", function () {
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0) {
      try { savedRange = sel.getRangeAt(0).cloneRange(); } catch (_) {}
    }
  });

  // Restore saved range into the selection and return the live Range object.
  // Falls back to end-of-display if nothing is saved.
  function getOrRestoreRange() {
    expressionDisplay.focus();
    const sel = window.getSelection();
    if (savedRange && expressionDisplay.contains(savedRange.startContainer)) {
      sel.removeAllRanges();
      sel.addRange(savedRange);
      return sel.getRangeAt(0);
    }
    const range = document.createRange();
    range.selectNodeContents(expressionDisplay);
    range.collapse(false);
    sel.removeAllRanges();
    sel.addRange(range);
    return range;
  }

  // Insert a DOM node (chip) at the current cursor position
  function insertNodeAtCursor(node) {
    const range = getOrRestoreRange();
    range.deleteContents();
    range.insertNode(node);
    range.setStartAfter(node);
    range.collapse(true);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    savedRange = range.cloneRange();
    syncToTextarea();
  }

  // Insert a plain-text string at the current cursor position
  function insertTextAtCursor(text) {
    const range = getOrRestoreRange();
    range.deleteContents();
    const textNode = document.createTextNode(text);
    range.insertNode(textNode);
    range.setStartAfter(textNode);
    range.collapse(true);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    savedRange = range.cloneRange();
    syncToTextarea();
  }

  // Wrap a chip in SUM_MONTHS(...)
  function wrapChipInSum(chip) {
    const code = chip.dataset.code;
    const name = chip.textContent;
    const isValset = chip.classList.contains("formula-chip-valset");
    if (isValset) {
      showToast("SUM_MONTHS only accepts sheet fields, not constants.", "error");
      return;
    }
    
    // Replace the chip with "SUM_MONTHS(chip)"
    const parent = chip.parentNode;
    const openParen = document.createTextNode("SUM_MONTHS(");
    const closeParen = document.createTextNode(")");
    
    parent.insertBefore(openParen, chip);
    parent.insertBefore(closeParen, chip.nextSibling);
    syncToTextarea();
  }

  // Click handler to select chips for wrapping
  expressionDisplay.addEventListener("click", function (e) {
    const chip = e.target.closest(".formula-chip");
    // Clear previous selection
    document.querySelectorAll(".formula-chip").forEach(c => {
      c.style.outline = "none";
    });
    selectedChip = null;
    
    if (chip) {
      chip.style.outline = "2px solid #7c3aed";
      selectedChip = chip;
    }
  });

  // Serialize contenteditable children → expression string of field codes
  function syncToTextarea() {
    let expr = "";
    function walk(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        expr += node.textContent;
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        if (node.classList && node.classList.contains("formula-chip")) {
          expr += node.dataset.code;
        } else if (node.nodeName === "BR") {
          expr += " ";
        } else {
          node.childNodes.forEach(walk);
        }
      }
    }
    expressionDisplay.childNodes.forEach(walk);
    expressionTextarea.value = expr;
    scanVariablesAndInitPreview();
  }

  // Rebuild the contenteditable display from the hidden textarea's expression.
  // Field codes found in fieldNameMap become chips; everything else stays as text.
  function refreshDisplay() {
    const expr = expressionTextarea.value || "";
    expressionDisplay.innerHTML = "";
    if (!expr.trim()) return;

    // Tokenize: identifiers, numbers, operators/parens/commas, spaces, fallback char
    const parts = expr.match(/[a-zA-Z_][a-zA-Z0-9_]*|[0-9]*\.?[0-9]+|[\+\-\*\/\(\),]+|\s+|./g) || [];
    parts.forEach(part => {
      const name = fieldNameMap[part];
      if (name) {
        const type = valsetCodeSet.has(part) ? "valset" : "field";
        expressionDisplay.appendChild(makeChip(part, name, type));
      } else {
        expressionDisplay.appendChild(document.createTextNode(part));
      }
    });
  }

  function setPendingAggregateHelper(helper) {
    pendingAggregateHelper = helper;
    if (!btnInsertSumMonths) return;
    const active = helper === "SUM_MONTHS";
    btnInsertSumMonths.classList.toggle("active", active);
  }

  function selectedExpressionText() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) return "";
    const range = sel.getRangeAt(0);
    if (!expressionDisplay.contains(range.commonAncestorContainer)) return "";
    return sel.toString().trim();
  }

  function isSingleFieldReference(text) {
    return /^[A-Za-z_][A-Za-z0-9_]*$/.test((text || "").trim());
  }

  // ── expressionDisplay event wiring ────────────────────────────────────
  expressionDisplay.addEventListener("input", syncToTextarea);

  // Prevent Enter key (no multi-line formulas)
  expressionDisplay.addEventListener("keydown", function (e) {
    if (e.key === "Enter") e.preventDefault();
  });

  // Plain-text paste only
  expressionDisplay.addEventListener("paste", function (e) {
    e.preventDefault();
    const text = (e.clipboardData || window.clipboardData).getData("text/plain");
    if (text) insertTextAtCursor(text);
  });

  // ── insertToken / insertOperator — now drive the contenteditable ──────
  window.insertToken = function (code) {
    if (isPublished) return;
    const name = fieldNameMap[code] || code;
    const type = valsetCodeSet.has(code) ? "valset" : "field";
    if (pendingAggregateHelper === "SUM_MONTHS" && type === "field") {
      insertTextAtCursor("SUM_MONTHS(");
      insertNodeAtCursor(makeChip(code, name, type));
      insertTextAtCursor(")");
      setPendingAggregateHelper(null);
      return;
    }
    insertNodeAtCursor(makeChip(code, name, type));
  };

  window.insertOperator = function (op) {
    if (isPublished) return;
    insertTextAtCursor(op);
  };

  if (btnInsertSumMonths) {
    btnInsertSumMonths.addEventListener("click", function () {
      if (isPublished) return;
      if (selectedChip) {
        wrapChipInSum(selectedChip);
        selectedChip.style.outline = "none";
        selectedChip = null;
        return;
      }
      
      const selectedText = selectedExpressionText();
      if (selectedText && !isSingleFieldReference(selectedText)) {
        setPendingAggregateHelper(null);
        showToast("SUM_MONTHS accepts one monthly field only. Use SUM_MONTHS(field_a) + SUM_MONTHS(field_b) for multiple fields.", "error");
        return;
      }
      setPendingAggregateHelper(pendingAggregateHelper === "SUM_MONTHS" ? null : "SUM_MONTHS");
      if (pendingAggregateHelper === "SUM_MONTHS") {
        showToast("Click a field, or drop a field onto Σ SUM to wrap it.");
      }
    });
  }

  // ── Drag & Drop Event Listeners ───────────────────────────────────────
  document.addEventListener("dragstart", function (e) {
    const el = e.target.closest("[draggable='true']");
    if (el) {
      el.classList.add("draggable-dragging");
      
      let dragData = {};
      if (el.dataset.code) {
        dragData.type = "operand";
        dragData.code = el.dataset.code;
      } else if (el.dataset.op) {
        dragData.type = "operator";
        dragData.op = el.dataset.op;
      }
      
      e.dataTransfer.setData("application/json", JSON.stringify(dragData));
      e.dataTransfer.effectAllowed = "copyMove";
    }
  });

  document.addEventListener("dragend", function (e) {
    const el = e.target.closest("[draggable='true']");
    if (el) {
      el.classList.remove("draggable-dragging");
    }
    expressionDisplay.classList.remove("drag-hover");
  });

  expressionDisplay.addEventListener("dragenter", function (e) {
    e.preventDefault();
    if (!isPublished) {
      expressionDisplay.classList.add("drag-hover");
    }
  });

  expressionDisplay.addEventListener("dragover", function (e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  });

  expressionDisplay.addEventListener("dragleave", function (e) {
    if (e.relatedTarget && expressionDisplay.contains(e.relatedTarget)) return;
    expressionDisplay.classList.remove("drag-hover");
  });

  expressionDisplay.addEventListener("drop", function (e) {
    e.preventDefault();
    expressionDisplay.classList.remove("drag-hover");
    if (isPublished) return;

    try {
      const dataStr = e.dataTransfer.getData("application/json");
      if (!dataStr) return;
      const data = JSON.parse(dataStr);

      // Determine insertion caret position
      let range = null;
      if (document.caretRangeFromPoint) {
        range = document.caretRangeFromPoint(e.clientX, e.clientY);
      } else if (document.caretPositionFromPoint) {
        const pos = document.caretPositionFromPoint(e.clientX, e.clientY);
        if (pos) {
          range = document.createRange();
          range.setStart(pos.offsetNode, pos.offset);
          range.collapse(true);
        }
      }

      const sel = window.getSelection();
      if (range && expressionDisplay.contains(range.startContainer)) {
        sel.removeAllRanges();
        sel.addRange(range);
        savedRange = range.cloneRange();
      } else {
        const rangeEnd = document.createRange();
        rangeEnd.selectNodeContents(expressionDisplay);
        rangeEnd.collapse(false);
        sel.removeAllRanges();
        sel.addRange(rangeEnd);
        savedRange = rangeEnd.cloneRange();
      }

      if (data.type === "operand") {
        insertToken(data.code);
      } else if (data.type === "operator") {
        if (data.op === "SUM_MONTHS") {
          // Check if dropped onto a field chip
          const targetEl = e.target.closest(".formula-chip");
          if (targetEl && !targetEl.classList.contains("formula-chip-valset")) {
            wrapChipInSum(targetEl);
          } else {
            insertOperator("SUM_MONTHS(");
            setPendingAggregateHelper("SUM_MONTHS");
          }
        } else {
          insertOperator(data.op);
        }
      }
    } catch (err) {
      console.error(err);
    }
  });

  // Drop onto SUM_MONTHS button
  if (btnInsertSumMonths) {
    btnInsertSumMonths.addEventListener("dragover", function (e) {
      e.preventDefault();
      btnInsertSumMonths.classList.add("bg-violet-100", "border-violet-400");
    });
    btnInsertSumMonths.addEventListener("dragleave", function () {
      btnInsertSumMonths.classList.remove("bg-violet-100", "border-violet-400");
    });
    btnInsertSumMonths.addEventListener("drop", function (e) {
      e.preventDefault();
      btnInsertSumMonths.classList.remove("bg-violet-100", "border-violet-400");
      if (isPublished) return;
      try {
        const dataStr = e.dataTransfer.getData("application/json");
        if (!dataStr) return;
        const data = JSON.parse(dataStr);
        if (data.type === "operand" && !valsetCodeSet.has(data.code)) {
          const name = fieldNameMap[data.code] || data.code;
          getOrRestoreRange();
          insertTextAtCursor("SUM_MONTHS(");
          insertNodeAtCursor(makeChip(data.code, name, "field"));
          insertTextAtCursor(")");
        } else {
          showToast("SUM_MONTHS only accepts sheet fields, not constants.", "error");
        }
      } catch (err) {
        console.error(err);
      }
    });
  }

  // ── View switching ────────────────────────────────────────────────────
  window.showList = function () {
    editorView.classList.add("hidden");
    listView.classList.remove("hidden");
    loadFormulas();
  };

  window.startNewFormula = function () {
    modalCreate.classList.remove("hidden");
    const nameInput = document.getElementById("formula-name");
    nameInput.value = "";
    setTimeout(() => nameInput.focus(), 50);
  };

  window.editFormula = function (formulaId, versionId) {
    selectedFormulaId = formulaId;
    selectedVersionId = versionId;
    listView.classList.add("hidden");
    editorView.classList.remove("hidden");
    validationResultContainer.classList.add("hidden");
    loadVersionDetails(versionId);
  };

  function openNewFormulaEditor(name) {
    selectedFormulaId = null;
    selectedVersionId = null;
    isPublished = false;
    savedRange = null;

    dfName.value = name;
    dfName.disabled = false;
    expressionTextarea.value = "";
    expressionDisplay.innerHTML = "";
    expressionDisplay.contentEditable = "true";
    expressionDisplay.classList.remove("bg-slate-50", "text-slate-400", "cursor-not-allowed");

    updateCodeDisplay(name);

    editorStatusBadge.textContent = "v1 (Draft)";
    editorStatusBadge.className = "px-2 py-0.5 rounded-full font-bold uppercase text-[9px] bg-amber-100 text-amber-800";

    btnSaveFormula.classList.remove("hidden");
    btnSaveFormula.textContent = "Save Draft";
    btnPublishFormula.classList.remove("hidden");

    validationResultContainer.classList.add("hidden");

    listView.classList.add("hidden");
    editorView.classList.remove("hidden");

    scanVariablesAndInitPreview();
  }

  // ── Load formulas list ────────────────────────────────────────────────
  function loadFormulas() {
    formulasListBody.innerHTML = '<tr><td colspan="5" class="px-6 py-12 text-center text-slate-400 italic">Loading formulas…</td></tr>';

    fetch("/module/FRMULA/api")
      .then(res => res.json())
      .then(data => {
        formulasList = data;
        formulasListBody.innerHTML = "";

        if (data.length === 0) {
          formulasListBody.innerHTML = `
            <tr>
              <td colspan="5" class="px-6 py-12 text-center text-slate-400 italic">
                No formulas configured yet. Click "Create Formula" to get started.
              </td>
            </tr>`;
          return;
        }

        data.forEach(item => {
          const tr = document.createElement("tr");
          tr.className = "hover:bg-slate-50/50 transition-colors";

          const statusBadge = item.is_published
            ? '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 uppercase">Published</span>'
            : '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 uppercase">Draft</span>';

          const actions = item.latest_version_id
            ? `<button onclick="editFormula(${item.id}, ${item.latest_version_id})" class="text-indigo-600 hover:text-indigo-900 font-bold hover:underline">Edit / Details</button>`
            : "";

          tr.innerHTML = `
            <td class="px-6 py-4 font-bold text-slate-800">${item.name}</td>
            <td class="px-6 py-4 font-mono text-slate-500">${item.code}</td>
            <td class="px-6 py-4">${statusBadge}</td>
            <td class="px-6 py-4 text-slate-500 font-semibold">v${item.latest_version_num || 1}</td>
            <td class="px-6 py-4 text-right whitespace-nowrap">${actions}</td>
          `;
          formulasListBody.appendChild(tr);
        });

        // Auto-open formula on return from value sets editor
        if (_openFormulaId) {
          const target = formulasList.find(f => f.id === _openFormulaId);
          if (target && target.latest_version_id) {
            editFormula(target.id, target.latest_version_id);
          }
        }
      })
      .catch(err => {
        console.error("Error loading formulas:", err);
        showToast("Error fetching formulas list.", "error");
      });
  }

  // ── Load version details ──────────────────────────────────────────────
  function loadVersionDetails(versionId) {
    fetch(`/module/FRMULA/api/version/${versionId}`)
      .then(res => res.json())
      .then(data => {
        selectedVersionId = data.version.id;
        selectedFormulaId = data.formula.id;
        isPublished = data.version.published_at !== null;
        savedRange = null;

        dfName.value = data.formula.name;
        dfCodeDisplay.textContent = "Code: " + data.formula.code;

        expressionTextarea.value = data.version.expression;
        refreshDisplay();

        const statusLabel = isPublished ? "Published" : "Draft";
        const badgeClass = isPublished ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800";
        editorStatusBadge.textContent = `v${data.version.version_number} (${statusLabel})`;
        editorStatusBadge.className = `px-2 py-0.5 rounded-full font-bold uppercase text-[9px] ${badgeClass}`;

        if (isPublished) {
          expressionDisplay.contentEditable = "false";
          dfName.disabled = true;
          btnSaveFormula.classList.add("hidden");
          btnPublishFormula.classList.add("hidden");
        } else {
          expressionDisplay.contentEditable = "true";
          expressionDisplay.classList.remove("bg-slate-50", "text-slate-400", "cursor-not-allowed");
          dfName.disabled = false;
          btnSaveFormula.classList.remove("hidden");
          btnSaveFormula.textContent = "Save Draft";
          btnPublishFormula.classList.remove("hidden");
        }

        scanVariablesAndInitPreview();
      })
      .catch(err => {
        console.error("Error loading version details:", err);
        showToast("Error loading formula details.", "error");
      });
  }

  // ── Value set palette wiring ──────────────────────────────────────────
  document.querySelectorAll(".palette-btn-valset").forEach(btn => {
    const code = btn.dataset.code;
    const label = btn.dataset.label || code;
    valsetCodeSet.add(code);
    fieldNameMap[code] = label;

    btn.onclick = () => {
      insertedValsetCodes.add(code);
      insertToken(code);
    };
  });

  // ── Create Value Set button ───────────────────────────────────────────
  const btnGotoValset = document.getElementById("btn-goto-valset");
  if (btnGotoValset) {
    btnGotoValset.addEventListener("click", function (e) {
      e.preventDefault();
      const fbBase = window.location.pathname;
      const fbParams = new URLSearchParams();
      if (selectedFormulaId) fbParams.set("open_formula_id", selectedFormulaId);
      if (_returnTo) fbParams.set("return_to", _returnTo);
      if (_returnFormId) fbParams.set("form_id", _returnFormId);
      if (_returnVersionId) fbParams.set("version_id", _returnVersionId);
      if (_returnFieldId) fbParams.set("field_id", _returnFieldId);
      const returnUrl = fbParams.toString() ? fbBase + "?" + fbParams.toString() : fbBase;
      window.location.href = "/module/VALSET/?" + new URLSearchParams({ return_to: returnUrl, context: "formula" }).toString();
    });
  }

  // ── Sidebar Tabs switching logic ──────────────────────────────────────
  window.switchSidebarTab = function (tabName) {
    const tabFields = document.getElementById("tab-fields");
    const tabValsets = document.getElementById("tab-valsets");
    const panelFields = document.getElementById("panel-fields");
    const panelValsets = document.getElementById("panel-valsets");

    if (tabName === "fields") {
      tabFields.classList.add("active");
      tabValsets.classList.remove("active");
      panelFields.classList.remove("hidden");
      panelValsets.classList.add("hidden");
    } else {
      tabFields.classList.remove("active");
      tabValsets.classList.add("active");
      panelFields.classList.add("hidden");
      panelValsets.classList.remove("hidden");
    }
  };

  // ── Sample Values Drawer Toggle ───────────────────────────────────────
  window.toggleDrawer = function () {
    const drawerBody = document.getElementById("drawer-body");
    const chevron = document.getElementById("drawer-chevron");
    if (drawerBody.classList.contains("open")) {
      drawerBody.classList.remove("open");
      chevron.style.transform = "rotate(0deg)";
    } else {
      drawerBody.classList.add("open");
      chevron.style.transform = "rotate(180deg)";
    }
  };

  // ── Field palette: load on form version select change ─────────────────
  function loadFormFields(formVerId) {
    if (!formVerId) return Promise.resolve();
    const searchFieldsInput = document.getElementById("search-fields");
    if (searchFieldsInput) searchFieldsInput.value = "";

    return fetch(`/module/FORMBLD/api/version/${formVerId}`)
      .then(res => res.json())
      .then(data => {
        const fieldsPalette = document.getElementById("fields-palette");
        fieldsPalette.innerHTML = "";

        const numericTypes = ["number", "integer", "decimal", "float", "numeric", "calculated"];
        const filtered = (data.fields || []).filter(f => numericTypes.includes(f.field_type.toLowerCase()));

        if (filtered.length === 0) {
          fieldsPalette.innerHTML = '<p class="text-xs text-slate-400 italic">No numeric fields in this form.</p>';
          return;
        }

        filtered.forEach(field => {
          fieldNameMap[field.field_code] = field.field_name;

          const unit = (field.field_config && field.field_config.unit) ? field.field_config.unit : "";
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "palette-btn-field skeuo-chip skeuo-chip-field flex items-center justify-between w-full text-left";
          btn.setAttribute("draggable", "true");
          btn.dataset.code = field.field_code;
          btn.innerHTML = `
            <span class="font-semibold text-slate-700 truncate flex-1 mr-1.5">${field.field_name}</span>
            ${unit ? `<span class="text-[9px] text-slate-400 font-mono whitespace-nowrap">${unit}</span>` : ""}
          `;
          btn.onclick = () => insertToken(field.field_code);
          fieldsPalette.appendChild(btn);
        });

        refreshDisplay();
      })
      .catch(err => {
        console.error("Error loading fields:", err);
      });
  }

  formVersionSelect.onchange = function () {
    loadFormFields(formVersionSelect.value);
  };

  // ── Live preview ──────────────────────────────────────────────────────
  function scanVariables() {
    const expr = expressionTextarea.value || "";
    const matches = expr.match(/[a-zA-Z_][a-zA-Z0-9_]*/g) || [];
    const forbidden = new Set(["min", "max", "sum_months"]);
    const seen = new Set();
    const unique = [];
    matches.forEach(m => {
      if (!forbidden.has(m.toLowerCase()) && !seen.has(m)) {
        seen.add(m);
        unique.push(m);
      }
    });
    return unique;
  }

  function scanVariablesAndInitPreview() {
    const variables = scanVariables();

    const prevValues = {};
    previewInputsGrid.querySelectorAll(".preview-var-input").forEach(inp => {
      prevValues[inp.dataset.var] = inp.value;
    });

    previewInputsGrid.innerHTML = "";

    if (variables.length === 0) {
      previewInputsGrid.innerHTML = '<p class="col-span-2 text-xs text-slate-400 italic">No variables detected in the formula expression yet.</p>';
      previewResultValue.textContent = "—";
      previewResultValue.className = "text-2xl font-black text-slate-300 tabular-nums";
      return;
    }

    variables.forEach(v => {
      const wrapper = document.createElement("div");
      wrapper.className = "flex flex-col space-y-1";
      const val = prevValues[v] !== undefined ? prevValues[v] : "1.0";
      const friendlyName = fieldNameMap[v];
      const labelHtml = friendlyName
        ? `<span class="text-[11px] font-bold text-slate-700 truncate">${friendlyName}</span><span class="text-[9px] font-mono text-slate-400">${v}</span>`
        : `<span class="text-[10px] font-bold text-slate-500 font-mono">${v}</span>`;
      wrapper.innerHTML = `
        <div class="flex flex-col">${labelHtml}</div>
        <input type="number" step="any" value="${val}" data-var="${v}"
          class="preview-var-input block w-full rounded border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-xs h-9 px-3 border skeuo-input">
      `;
      previewInputsGrid.appendChild(wrapper);
    });

    previewInputsGrid.querySelectorAll(".preview-var-input").forEach(input => {
      input.oninput = runLivePreview;
    });

    runLivePreview();
  }

  function runLivePreview() {
    const expr = expressionTextarea.value;
    if (!expr || !expr.trim()) {
      previewResultValue.textContent = "—";
      previewResultValue.className = "text-2xl font-black text-slate-300 tabular-nums";
      return;
    }
    const values = {};
    previewInputsGrid.querySelectorAll(".preview-var-input").forEach(input => {
      values[input.dataset.var] = input.value.trim();
    });

    if (window.FormulaRuntime) {
      if (typeof window.FormulaRuntime.validate === "function") {
        const validation = window.FormulaRuntime.validate(expr);
        if (!validation.valid) {
          previewResultValue.textContent = validation.error || "Error";
          previewResultValue.className = "max-w-xs text-right text-xs font-bold leading-tight text-rose-600";
          return;
        }
      }
      const result = window.FormulaRuntime.evaluate(expr, values);
      if (result !== null && result !== undefined && !isNaN(result)) {
        previewResultValue.textContent = parseFloat(result.toFixed(6));
        previewResultValue.className = "text-2xl font-black text-indigo-900 tabular-nums";
      } else {
        previewResultValue.textContent = "Error";
        previewResultValue.className = "text-xl font-black text-rose-500 tabular-nums";
      }
    }
  }

  // Update code preview when name changes (new formula only)
  dfName.addEventListener("input", function () {
    if (selectedFormulaId === null) updateCodeDisplay(dfName.value);
  });

  // ── Validate syntax ───────────────────────────────────────────────────
  btnValidate.onclick = function () {
    const expression = expressionTextarea.value.trim();
    if (!expression) {
      showToast("Formula expression is empty.", "error");
      return;
    }
    const variables = scanVariables();
    fetch("/module/FRMULA/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expression, field_codes: variables })
    })
      .then(res => res.json())
      .then(data => {
        validationResultContainer.classList.remove("hidden");
        if (data.valid) {
          validationResult.className = "p-2 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100";
          validationResult.textContent = "✓ Formula syntax is valid.";
        } else {
          validationResult.className = "p-2 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-100";
          validationResult.textContent = `⚠ Syntax error: ${data.error || "Invalid expression."}`;
        }
      })
      .catch(() => showToast("Error checking syntax.", "error"));
  };

  // ── Save Draft ────────────────────────────────────────────────────────
  btnSaveFormula.onclick = async function () {
    const expression = expressionTextarea.value.trim();
    if (!expression) {
      showToast("Formula expression is empty.", "error");
      return;
    }
    const name = dfName.value.trim();
    if (!name) {
      showToast("Formula name is required.", "error");
      return;
    }

    const variables = scanVariables();
    const tokens = {};
    variables.forEach(v => { tokens[v] = v; });
    insertedValsetCodes.forEach(c => { if (variables.includes(c)) tokens[c] = c; });
    const field_codes = [...new Set([...variables, ...insertedValsetCodes])];

    btnSaveFormula.disabled = true;
    const originalText = btnSaveFormula.textContent;
    btnSaveFormula.textContent = "Saving…";

    try {
      const validateRes = await fetch("/module/FRMULA/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expression, field_codes })
      });
      const validateData = await validateRes.json();
      if (!validateData.valid) {
        showToast(`Syntax error: ${validateData.error}`, "error");
        return;
      }

      if (selectedFormulaId === null) {
        const code = slugify(name);
        if (!code) { showToast("Could not generate a code from that name.", "error"); return; }
        const createRes = await fetch("/module/FRMULA/api", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, code, expression, tokens })
        });
        const createData = await createRes.json();
        if (createData.error) {
          showToast(createData.error, "error");
        } else {
          showToast("Formula created successfully!");
          selectedFormulaId = createData.data && createData.data.id ? createData.data.id : selectedFormulaId;
          selectedVersionId = createData.data && createData.data.version_id ? createData.data.version_id : selectedVersionId;
          if (selectedVersionId) {
            loadVersionDetails(selectedVersionId);
          }
        }
      } else {
        const putRes = await fetch(`/module/FRMULA/api/${selectedFormulaId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name })
        });
        const putData = await putRes.json();
        if (putData.error) { showToast(putData.error, "error"); return; }

        const draftRes = await fetch(`/module/FRMULA/api/${selectedFormulaId}/new-version`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expression, tokens })
        });
        const draftData = await draftRes.json();
        if (draftData.error) {
          showToast(draftData.error, "error");
        } else {
          showToast("Formula draft saved successfully!");
          if (draftData.data && draftData.data.version_id) selectedVersionId = draftData.data.version_id;
          loadVersionDetails(selectedVersionId);
        }
      }
    } catch (err) {
      console.error("Error saving formula:", err);
      showToast("Failed to save formula. Check console for details.", "error");
    } finally {
      btnSaveFormula.disabled = false;
      btnSaveFormula.textContent = originalText;
    }
  };

  // ── Publish Version ───────────────────────────────────────────────────
  btnPublishFormula.onclick = async function () {
    if (!selectedVersionId) return;
    if (!confirm("Publish this formula version? It will become active and immutable.")) return;

    btnPublishFormula.disabled = true;
    const originalText = btnPublishFormula.textContent;
    btnPublishFormula.textContent = "Publishing…";

    try {
      const res = await fetch(`/module/FRMULA/api/version/${selectedVersionId}/publish`, { method: "POST" });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("Formula published successfully!");
        if (_returnTo) {
          const returnParams = new URLSearchParams();
          returnParams.set("prefill_formula", selectedVersionId);
          if (_returnFieldId) returnParams.set("field_id", _returnFieldId);
          if (_returnFormId) returnParams.set("form_id", _returnFormId);
          if (_returnVersionId) returnParams.set("version_id", _returnVersionId);
          window.location.href = _returnTo + "?" + returnParams.toString();
        } else {
          showList();
        }
      }
    } catch (err) {
      console.error("Error publishing formula:", err);
      showToast("Failed to publish formula.", "error");
    } finally {
      btnPublishFormula.disabled = false;
      btnPublishFormula.textContent = originalText;
    }
  };

  // ── Modal ─────────────────────────────────────────────────────────────
  window.startNewFormula = function () {
    modalCreate.classList.remove("hidden");
    const nameInput = document.getElementById("formula-name");
    nameInput.value = "";
    setTimeout(() => nameInput.focus(), 50);
  };

  btnCloseModal.onclick = () => modalCreate.classList.add("hidden");
  btnCancelModal.onclick = () => modalCreate.classList.add("hidden");

  formCreateFormula.onsubmit = function (e) {
    e.preventDefault();
    const name = document.getElementById("formula-name").value.trim();
    if (!name) { showToast("Formula name is required.", "error"); return; }
    modalCreate.classList.add("hidden");
    openNewFormulaEditor(name);
  };

  // ── Search & Filter Logic ─────────────────────────────────────────────
  const searchFieldsInput = document.getElementById("search-fields");
  const searchValsetsInput = document.getElementById("search-valsets");

  if (searchFieldsInput) {
    searchFieldsInput.addEventListener("input", function () {
      const q = searchFieldsInput.value.toLowerCase().trim();
      document.querySelectorAll("#fields-palette .palette-btn-field").forEach(btn => {
        const name = btn.querySelector("span").textContent.toLowerCase();
        const code = btn.dataset.code ? btn.dataset.code.toLowerCase() : "";
        if (name.includes(q) || code.includes(q)) {
          btn.style.display = "flex";
        } else {
          btn.style.display = "none";
        }
      });
    });
  }

  if (searchValsetsInput) {
    searchValsetsInput.addEventListener("input", function () {
      const q = searchValsetsInput.value.toLowerCase().trim();
      document.querySelectorAll("#valsets-palette .palette-btn-valset").forEach(btn => {
        const label = btn.querySelector("span").textContent.toLowerCase();
        const desc = btn.querySelector("span:last-child") ? btn.querySelector("span:last-child").textContent.toLowerCase() : "";
        const code = btn.dataset.code ? btn.dataset.code.toLowerCase() : "";
        if (label.includes(q) || desc.includes(q) || code.includes(q)) {
          btn.style.display = "flex";
        } else {
          btn.style.display = "none";
        }
      });
    });
  }

  // ── Initial load ──────────────────────────────────────────────────────
  const initialFormVerId = formVersionSelect.value;
  loadFormFields(initialFormVerId).then(() => {
    if (_openVersionId) {
      loadVersionDetails(_openVersionId);
    } else if (_returnFieldId) {
      const friendlyName = fieldNameMap[_returnFieldId] || _returnFieldId;
      openNewFormulaEditor(friendlyName);
    } else {
      const landingView = document.getElementById("landing-view");
      if (editorView) editorView.classList.add("hidden");
      if (listView) listView.classList.add("hidden");
      if (landingView) landingView.classList.remove("hidden");
    }
  });
});
