(function () {
  "use strict";

  /** 至少 1 字即搜尋；資料量變大前不提高到 2 字（見 customer_search.py） */
  var MIN_CHARS = 1;
  var ASSET_TAG = "20260726d";

  function bindForm(form) {
    if (!form || form.dataset.touchLiveSearch === "bound") return;
    form.dataset.touchLiveSearch = "bound";
    var input = form.querySelector('input[type="search"], input[name="q"]');
    if (!input) return;

    var composing = false;
    var timer = null;

    function isComposingNow() {
      return composing || input.isComposing;
    }

    function goSearch() {
      if (isComposingNow()) return;
      var q = input.value.trim();
      if (q.length < MIN_CHARS) {
        if (!q.length && window.location.search.indexOf("q=") !== -1) {
          window.location.href = form.getAttribute("action") || window.location.pathname;
        }
        return;
      }
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }

    function scheduleSearchAfterLatinInput() {
      if (isComposingNow()) return;
      clearTimeout(timer);
      timer = setTimeout(goSearch, 200);
    }

    function runSearchAfterComposition() {
      clearTimeout(timer);
      timer = null;
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
          if (!isComposingNow()) goSearch();
        });
      });
    }

    form.addEventListener(
      "submit",
      function (e) {
        if (isComposingNow()) {
          e.preventDefault();
          e.stopPropagation();
        }
      },
      true
    );

    input.addEventListener("compositionstart", function () {
      composing = true;
      clearTimeout(timer);
      timer = null;
    });

    input.addEventListener("compositionupdate", function () {
      composing = true;
      clearTimeout(timer);
      timer = null;
    });

    input.addEventListener("compositionend", function () {
      composing = false;
      runSearchAfterComposition();
    });

    input.addEventListener("input", function (e) {
      if (isComposingNow() || (e && e.isComposing)) {
        clearTimeout(timer);
        timer = null;
        return;
      }
      scheduleSearchAfterLatinInput();
    });

    input.addEventListener("keydown", function (e) {
      if (!isComposingNow() && !(e && e.isComposing)) return;
      clearTimeout(timer);
      timer = null;
      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  }

  document.querySelectorAll(".touch-search-form").forEach(bindForm);
  window.__touchCustomerSearchVersion = ASSET_TAG;
})();
