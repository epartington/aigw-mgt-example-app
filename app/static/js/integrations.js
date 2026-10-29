// Integrations page: platform tabs and code-block copy buttons for the
// setup cards. Scoped to this page only — not loaded on every page, see
// app/templates/integrations.html's extra_scripts block.
(function () {
  document.querySelectorAll(".setup-tabs").forEach(function (tabGroup) {
    var buttons = tabGroup.querySelectorAll(".setup-tab-btn");
    var panels = tabGroup.querySelectorAll(".setup-tab-panel");

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        buttons.forEach(function (b) { b.classList.remove("active"); });
        panels.forEach(function (p) { p.classList.remove("active"); });
        btn.classList.add("active");
        var target = tabGroup.querySelector(
          '.setup-tab-panel[data-tab="' + btn.dataset.tab + '"]'
        );
        if (target) target.classList.add("active");
      });
    });
  });

  function copyText(text, btn) {
    var originalLabel = btn.textContent;
    function done(ok) {
      btn.textContent = ok ? "Copied" : "Copy failed";
      setTimeout(function () {
        btn.textContent = originalLabel;
      }, 1500);
    }

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { done(true); }).catch(function () { done(false); });
      return;
    }

    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    try {
      document.execCommand("copy");
      done(true);
    } catch (e) {
      done(false);
    } finally {
      document.body.removeChild(textarea);
    }
  }

  document.querySelectorAll(".code-copy-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var codeEl = document.getElementById(btn.dataset.copyTarget);
      if (codeEl) copyText(codeEl.textContent, btn);
    });
  });
})();
