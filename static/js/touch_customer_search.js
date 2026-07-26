(function () {
  "use strict";

  var MIN_CHARS = 1;
  var ASSET_TAG = "20260726e";
  var API_PATH = "/api/customers/search/";

  function bindForm(form) {
    if (!form || form.dataset.touchLiveSearch === "bound") return;
    form.dataset.touchLiveSearch = "bound";
    var input = form.querySelector('input[type="search"], input[name="q"]');
    if (!input) return;

    var mount =
      document.getElementById("touch-search-results-mount") ||
      document.getElementById("touch-search-results-panel") ||
      form.parentElement;
    var composing = false;
    var timer = null;
    var fetchAbort = null;

    function isComposingNow() {
      return composing || input.isComposing;
    }

    function saveCaret() {
      return { start: input.selectionStart, end: input.selectionEnd };
    }

    function restoreCaret(caret) {
      if (!caret || document.activeElement !== input) return;
      try {
        input.setSelectionRange(caret.start, caret.end);
      } catch (e) {
        /* ignore */
      }
    }

    function updateResultsHtml(html) {
      if (!mount) return;
      var caret = saveCaret();
      mount.innerHTML = html;
      restoreCaret(caret);
      if (document.activeElement !== input) {
        input.focus({ preventScroll: true });
      }
    }

    function runFetch(showAll) {
      if (isComposingNow()) return;
      var q = input.value.trim();
      if (q.length < MIN_CHARS) {
        if (!q.length) {
          updateResultsHtml(
            '<div id="touch-search-results-panel" class="touch-search-results-panel">' +
              '<p class="touch-hint touch-search-empty">輸入店名、電話、地址或客戶編號，點選結果進入客戶中心。</p></div>'
          );
          if (window.history && window.history.replaceState) {
            window.history.replaceState(null, "", form.getAttribute("action") || "/");
          }
        }
        return;
      }

      var url =
        API_PATH +
        "?q=" +
        encodeURIComponent(q) +
        (showAll ? "&more=1" : "");

      if (fetchAbort) fetchAbort.abort();
      fetchAbort = new AbortController();

      fetch(url, {
        headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
        signal: fetchAbort.signal,
      })
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (!data || !data.ok) return;
          if (data.redirect) {
            window.location.href = data.redirect;
            return;
          }
          if (typeof data.html === "string") {
            updateResultsHtml(data.html);
          }
          if (window.history && window.history.replaceState) {
            var base = form.getAttribute("action") || "/";
            var next = base + (base.indexOf("?") >= 0 ? "&" : "?") + "q=" + encodeURIComponent(q);
            if (showAll) next += "&more=1";
            window.history.replaceState(null, "", next);
          }
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") return;
        });
    }

    function scheduleLatinFetch() {
      if (isComposingNow()) return;
      clearTimeout(timer);
      timer = setTimeout(function () {
        runFetch(false);
      }, 220);
    }

    function afterCompositionEnd() {
      clearTimeout(timer);
      timer = null;
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
          if (!isComposingNow()) runFetch(false);
        });
      });
    }

    form.addEventListener(
      "submit",
      function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (isComposingNow()) return;
        clearTimeout(timer);
        runFetch(false);
      },
      true
    );

    input.addEventListener("compositionstart", function () {
      composing = true;
      clearTimeout(timer);
      if (fetchAbort) fetchAbort.abort();
    });

    input.addEventListener("compositionupdate", function () {
      composing = true;
      clearTimeout(timer);
    });

    input.addEventListener("compositionend", function () {
      composing = false;
      afterCompositionEnd();
    });

    input.addEventListener("input", function (e) {
      if (isComposingNow() || (e && e.isComposing)) {
        clearTimeout(timer);
        return;
      }
      scheduleLatinFetch();
    });

    input.addEventListener("keydown", function (e) {
      if (!isComposingNow() && !(e && e.isComposing)) return;
      clearTimeout(timer);
      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
      }
    });

    if (mount) {
      mount.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-touch-search-more]");
        if (!btn) return;
        e.preventDefault();
        runFetch(true);
      });
    }
  }

  document.querySelectorAll(".touch-search-form").forEach(bindForm);
  window.__touchCustomerSearchVersion = ASSET_TAG;
})();
