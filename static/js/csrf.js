(function () {
  const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
  const originalFetch = window.fetch.bind(window);

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function csrfHeaders(input, init) {
    const method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
    if (SAFE_METHODS.has(method)) return init || {};

    const url = new URL(typeof input === "string" ? input : input.url, window.location.href);
    if (url.origin !== window.location.origin) return init || {};

    const next = Object.assign({}, init || {});
    const headers = new Headers(next.headers || (input && input.headers) || {});
    if (!headers.has("X-CSRFToken")) {
      headers.set("X-CSRFToken", csrfToken());
    }
    next.headers = headers;
    return next;
  }

  window.ghgCsrfToken = csrfToken;
  window.ghgFetch = function (input, init) {
    return originalFetch(input, csrfHeaders(input, init));
  };
  window.fetch = window.ghgFetch;
})();
