(function () {
  // Canonical escaping/formatting/toast helpers, shared across pages that load
  // their own JS file with no build step (see README "Running Tests"/Module
  // Prefix Reference). Load this script before any file that references
  // window.UIHelpers.

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatDateTime(value, fallback = "—") {
    if (!value) return fallback;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  }

  function formatDate(dateStr) {
    return formatDateTime(dateStr, "—");
  }

  function formatShortDate(dateStr) {
    if (!dateStr) return "—";
    const date = new Date(dateStr);
    if (Number.isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

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
      type === "success"
        ? "bg-emerald-50 border-emerald-200 text-emerald-800"
        : type === "warning" || type === "warn"
          ? "bg-amber-50 border-amber-200 text-amber-800"
          : "bg-rose-50 border-rose-200 text-rose-800",
    ].join(" ");
    toast.innerHTML = `<span>${escapeHtml(message)}</span><button class="ml-4 font-normal text-slate-400 hover:text-slate-600" type="button">✕</button>`;
    toast.querySelector("button").onclick = () => toast.remove();
    container.appendChild(toast);
    setTimeout(() => toast.classList.remove("translate-y-2", "opacity-0"), 10);
    setTimeout(() => {
      toast.classList.add("translate-y-2", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Autosave responses race against further local edits made while the
  // request was in flight: naively applying every key the server echoes back
  // can clobber a newer local edit with the server's stale echo of what was
  // actually sent. `sent` must be a snapshot of the values object taken at the
  // exact moment the request body was serialized (not any earlier point --
  // an await between "user's edit" and "request sent" is itself a window
  // where a later edit could slip in ahead of the snapshot). A field is only
  // updated from `serverValues` if its current local value still strictly
  // equals what was sent for it; anything that changed locally since is left
  // alone for the next debounced autosave to pick up and persist correctly.
  // Mutates `current` in place. Returns the list of field codes skipped as
  // stale, for callers that want to avoid re-touching those in the DOM too.
  function reconcileAutosaveResponse(current, sent, serverValues) {
    const skipped = [];
    Object.keys(serverValues).forEach((code) => {
      if (current[code] === sent[code]) {
        current[code] = serverValues[code];
      } else {
        skipped.push(code);
      }
    });
    return skipped;
  }

  window.UIHelpers = {
    escapeHtml,
    formatDate,
    formatDateTime,
    formatShortDate,
    showToast,
    reconcileAutosaveResponse,
  };
})();
