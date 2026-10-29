// Token sidecar panel. Fetches /ui/token.json, renders the curated fields.
// The raw token and full claims object are kept only in these two
// module-level variables, to back the Copy buttons — never written to the
// DOM as one blob. Every claim value rendered below uses textContent, not
// innerHTML, since claim values come from the token, not from this app.
(function () {
  let rawToken = null;
  let fullClaims = null;
  let countdownTimer = null;

  const body = document.getElementById("token-sidecar-body");
  const refreshBtn = document.getElementById("token-refresh");
  const sidecar = document.getElementById("token-sidecar");
  const collapseBtn = document.getElementById("token-collapse-toggle");
  const COLLAPSE_STORAGE_KEY = "tokenSidecarCollapsed";

  // Pinned open/closed across page loads. Purely a per-viewer display
  // preference, so localStorage is the right place for it — never read
  // back by the server, never shared between viewers.
  function loadCollapsedPref() {
    try {
      return localStorage.getItem(COLLAPSE_STORAGE_KEY) === "true";
    } catch (e) {
      return false;
    }
  }

  function saveCollapsedPref(collapsed) {
    try {
      localStorage.setItem(COLLAPSE_STORAGE_KEY, collapsed ? "true" : "false");
    } catch (e) {
      // Private browsing or blocked storage: the toggle still works for
      // this page view, it just won't persist to the next one.
    }
  }

  function applyCollapsedState(collapsed) {
    if (!sidecar) return;
    sidecar.classList.toggle("collapsed", collapsed);
    if (collapseBtn) {
      collapseBtn.textContent = collapsed ? "«" : "»";
      collapseBtn.title = collapsed ? "Expand" : "Collapse";
      collapseBtn.setAttribute("aria-label", collapsed ? "Expand panel" : "Collapse panel");
    }
  }

  applyCollapsedState(loadCollapsedPref());

  if (collapseBtn) {
    collapseBtn.addEventListener("click", function () {
      const nowCollapsed = !sidecar.classList.contains("collapsed");
      applyCollapsedState(nowCollapsed);
      saveCollapsedPref(nowCollapsed);
    });
  }

  function clearCountdown() {
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function fieldBlock(label, value, { absent = false } = {}) {
    const wrap = el("div", "token-field");
    wrap.appendChild(el("span", "token-field-label", label));
    const valueNode = el(
      "div",
      "token-field-value" + (absent ? " absent" : ""),
      absent ? "(absent)" : value
    );
    wrap.appendChild(valueNode);
    return wrap;
  }

  function maskValue(value) {
    if (!value) return "";
    const last4 = value.slice(-4);
    return "••••" + last4;
  }

  function sensitiveIdField(value) {
    const wrap = el("div", "token-field");
    wrap.appendChild(el("span", "token-field-label", "Sensitive identifier"));
    const row = el("div", "token-field-value");
    if (!value) {
      row.classList.add("absent");
      row.textContent = "(absent)";
      wrap.appendChild(row);
      return wrap;
    }
    let revealed = false;
    const valueSpan = el("span", null, maskValue(value));
    const toggleBtn = el("button", "token-reveal-btn", "reveal");
    toggleBtn.type = "button";
    toggleBtn.addEventListener("click", function () {
      revealed = !revealed;
      valueSpan.textContent = revealed ? value : maskValue(value);
      toggleBtn.textContent = revealed ? "hide" : "reveal";
    });
    row.appendChild(valueSpan);
    row.appendChild(toggleBtn);
    wrap.appendChild(row);
    return wrap;
  }

  function scopeField(scopes, capability) {
    const wrap = el("div", "token-field");
    wrap.appendChild(el("span", "token-field-label", "Scope"));
    if (!scopes) {
      wrap.appendChild(el("div", "token-field-value absent", "(absent)"));
      return wrap;
    }
    const row = el("div", "token-pill-row");
    scopes.forEach(function (scope) {
      const highlight = capability && capability.scope === scope;
      row.appendChild(el("span", "token-pill" + (highlight ? " highlight" : ""), scope));
    });
    wrap.appendChild(row);

    if (capability) {
      const capRow = el("div", "token-field-value");
      const flag = el(
        "span",
        "token-capability " + (capability.present ? "present" : "absent"),
        capability.scope + " " + (capability.present ? "present ✓" : "absent ✗")
      );
      capRow.appendChild(flag);
      wrap.appendChild(capRow);
    }
    return wrap;
  }

  function structuredField(label, value) {
    const wrap = el("div", "token-field");
    wrap.appendChild(el("span", "token-field-label", label));
    if (value === undefined || value === null) {
      wrap.appendChild(el("div", "token-field-value absent", "(absent)"));
      return wrap;
    }
    const pre = el("pre", null, JSON.stringify(value, null, 2));
    const box = el("div", "token-field-value");
    box.appendChild(pre);
    wrap.appendChild(box);
    return wrap;
  }

  function formatTimestamp(seconds) {
    if (seconds === undefined || seconds === null) return null;
    return new Date(seconds * 1000).toLocaleString();
  }

  function validityField(iat, nbf, exp) {
    const wrap = el("div", "token-field");
    wrap.appendChild(el("span", "token-field-label", "Validity"));
    const box = el("div", "token-field-value");
    box.appendChild(el("div", null, "issued: " + (formatTimestamp(iat) || "(absent)")));
    box.appendChild(el("div", null, "not before: " + (formatTimestamp(nbf) || "(absent)")));
    box.appendChild(el("div", null, "expires: " + (formatTimestamp(exp) || "(absent)")));
    const countdown = el("div", "token-countdown");
    box.appendChild(countdown);
    wrap.appendChild(box);

    clearCountdown();
    if (exp) {
      const update = function () {
        const remaining = exp - Math.floor(Date.now() / 1000);
        if (remaining <= 0) {
          countdown.className = "token-countdown expired";
          countdown.textContent = "EXPIRED " + Math.floor(-remaining / 60) + "m " + (-remaining % 60) + "s ago";
          return;
        }
        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        countdown.className = "token-countdown " + (remaining > 300 ? "ok" : "warn");
        countdown.textContent = "expires in " + mins + "m " + secs + "s";
      };
      update();
      countdownTimer = setInterval(update, 1000);
    }
    return wrap;
  }

  function standardClaimsField(standardClaims) {
    const wrap = el("div", "token-field token-standard-claims");
    const details = document.createElement("details");
    const summary = el("summary", null, "Standard claims");
    details.appendChild(summary);
    details.appendChild(el("pre", null, JSON.stringify(standardClaims, null, 2)));
    wrap.appendChild(details);
    return wrap;
  }

  function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      try {
        document.execCommand("copy");
        resolve();
      } catch (err) {
        reject(err);
      } finally {
        document.body.removeChild(textarea);
      }
    });
  }

  function flashStatus(statusEl, message) {
    statusEl.textContent = message;
    setTimeout(function () {
      statusEl.textContent = "";
    }, 1800);
  }

  function copyRow(claimsAvailable) {
    const row = el("div", "token-copy-row");
    const copyTokenBtn = el("button", "token-copy-btn", "Copy token");
    copyTokenBtn.type = "button";
    const copyClaimsBtn = el("button", "token-copy-btn", "Copy claims JSON");
    copyClaimsBtn.type = "button";
    copyClaimsBtn.disabled = !claimsAvailable;
    const status = el("span", "token-copy-status", "");

    copyTokenBtn.addEventListener("click", function () {
      copyToClipboard(rawToken || "")
        .then(function () { flashStatus(status, "token copied"); })
        .catch(function () { flashStatus(status, "copy failed"); });
    });
    copyClaimsBtn.addEventListener("click", function () {
      copyToClipboard(JSON.stringify(fullClaims, null, 2))
        .then(function () { flashStatus(status, "claims copied"); })
        .catch(function () { flashStatus(status, "copy failed"); });
    });

    row.appendChild(copyTokenBtn);
    row.appendChild(copyClaimsBtn);
    row.appendChild(status);
    return row;
  }

  function render(data) {
    clearCountdown();
    body.textContent = "";
    rawToken = null;
    fullClaims = null;

    if (!data.present) {
      body.appendChild(el("p", "setup-note", "No user JWT relayed — gateway calls use the shared api-key."));
      return;
    }

    rawToken = data.raw;

    if (!data.decodable) {
      body.appendChild(el("p", "setup-note", "Token present but could not be decoded."));
      body.appendChild(copyRow(false));
      return;
    }

    fullClaims = data.claims;

    body.appendChild(scopeField(data.scopes, data.capability));
    body.appendChild(fieldBlock("Identity", data.identity, { absent: !data.identity }));
    body.appendChild(fieldBlock("Workspace", data.workspace, { absent: !data.workspace }));
    body.appendChild(sensitiveIdField(data.sensitive_id));
    body.appendChild(structuredField("Defaults", data.structured));
    body.appendChild(validityField(data.iat, data.nbf, data.exp));
    body.appendChild(standardClaimsField(data.standard_claims));
    body.appendChild(copyRow(true));
  }

  function load() {
    fetch("/ui/token.json", { cache: "no-store" })
      .then(function (res) { return res.json(); })
      .then(render)
      .catch(function () {
        body.textContent = "";
        body.appendChild(el("p", "setup-note", "Could not load token details."));
      });
  }

  function refreshToken() {
    if (refreshBtn) {
      refreshBtn.disabled = true;
      refreshBtn.textContent = "…";
    }
    fetch("/ui/token/refresh", { method: "POST", cache: "no-store" })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (result) {
        if (result.ok) {
          render(result.data);
        } else {
          body.textContent = "";
          body.appendChild(el("p", "setup-note", result.data.error || "Could not refresh the token."));
        }
      })
      .catch(function () {
        body.textContent = "";
        body.appendChild(el("p", "setup-note", "Could not refresh the token."));
      })
      .finally(function () {
        if (refreshBtn) {
          refreshBtn.disabled = false;
          refreshBtn.textContent = "↻";
        }
      });
  }

  document.addEventListener("DOMContentLoaded", load);
  if (refreshBtn) refreshBtn.addEventListener("click", refreshToken);
})();
