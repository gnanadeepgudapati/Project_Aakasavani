// Vanilla, minimal - CLAUDE.md Stack table. Rule 9: log dwell_seconds.
(function () {
  var article = document.querySelector(".article-full[data-url-hash]");
  if (!article) return;

  var hash = article.dataset.urlHash;
  var openedAt = Date.now();

  function reportDwell() {
    var dwellSeconds = Math.round((Date.now() - openedAt) / 1000);
    var payload = JSON.stringify({ dwell_seconds: dwellSeconds });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(
        "/article/" + hash + "/close",
        new Blob([payload], { type: "application/json" })
      );
    } else {
      fetch("/article/" + hash + "/close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true,
      });
    }
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") reportDwell();
  });
})();
