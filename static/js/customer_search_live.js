(function (global) {
  "use strict";

  var API_PATH = "/api/customers/search/";
  var REVISION_PATH = "/api/customers/revision/";
  var EVENTS_PATH = "/api/customers/events/";
  var REVISION_POLL_MS = 3000;
  var ASSET_TAG = "20260803live-v1";

  function buildSearchUrl(params) {
    var q = (params && params.q) || "";
    var url = API_PATH + "?q=" + encodeURIComponent(q);
    if (params && params.home) url += "&home=1";
    if (params && params.more) url += "&more=1";
    if (params && params.voice) url += "&voice=1";
    if (params && params.alts && params.alts.length) {
      params.alts.forEach(function (alt) {
        if (alt) url += "&alt=" + encodeURIComponent(alt);
      });
    }
    return url;
  }

  function fetchSearch(params) {
    var url = buildSearchUrl(params || {});
    var options = {
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
      cache: "no-store",
    };
    if (params && params.signal) options.signal = params.signal;
    return fetch(url, options).then(function (res) {
      return res.json().then(function (data) {
        return {
          status: res.status,
          ok: res.ok && data && data.ok,
          data: data || {},
        };
      });
    });
  }

  function fetchRevision() {
    return fetch(REVISION_PATH, {
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      cache: "no-store",
    }).then(function (res) {
      return res.json();
    });
  }

  function subscribeLiveRefresh(onChange) {
    if (typeof onChange !== "function") {
      return function () {};
    }

    var stopped = false;
    var pollTimer = null;
    var eventSource = null;
    var lastVersion = null;

    function notify(version) {
      if (stopped || typeof version !== "number") return;
      if (lastVersion !== null && version !== lastVersion) {
        onChange({ version: version });
      }
      lastVersion = version;
    }

    function startPolling() {
      if (pollTimer || stopped) return;
      pollTimer = global.setInterval(function () {
        fetchRevision()
          .then(function (data) {
            if (data && data.ok) notify(data.version);
          })
          .catch(function () {
            /* ignore transient network errors */
          });
      }, REVISION_POLL_MS);
    }

    function stopPolling() {
      if (!pollTimer) return;
      global.clearInterval(pollTimer);
      pollTimer = null;
    }

    fetchRevision()
      .then(function (data) {
        if (data && data.ok) lastVersion = data.version;
      })
      .catch(function () {
        /* ignore */
      });

    if (typeof EventSource !== "undefined") {
      try {
        eventSource = new EventSource(EVENTS_PATH);
        eventSource.addEventListener("revision", function (ev) {
          try {
            var payload = JSON.parse(ev.data || "{}");
            notify(payload.version);
          } catch (e) {
            /* ignore malformed SSE payload */
          }
        });
        eventSource.onerror = function () {
          if (eventSource) {
            eventSource.close();
            eventSource = null;
          }
          startPolling();
        };
      } catch (e) {
        startPolling();
      }
    } else {
      startPolling();
    }

    return function unsubscribe() {
      stopped = true;
      stopPolling();
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    };
  }

  global.YousinCustomerSearch = {
    API_PATH: API_PATH,
    REVISION_PATH: REVISION_PATH,
    EVENTS_PATH: EVENTS_PATH,
    fetchSearch: fetchSearch,
    fetchRevision: fetchRevision,
    subscribeLiveRefresh: subscribeLiveRefresh,
    version: ASSET_TAG,
  };
})(window);
