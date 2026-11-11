// Catalog page, MCP Tools tab: expand/collapse a server row to lazy-load
// its tool list + this user's access, via GET /catalog/mcp-servers/{id}.
// Scoped to this page only — see app/templates/catalog.html's extra_scripts
// block, which only loads this file when active_tab == 'mcp-tools'.
(function () {
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderDetail(container, data) {
    container.textContent = "";

    var accessPill = el(
      "span",
      "status-pill " + (data.user_access_positive ? "status-pill-green" : "status-pill-neutral"),
      data.user_access_label
    );
    var accessRow = el("p", "mcp-detail-access");
    accessRow.appendChild(el("strong", null, "Your access: "));
    accessRow.appendChild(accessPill);
    container.appendChild(accessRow);

    if (!data.tools.length) {
      container.appendChild(el("p", "setup-note", "No enabled tools found for this server."));
      return;
    }

    var list = el("ul", "mcp-tool-list");
    data.tools.forEach(function (tool) {
      var item = el("li", "mcp-tool-item");
      item.appendChild(el("span", "mcp-tool-name", tool.title || tool.name || "—"));
      if (tool.description) {
        item.appendChild(el("span", "mcp-tool-description", tool.description));
      }
      list.appendChild(item);
    });
    container.appendChild(list);
  }

  document.querySelectorAll(".mcp-expand-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var row = btn.closest(".mcp-server-row");
      var detailRow = row.nextElementSibling;
      if (!detailRow || !detailRow.classList.contains("mcp-server-detail-row")) return;
      var container = detailRow.querySelector(".mcp-server-detail");
      var expanded = btn.getAttribute("aria-expanded") === "true";

      if (expanded) {
        detailRow.hidden = true;
        btn.setAttribute("aria-expanded", "false");
        btn.textContent = "▸";
        return;
      }

      detailRow.hidden = false;
      btn.setAttribute("aria-expanded", "true");
      btn.textContent = "▾";

      if (container.dataset.loaded === "true") return;
      container.textContent = "Loading…";
      fetch("/catalog/mcp-servers/" + encodeURIComponent(row.dataset.serverId), { cache: "no-store" })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          container.dataset.loaded = "true";
          renderDetail(container, data);
        })
        .catch(function () {
          container.textContent = "";
          container.appendChild(el("p", "setup-note", "Could not load this server's tools."));
        });
    });
  });
})();
