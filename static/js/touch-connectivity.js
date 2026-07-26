(function () {
  "use strict";

  var banner = document.getElementById("touch-offline-banner");
  if (!banner) return;

  var retryBtn = document.getElementById("touch-offline-retry");
  var wasOffline = !navigator.onLine;

  function setOfflineVisible(visible) {
    banner.hidden = !visible;
    banner.setAttribute("aria-hidden", visible ? "false" : "true");
    document.documentElement.classList.toggle("touch-is-offline", visible);
  }

  function refreshWhenOnline() {
    if (!navigator.onLine) {
      setOfflineVisible(true);
      return;
    }
    setOfflineVisible(false);
    window.location.reload();
  }

  window.addEventListener("offline", function () {
    wasOffline = true;
    setOfflineVisible(true);
  });

  window.addEventListener("online", function () {
    if (!wasOffline) return;
    wasOffline = false;
    setOfflineVisible(false);
    window.setTimeout(function () {
      window.location.reload();
    }, 400);
  });

  if (retryBtn) {
    retryBtn.addEventListener("click", function () {
      if (navigator.onLine) {
        window.location.reload();
        return;
      }
      setOfflineVisible(true);
    });
  }

  if (!navigator.onLine) {
    setOfflineVisible(true);
  }
})();
