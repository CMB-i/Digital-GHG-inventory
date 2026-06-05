document.addEventListener("DOMContentLoaded", function () {
  let table;
  let selectedValSetId = null;
  let selectedVersionId = null;
  let currentPermissions = {};

  const listContainer = document.getElementById("valset-list");
  const detailsPanel = document.getElementById("details-panel");
  const emptyState = document.getElementById("details-empty-state");
  const btnCreateValSet = document.getElementById("btn-create-valset");
  const modalCreate = document.getElementById("modal-create");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const btnCancelModal = document.getElementById("btn-cancel-modal");
  const formCreateValSet = document.getElementById("form-create-valset");
  const versionSelect = document.getElementById("version-select");
  const statusBar = document.getElementById("status-bar");
  const entryActions = document.getElementById("entry-actions");
  const btnAddEntry = document.getElementById("btn-add-entry");
  const btnSaveEntries = document.getElementById("btn-save-entries");
  
  // Rejection modal elements
  const modalReject = document.getElementById("modal-reject");
  const btnCloseReject = document.getElementById("btn-close-reject");
  const btnCancelReject = document.getElementById("btn-cancel-reject");
  const formRejectVersion = document.getElementById("form-reject-version");

  // ── Toast Helper ──────────────────────────────────────────────────────────
  function showToast(message, type = "success") {
    // Reuse container at top of page if it exists, otherwise inject one
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
      type === "success"
        ? "bg-emerald-50 border-emerald-200 text-emerald-800"
        : type === "warning"
          ? "bg-amber-50 border-amber-200 text-amber-800"
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

  // ── Button loading state helpers ──────────────────────────────────────────
  function setLoading(btn, loading, loadingText = "Please wait…") {
    if (loading) {
      btn.dataset.origText = btn.textContent;
      btn.textContent = loadingText;
      btn.disabled = true;
    } else {
      btn.textContent = btn.dataset.origText || btn.textContent;
      btn.disabled = false;
    }
  }

  // Fetch and display Value Sets
  function loadValueSets(selectId = null) {
    listContainer.innerHTML = '<li class="p-6 text-center text-slate-400 italic text-sm">Loading value sets...</li>';
    fetch("/module/VALSET/api")
      .then((res) => res.json())
      .then((data) => {
        listContainer.innerHTML = "";
        if (data.length === 0) {
          listContainer.innerHTML = '<li class="p-6 text-center text-slate-400 italic text-sm">No value sets created yet.</li>';
          return;
        }

        data.forEach((item) => {
          const li = document.createElement("li");
          li.className = `p-4 hover:bg-slate-50 cursor-pointer transition-all flex flex-col space-y-1 ${
            selectedValSetId === item.id ? "bg-indigo-50/50 border-l-4 border-indigo-600 pl-3" : ""
          }`;
          
          let badgeColor = "bg-slate-100 text-slate-700";
          if (item.latest_version_status === "Approved") badgeColor = "bg-emerald-100 text-emerald-800";
          else if (item.latest_version_status === "Submitted") badgeColor = "bg-amber-100 text-amber-800";
          else if (item.latest_version_status === "Rejected") badgeColor = "bg-rose-100 text-rose-800";

          li.innerHTML = `
            <div class="flex items-center justify-between">
              <span class="font-bold text-sm text-slate-800">${item.name}</span>
              <span class="text-[10px] px-2 py-0.5 rounded-full font-bold ${badgeColor}">v${item.latest_version_num || 1}: ${item.latest_version_status || "Draft"}</span>
            </div>
            <div class="flex items-center justify-between text-xs text-slate-400">
              <span class="font-mono">${item.code}</span>
              <span>${item.description ? item.description.substring(0, 40) + "..." : ""}</span>
            </div>
          `;

          li.onclick = () => {
            selectedValSetId = item.id;
            // Update active list highlighting
            Array.from(listContainer.children).forEach(child => child.classList.remove("bg-indigo-50/50", "border-l-4", "border-indigo-600", "pl-3"));
            li.classList.add("bg-indigo-50/50", "border-l-4", "border-indigo-600", "pl-3");
            loadVersion(item.latest_version_id);
          };

          listContainer.appendChild(li);
        });

        // Automatically select if specified
        if (selectId) {
          selectedValSetId = selectId;
          const found = data.find(x => x.id === selectId);
          if (found) {
            loadVersion(found.latest_version_id);
          }
        }
      });
  }

  // Fetch detail for a specific version
  function loadVersion(versionId) {
    if (!versionId) return;
    
    fetch(`/module/VALSET/api/version/${versionId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load value set version details.");
        return res.json();
      })
      .then((data) => {
        selectedVersionId = data.version.id;
        currentPermissions = data.permissions || {};
        
        // Show panel
        emptyState.classList.add("hidden");
        detailsPanel.classList.remove("hidden");

        // Set text details
        document.getElementById("detail-name").textContent = data.value_set.name;
        document.getElementById("detail-code").textContent = data.value_set.code;
        document.getElementById("detail-desc").textContent = data.value_set.description || "No description provided.";

        // Populate Version Selector
        versionSelect.innerHTML = "";
        data.all_versions.forEach((v) => {
          const opt = document.createElement("option");
          opt.value = v.id;
          opt.textContent = `Version ${v.version_number} (${v.status})`;
          if (v.id === selectedVersionId) {
            opt.selected = true;
          }
          versionSelect.appendChild(opt);
        });

        // Setup status bar
        setupStatusBar(data.version);

        // Render Tabulator Table
        initTabulatorTable(data.entries, currentPermissions.can_edit);
      })
      .catch((err) => {
        showToast(err.message, "error");
      });
  }

  versionSelect.onchange = function () {
    loadVersion(parseInt(versionSelect.value));
  };

  // Render status info and relevant actions
  function setupStatusBar(version) {
    statusBar.innerHTML = "";
    
    // Status Badge
    let statusClass = "bg-slate-100 text-slate-800";
    if (version.status === "Approved") statusClass = "bg-emerald-100 text-emerald-800";
    else if (version.status === "Submitted") statusClass = "bg-amber-100 text-amber-800";
    else if (version.status === "Rejected") statusClass = "bg-rose-100 text-rose-800";

    const badgeContainer = document.createElement("div");
    badgeContainer.className = "flex items-center space-x-2";
    badgeContainer.innerHTML = `
      <span class="px-2.5 py-1 rounded-md text-xs font-bold ${statusClass}">${version.status.toUpperCase()}</span>
      <span class="text-[11px] text-slate-500 font-medium">Effective: ${version.effective_from || "Immediately"}</span>
    `;
    statusBar.appendChild(badgeContainer);

    // Actions Button Container
    const actionContainer = document.createElement("div");
    actionContainer.className = "flex items-center space-x-2 mt-2 sm:mt-0";

    // Show rejection message if exists
    if (version.status === "Rejected" && version.rejection_reason) {
      const rejectMsg = document.createElement("div");
      rejectMsg.className = "w-full text-xs bg-rose-50 border border-rose-100 text-rose-700 p-2.5 rounded-lg mt-3 font-medium";
      rejectMsg.innerHTML = `<strong>Rejection Reason:</strong> ${version.rejection_reason} (by ${version.rejected_by || "Approver"})`;
      statusBar.appendChild(rejectMsg);
    }

    // Toggle Entry actions buttons
    if (currentPermissions.can_edit) {
      entryActions.classList.remove("hidden");
    } else {
      entryActions.classList.add("hidden");
    }

    // Add buttons dynamically based on permission payload
    if (currentPermissions.can_submit) {
      const btnSubmit = document.createElement("button");
      btnSubmit.className = "px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded shadow transition-colors";
      btnSubmit.textContent = "Submit for Approval";
      btnSubmit.onclick = () => submitForApproval();
      actionContainer.appendChild(btnSubmit);
    }

    if (currentPermissions.can_approve) {
      const btnApprove = document.createElement("button");
      btnApprove.className = "px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded shadow transition-colors";
      btnApprove.textContent = "Approve";
      btnApprove.onclick = () => approveVersion();
      actionContainer.appendChild(btnApprove);

      const btnReject = document.createElement("button");
      btnReject.className = "px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded shadow transition-colors";
      btnReject.textContent = "Reject";
      btnReject.onclick = () => {
        modalReject.classList.remove("hidden");
      };
      actionContainer.appendChild(btnReject);
    }

    if (currentPermissions.can_create_version) {
      const btnCreateVer = document.createElement("button");
      btnCreateVer.className = "px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded shadow transition-colors";
      btnCreateVer.textContent = "+ Create New Version Draft";
      btnCreateVer.onclick = () => createNewDraft();
      actionContainer.appendChild(btnCreateVer);
    }

    statusBar.appendChild(actionContainer);
  }

  // Initialize Tabulator Grid
  function initTabulatorTable(entries, isEditable) {
    if (table) {
      table.destroy();
    }

    table = new Tabulator("#entries-table", {
      data: entries,
      layout: "fitColumns",
      placeholder: "No entries configured. Add rows to this value set.",
      columns: [
        {
          title: "Entry Code",
          field: "entry_code",
          editor: isEditable ? "input" : false,
          validator: "required",
          headerSort: false,
          widthGrow: 1
        },
        {
          title: "Entry Label / Value",
          field: "entry_label",
          editor: isEditable ? "input" : false,
          validator: "required",
          headerSort: false,
          widthGrow: 2
        },
        {
          title: "Display Order",
          field: "display_order",
          editor: isEditable ? "number" : false,
          validator: "required",
          headerSort: true,
          width: 120,
          sorter: "number"
        },
        {
          title: "Active",
          field: "is_active",
          formatter: "tickCross",
          hozAlign: "center",
          headerSort: false,
          width: 90,
          cellClick: function (e, cell) {
            if (isEditable) {
              cell.setValue(!cell.getValue());
            }
          }
        },
        {
          title: "",
          formatter: "html",
          hozAlign: "center",
          headerSort: false,
          width: 70,
          cellClick: function (e, cell) {
            if (isEditable) {
              cell.getRow().delete();
            }
          },
          formatterParams: {
            value: isEditable ? "<span class='text-rose-600 cursor-pointer hover:underline text-xs font-semibold'>Delete</span>" : ""
          }
        }
      ]
    });
  }

  // Add a row to the table
  btnAddEntry.onclick = function () {
    if (!table) return;
    const maxOrder = table.getData().reduce((max, item) => Math.max(max, item.display_order || 0), 0);
    table.addRow({
      entry_code: "",
      entry_label: "",
      display_order: maxOrder + 1,
      is_active: true
    });
  };

  // Save entries
  btnSaveEntries.onclick = async function () {
    if (!selectedVersionId) return;

    // Validate table data
    const data = table.getData();
    let hasError = false;
    data.forEach(row => {
      if (!row.entry_code || !row.entry_code.trim()) hasError = true;
      if (!row.entry_label || !row.entry_label.trim()) hasError = true;
    });

    if (hasError) {
      showToast("Please fill in Entry Code and Entry Label for all rows before saving.", "error");
      return;
    }

    setLoading(btnSaveEntries, true, "Saving…");
    try {
      const res = await fetch(`/module/VALSET/api/version/${selectedVersionId}/entries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entries: data })
      });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("Draft entries saved successfully.");
        loadVersion(selectedVersionId);
      }
    } catch (err) {
      console.error("Error saving entries:", err);
      showToast("Failed to save entries. Please try again.", "error");
    } finally {
      setLoading(btnSaveEntries, false);
    }
  };

  // Submit version for approval
  async function submitForApproval() {
    if (!selectedVersionId) return;
    if (!confirm("Are you sure you want to submit this draft version for approval?")) return;

    const btn = statusBar.querySelector("button");
    if (btn) setLoading(btn, true, "Submitting…");
    try {
      const res = await fetch(`/module/VALSET/api/version/${selectedVersionId}/submit`, {
        method: "POST"
      });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("Version submitted for approval.");
        loadVersion(selectedVersionId);
        loadValueSets();
      }
    } catch (err) {
      console.error("Error submitting:", err);
      showToast("Failed to submit. Please try again.", "error");
    }
  }

  // Approve version
  async function approveVersion() {
    if (!selectedVersionId) return;
    if (!confirm("Are you sure you want to approve this value set version? It will become active immediately.")) return;

    try {
      const res = await fetch(`/module/VALSET/api/version/${selectedVersionId}/approve`, {
        method: "POST"
      });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("Version approved and published.");
        loadVersion(selectedVersionId);
        loadValueSets();
      }
    } catch (err) {
      console.error("Error approving:", err);
      showToast("Failed to approve. Please try again.", "error");
    }
  }

  // Submit Rejection
  formRejectVersion.onsubmit = async function (e) {
    e.preventDefault();
    if (!selectedVersionId) return;
    const reason = document.getElementById("reject-reason").value;
    const submitBtn = formRejectVersion.querySelector("button[type=submit]");
    if (submitBtn) setLoading(submitBtn, true, "Rejecting…");
    try {
      const res = await fetch(`/module/VALSET/api/version/${selectedVersionId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason })
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
    } catch (err) {
      console.error("Error rejecting:", err);
      showToast("Failed to reject version. Please try again.", "error");
    } finally {
      if (submitBtn) setLoading(submitBtn, false);
    }
  };

  // Create a new draft version from Approved version
  async function createNewDraft() {
    if (!selectedValSetId) return;
    if (!confirm("Create a new draft version based on the current approved entries?")) return;

    try {
      const res = await fetch(`/module/VALSET/api/${selectedValSetId}/new-version`, {
        method: "POST"
      });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("New draft version created.");
        loadVersion(resData.data.version_id);
        loadValueSets(selectedValSetId);
      }
    } catch (err) {
      console.error("Error creating draft:", err);
      showToast("Failed to create new draft version.", "error");
    }
  }

  // Modal actions
  btnCreateValSet.onclick = () => modalCreate.classList.remove("hidden");
  btnCloseModal.onclick = () => modalCreate.classList.add("hidden");
  btnCancelModal.onclick = () => modalCreate.classList.add("hidden");

  btnCloseReject.onclick = () => modalReject.classList.add("hidden");
  btnCancelReject.onclick = () => modalReject.classList.add("hidden");

  // Create Value Set Submit
  formCreateValSet.onsubmit = async function (e) {
    e.preventDefault();
    const name = document.getElementById("valset-name").value;
    const code = document.getElementById("valset-code").value.toUpperCase().replace(/\s+/g, "_");
    const description = document.getElementById("valset-description").value;
    const submitBtn = formCreateValSet.querySelector("button[type=submit]");
    setLoading(submitBtn, true, "Creating…");
    try {
      const res = await fetch("/module/VALSET/api", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, code, description })
      });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        modalCreate.classList.add("hidden");
        document.getElementById("valset-name").value = "";
        document.getElementById("valset-code").value = "";
        document.getElementById("valset-description").value = "";
        showToast("Value set created successfully.");
        loadValueSets(resData.data.id);
      }
    } catch (err) {
      console.error("Error creating value set:", err);
      showToast("Failed to create value set. Please try again.", "error");
    } finally {
      setLoading(submitBtn, false);
    }
  };

  // Initial load
  loadValueSets();
});
