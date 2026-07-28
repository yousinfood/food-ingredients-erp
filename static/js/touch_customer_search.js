(function () {
  "use strict";

  var MIN_CHARS = 1;
  var ASSET_TAG = "20260728kbd1";
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

    function emptyHomePanelHtml() {
      return (
        '<div id="touch-search-results-panel" class="touch-search-results-panel touch-search-results-panel--home" data-query=""></div>'
      );
    }

    function updateKeyboardInset() {
      var vv = window.visualViewport;
      if (!vv) return;
      var inset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      document.documentElement.style.setProperty("--touch-keyboard-pad", inset + "px");
      document.body.classList.toggle("touch-keyboard-open", inset > 48);
    }

    function bindHomeKeyboardViewport() {
      if (!isHomeSearch) return;
      var vv = window.visualViewport;
      if (!vv) return;
      var onVv = function () {
        updateKeyboardInset();
      };
      vv.addEventListener("resize", onVv);
      vv.addEventListener("scroll", onVv);
      input.addEventListener("focus", function () {
        updateKeyboardInset();
        window.requestAnimationFrame(function () {
          var sticky = form.closest(".touch-home-app__search-sticky");
          if (sticky && sticky.scrollIntoView) {
            sticky.scrollIntoView({ block: "start", behavior: "auto" });
          } else if (input.scrollIntoView) {
            input.scrollIntoView({ block: "center", behavior: "auto" });
          }
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

    function runFetch(showAll) {
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
        (isHomeSearch ? "&home=1" : "");

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
      input.focus();
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
          runFetch(false);
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
