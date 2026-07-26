(function () {
  "use strict";

  var API_PATH = "/api/dashboard/orders/";
  var cache = Object.create(null);
  var activeFilter = null;
  var fetchAbort = null;

  function $(id) {
    return document.getElementById(id);
  }

  function statButtons() {
    var row = $("touch-dashboard-stats");
    if (!row) return [];
    return row.querySelectorAll("[data-dashboard-filter]");
  }

  function setActiveCard(filterKey) {
    statButtons().forEach(function (btn) {
      var on = btn.getAttribute("data-dashboard-filter") === filterKey;
      btn.classList.toggle("touch-stat--active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function clearActiveCards() {
    statButtons().forEach(function (btn) {
      btn.classList.remove("touch-stat--active");
      btn.setAttribute("aria-pressed", "false");
    });
  }

  function syncUrl(filterKey) {
    var url = new URL(window.location.href);
    if (filterKey) {
      url.searchParams.set("dashboard", filterKey);
    } else {
      url.searchParams.delete("dashboard");
    }
    history.replaceState({ touchDashboard: filterKey || null }, "", url);
  }

  function showPanel(filterKey, label, html) {
    var panel = $("touch-dashboard-panel");
    var title = $("touch-dashboard-panel-title");
    var body = $("touch-dashboard-panel-body");
    var recent = $("touch-recent-orders");
    if (!panel || !body) return;

    activeFilter = filterKey;
    if (title) {
      title.textContent = label || "";
    }
    body.innerHTML = html || "";
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
    if (recent) recent.hidden = true;
    setActiveCard(filterKey);
    syncUrl(filterKey);
    var back = $("touch-dashboard-back");
    if (back) back.focus();
  }

  function hidePanel() {
    var panel = $("touch-dashboard-panel");
    var recent = $("touch-recent-orders");
    if (!panel) return;

    activeFilter = null;
    panel.hidden = true;
    panel.setAttribute("aria-hidden", "true");
    if (recent) recent.hidden = false;
    clearActiveCards();
    syncUrl(null);
  }

  function showLoading() {
    var body = $("touch-dashboard-panel-body");
    if (body) {
      body.innerHTML = '<p class="touch-empty">載入中…</p>';
    }
  }

  function openFilter(filterKey) {
    if (!filterKey) return;
    if (activeFilter === filterKey && !$("touch-dashboard-panel").hidden) {
      return;
    }

    var panel = $("touch-dashboard-panel");
    if (panel) {
      panel.hidden = false;
      panel.setAttribute("aria-hidden", "false");
    }
    var recent = $("touch-recent-orders");
    if (recent) recent.hidden = true;
    setActiveCard(filterKey);

    if (cache[filterKey]) {
      var cached = cache[filterKey];
      showPanel(filterKey, cached.label, cached.html);
      return;
    }

    showLoading();
    syncUrl(filterKey);

    if (fetchAbort) {
      fetchAbort.abort();
    }
    fetchAbort = new AbortController();

    var url = API_PATH + "?dashboard=" + encodeURIComponent(filterKey);
    fetch(url, {
      signal: fetchAbort.signal,
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (res) {
        if (!res.ok) throw new Error("load failed");
        return res.json();
      })
      .then(function (data) {
        if (!data.ok) throw new Error("bad response");
        cache[filterKey] = { html: data.html, label: data.label };
        showPanel(filterKey, data.label, data.html);
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") return;
        var body = $("touch-dashboard-panel-body");
        if (body) {
          body.innerHTML =
            '<p class="touch-empty">無法載入訂單，請檢查網路後再試</p>';
        }
      });
  }

  function bind() {
    statButtons().forEach(function (btn) {
      btn.addEventListener("click", function () {
        openFilter(btn.getAttribute("data-dashboard-filter"));
      });
    });

    var back = $("touch-dashboard-back");
    if (back) {
      back.addEventListener("click", hidePanel);
    }

    var params = new URLSearchParams(window.location.search);
    var fromUrl = params.get("dashboard");
    if (fromUrl) {
      openFilter(fromUrl);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
