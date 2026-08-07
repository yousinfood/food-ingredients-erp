(function (global) {
  "use strict";

  var API_PATH = "/api/customers/search/";
  var REVISION_PATH = "/api/customers/revision/";
  var EVENTS_PATH = "/api/customers/events/";
  var REVISION_POLL_MS = 30000;
  var SEARCH_TIMEOUT_MS = 1000;
  if (typeof global.YOUSIN_CUSTOMER_SEARCH_TIMEOUT_MS === "number") {
    SEARCH_TIMEOUT_MS = global.YOUSIN_CUSTOMER_SEARCH_TIMEOUT_MS;
  }
  var ASSET_TAG = "20260806dev-timeout";

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
    var timeoutMs =
      params && typeof params.timeoutMs === "number" ? params.timeoutMs : SEARCH_TIMEOUT_MS;
    var controller = new AbortController();
    var startedAt = Date.now();
    var externalSignal = params && params.signal;
    var timedOut = false;

    if (externalSignal) {
      if (externalSignal.aborted) {
        controller.abort();
      } else {
        externalSignal.addEventListener(
          "abort",
          function () {
            controller.abort();
          },
          { once: true }
        );
      }
    }

    var timeoutId = global.setTimeout(function () {
      timedOut = true;
      controller.abort();
    }, timeoutMs);

    var options = {
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
    };

    return fetch(url, options)
      .then(function (res) {
        return res.text().then(function (bodyText) {
          var data = {};
          try {
            data = bodyText ? JSON.parse(bodyText) : {};
          } catch (parseError) {
            data = { ok: false, error: "搜尋回應格式錯誤" };
          }
          var elapsedMs = Date.now() - startedAt;
          return {
            status: res.status,
            ok: res.ok && data && data.ok,
            data: data || {},
            elapsedMs: elapsedMs,
            timedOut: false,
          };
        });
      })
      .catch(function (err) {
        var elapsedMs = Date.now() - startedAt;
        var isAbort = err && err.name === "AbortError";
        if (isAbort && timedOut) {
          return {
            status: 0,
            ok: false,
            timedOut: true,
            elapsedMs: elapsedMs,
            data: {
              ok: false,
              error: "搜尋逾時，請稍後再試",
              total: 0,
              html: "",
            },
          };
        }
        throw err;
      })
      .finally(function () {
        global.clearTimeout(timeoutId);
      });
  }

  function fetchRevision() {
    var controller = new AbortController();
    var timeoutId = global.setTimeout(function () {
      controller.abort();
    }, SEARCH_TIMEOUT_MS);
    return fetch(REVISION_PATH, {
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
    })
      .then(function (res) {
        return res.json();
      })
      .catch(function () {
        return null;
      })
      .finally(function () {
        global.clearTimeout(timeoutId);
      });
  }

  function subscribeLiveRefresh(onChange) {
    if (typeof onChange !== "function") {
      return function () {};
    }

    // P0: disable SSE — long-lived EventSource ties up gunicorn sync workers and blocks search.
    // Optional slow polling only; skip EventSource entirely until infra supports it safely.
    var stopped = false;
    var pollTimer = null;
    var lastVersion = null;

    function notify(version) {
      if (stopped || typeof version !== "number") return;
      if (lastVersion !== null && version !== lastVersion) {
        onChange({ version: version });
      }
      lastVersion = version;
    }

    pollTimer = global.setInterval(function () {
      fetchRevision()
        .then(function (data) {
          if (data && data.ok) notify(data.version);
        })
        .catch(function () {
          /* ignore transient network errors */
        });
    }, REVISION_POLL_MS);

    fetchRevision()
      .then(function (data) {
        if (data && data.ok) lastVersion = data.version;
      })
      .catch(function () {
        /* ignore */
      });

    return function unsubscribe() {
      stopped = true;
      if (pollTimer) {
        global.clearInterval(pollTimer);
        pollTimer = null;
      }
    };
  }

  global.YousinCustomerSearch = {
    API_PATH: API_PATH,
    REVISION_PATH: REVISION_PATH,
    EVENTS_PATH: EVENTS_PATH,
    SEARCH_TIMEOUT_MS: SEARCH_TIMEOUT_MS,
    fetchSearch: fetchSearch,
    fetchRevision: fetchRevision,
    subscribeLiveRefresh: subscribeLiveRefresh,
    version: ASSET_TAG,
  };
})(window);
