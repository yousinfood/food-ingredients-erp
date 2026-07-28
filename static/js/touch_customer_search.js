(function () {
  "use strict";

  var MIN_CHARS = 1;
  var ASSET_TAG = "20260728voice1";
  var API_PATH = "/api/customers/search/";

  function bindForm(form) {
    if (!form || form.dataset.touchLiveSearch === "bound") return;
    form.dataset.touchLiveSearch = "bound";
    var input = form.querySelector('input[type="search"], input[type="text"][name="q"], input[name="q"]');
    if (!input) return;

    var isHomeSearch = form.dataset.touchHomeSearch === "1";
    var micBtn = isHomeSearch ? form.querySelector(".touch-search-mic-btn") : null;

    var mount = document.getElementById("touch-search-results-mount");
    if (!mount) {
      mount =
        document.getElementById("touch-search-results-panel") ||
        form.parentElement;
    }

    var composing = false;
    var timer = null;
    var fetchAbort = null;
    var fetchSeq = 0;
    var pendingHtml = null;
    var speechRec = null;
    var userScrolledResults = false;
    var didInitialScrollIntoView = false;
    var lastScrollQuery = null;
    var activeIndex = -1;
    var lastKeyboardInset = 0;

    function emptyHomePanelHtml() {
      return (
        '<div id="touch-search-results-panel" class="touch-search-results-panel touch-search-results-panel--home" data-query=""></div>'
      );
    }

    function updateKeyboardInset() {
      var vv = window.visualViewport;
      if (!vv) return;
      var inset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      if (Math.abs(inset - lastKeyboardInset) < 2) return;
      lastKeyboardInset = inset;
      document.documentElement.style.setProperty("--touch-keyboard-pad", inset + "px");
      document.body.classList.toggle("touch-keyboard-open", inset > 48);
    }

    function mayAutoRepositionResults() {
      return !userScrolledResults;
    }

    function resetScrollBehaviorForQuery(q) {
      if (q === lastScrollQuery) return;
      lastScrollQuery = q;
      userScrolledResults = false;
      didInitialScrollIntoView = false;
      activeIndex = -1;
    }

    function markUserScrolledResults() {
      if (userScrolledResults) return;
      userScrolledResults = true;
      activeIndex = -1;
      clearResultHighlight();
      if (isHomeSearch && document.activeElement === input) {
        input.blur();
      }
    }

    function resultsScrollEl() {
      return mount;
    }

    function clearResultHighlight() {
      if (!mount) return;
      mount.querySelectorAll(".touch-home-result-btn--active").forEach(function (el) {
        el.classList.remove("touch-home-result-btn--active");
      });
    }

    function highlightFirstResult() {
      if (!mayAutoRepositionResults() || didInitialScrollIntoView || !mount) return;
      var first = mount.querySelector(".touch-home-result-btn, .touch-search-result-row a");
      if (!first) return;
      clearResultHighlight();
      first.classList.add("touch-home-result-btn--active");
      activeIndex = 0;
      if (first.scrollIntoView) {
        first.scrollIntoView({ block: "nearest", behavior: "auto" });
      }
      didInitialScrollIntoView = true;
    }

    function scrollSearchChromeIntoViewOnce() {
      if (!mayAutoRepositionResults() || didInitialScrollIntoView) return;
      var sticky = form.closest(".touch-home-app__search-sticky");
      if (sticky && sticky.scrollIntoView) {
        sticky.scrollIntoView({ block: "start", behavior: "auto" });
      } else if (input.scrollIntoView) {
        input.scrollIntoView({ block: "nearest", behavior: "auto" });
      }
      didInitialScrollIntoView = true;
    }

    function bindResultsScrollGuards() {
      if (!mount || mount.dataset.touchResultsScrollBound === "1") return;
      mount.dataset.touchResultsScrollBound = "1";
      mount.addEventListener(
        "scroll",
        function () {
          markUserScrolledResults();
        },
        { passive: true }
      );
      mount.addEventListener(
        "touchmove",
        function () {
          markUserScrolledResults();
        },
        { passive: true }
      );
    }

    bindResultsScrollGuards();

    function bindHomeKeyboardViewport() {
      if (!isHomeSearch) return;
      var vv = window.visualViewport;
      if (!vv) return;
      vv.addEventListener("resize", function () {
        updateKeyboardInset();
      });
      input.addEventListener("focus", function () {
        updateKeyboardInset();
        if (!mayAutoRepositionResults()) return;
        window.requestAnimationFrame(function () {
          if (!mayAutoRepositionResults() || didInitialScrollIntoView) return;
          var hasResults =
            mount &&
            mount.querySelector(".touch-home-result-btn, .touch-search-result-row a");
          if (hasResults) return;
          scrollSearchChromeIntoViewOnce();
          updateKeyboardInset();
        });
      });
      input.addEventListener("blur", function () {
        window.setTimeout(function () {
          updateKeyboardInset();
        }, 120);
      });
      updateKeyboardInset();
    }

    bindHomeKeyboardViewport();

    function focusInputWithoutScroll() {
      try {
        input.focus({ preventScroll: true });
      } catch (e) {
        input.focus();
      }
    }

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

    function applyResultsHtml(html) {
      if (!mount || typeof html !== "string") return;
      var caret = saveCaret();
      var scrollEl = resultsScrollEl();
      var savedScrollTop = scrollEl ? scrollEl.scrollTop : 0;
      var q = input.value.trim();

      var panel = mount.querySelector("#touch-search-results-panel");
      if (panel) {
        var wrap = document.createElement("div");
        wrap.innerHTML = html.trim();
        var next = wrap.firstElementChild;
        if (next) {
          panel.replaceWith(next);
        } else {
          panel.innerHTML = html;
        }
      } else {
        mount.innerHTML = html;
      }

      if (userScrolledResults && scrollEl) {
        scrollEl.scrollTop = savedScrollTop;
      } else if (scrollEl && q === lastScrollQuery && savedScrollTop > 0) {
        scrollEl.scrollTop = savedScrollTop;
      } else if (isHomeSearch && q.length >= MIN_CHARS && mayAutoRepositionResults()) {
        highlightFirstResult();
      }

      restoreCaret(caret);
    }

    function flushPendingHtml() {
      if (pendingHtml && !isComposingNow()) {
        var html = pendingHtml;
        pendingHtml = null;
        applyResultsHtml(html);
      }
    }

    function updateResultsHtml(html) {
      if (isComposingNow()) {
        pendingHtml = html;
        return;
      }
      applyResultsHtml(html);
    }

    function runFetch(showAll, opts) {
      opts = opts || {};
      if (isComposingNow()) return;

      var q = input.value.trim();
      if (q.length < MIN_CHARS) {
        if (!q.length && isHomeSearch) {
          updateResultsHtml(emptyHomePanelHtml());
        } else if (!q.length) {
          updateResultsHtml(
            '<div id="touch-search-results-panel" class="touch-search-results-panel">' +
              '<p class="touch-hint touch-search-empty">輸入店名、電話、地址或客戶編號，點選結果進入客戶中心。</p></div>'
          );
        }
        return;
      }

      var url =
        API_PATH +
        "?q=" +
        encodeURIComponent(q) +
        (showAll ? "&more=1" : "") +
        (isHomeSearch ? "&home=1" : "") +
        (opts.voice ? "&voice=1" : "");

      if (fetchAbort) fetchAbort.abort();
      fetchAbort = new AbortController();
      var seq = ++fetchSeq;

      fetch(url, {
        headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
        signal: fetchAbort.signal,
      })
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (seq !== fetchSeq) return;
          if (input.value.trim() !== q) return;
          if (isComposingNow()) {
            if (data && typeof data.html === "string") pendingHtml = data.html;
            return;
          }
          if (!data || !data.ok) return;
          if (opts.voice && data.normalized_q && typeof data.normalized_q === "string") {
            var normalized = data.normalized_q.trim();
            if (normalized && normalized !== input.value.trim()) {
              input.value = normalized;
              resetScrollBehaviorForQuery(normalized);
            }
          }
          if (!isHomeSearch && data.redirect) {
            window.location.href = data.redirect;
            return;
          }
          if (typeof data.html === "string") {
            updateResultsHtml(data.html);
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
      }, 280);
    }

    function afterCompositionEnd() {
      clearTimeout(timer);
      timer = null;
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
          if (isComposingNow()) return;
          flushPendingHtml();
          runFetch(false);
        });
      });
    }

    function setMicListening(on) {
      if (!micBtn) return;
      micBtn.classList.toggle("touch-search-mic-btn--listening", on);
      micBtn.setAttribute("aria-pressed", on ? "true" : "false");
    }

    function startVoiceInput() {
      focusInputWithoutScroll();
      var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        return;
      }
      if (speechRec) {
        try {
          speechRec.abort();
        } catch (e) {
          /* ignore */
        }
      }
      speechRec = new SpeechRecognition();
      speechRec.lang = "zh-TW";
      speechRec.interimResults = false;
      speechRec.maxAlternatives = 1;
      setMicListening(true);
      speechRec.onresult = function (ev) {
        var text = "";
        if (ev.results && ev.results.length) {
          text = (ev.results[0][0] && ev.results[0][0].transcript) || "";
        }
        text = text.trim();
        if (text) {
          input.value = text;
          resetScrollBehaviorForQuery(text);
          runFetch(false, { voice: true });
        }
      };
      speechRec.onerror = function () {
        setMicListening(false);
      };
      speechRec.onend = function () {
        setMicListening(false);
      };
      try {
        speechRec.start();
      } catch (e) {
        setMicListening(false);
      }
    }

    if (micBtn) {
      micBtn.addEventListener("click", function (e) {
        e.preventDefault();
        startVoiceInput();
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
      resetScrollBehaviorForQuery(input.value.trim());
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
