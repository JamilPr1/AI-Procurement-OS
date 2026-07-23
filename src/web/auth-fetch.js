/** Attach CRM session token to all /api/* requests (except login). */
(function () {
  function getUser() {
    try {
      return JSON.parse(sessionStorage.getItem("crm_user") || "null");
    } catch {
      return null;
    }
  }
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function (url, options) {
    const opts = options ? { ...options } : {};
    const path = String(url);
    const user = getUser();
    if (
      user?.token &&
      path.startsWith("/api/") &&
      !path.startsWith("/api/auth/login")
    ) {
      const headers = new Headers(opts.headers || {});
      if (!headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${user.token}`);
      }
      opts.headers = headers;
    }
    return nativeFetch(url, opts);
  };
})();
