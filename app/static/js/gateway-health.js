// Topbar pill: the self-hosted gateway's own /health (version/status), fetched
// once on page load from /ui/gateway-health.json. Same pattern as this
// cluster's secure-chatbot-panw-gateway app's config pill.
(function () {
  const pill = document.getElementById("gateway-health-pill");
  if (!pill) return;

  fetch("/ui/gateway-health.json")
    .then((r) => r.json())
    .then((j) => {
      pill.classList.remove("status-pill-neutral");
      if (j.ok) {
        const version = (j.detail && j.detail.version) || "";
        pill.textContent = "gateway: healthy" + (version ? " (" + version + ")" : "");
        pill.classList.add("status-pill-green");
      } else {
        pill.textContent = "gateway: unreachable";
        pill.classList.add("status-pill-red");
      }
    })
    .catch(() => {
      pill.classList.remove("status-pill-neutral");
      pill.textContent = "gateway: unreachable";
      pill.classList.add("status-pill-red");
    });
})();
