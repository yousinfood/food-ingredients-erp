(function () {
  "use strict";

  if (document.getElementById("customer-search-page")) {
    return;
  }

  var MIN_CHARS = 1;
  var ASSET_TAG = "20260802voice-ios-v3";
  var VOICE_LS_COMPLETED = "voice_permission_completed";
  var VOICE_LS_DENIED = "voice_permission_denied";
  var API_PATH = "/api/customers/search/";
  var VOICE_UNCLEAR_TEXT = "聽不清楚，請再說一次";

  function isIOSDevice() {
    var ua = navigator.userAgent || "";
    return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  function isVoiceSearchIOSEnabled() {
    return !!document.querySelector('script[src*="voice_search_ios"]');
  }

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function bindForm(form) {
    if (!form || form.dataset.touchLiveSearch === "bound") return;
    form.dataset.touchLiveSearch = "bound";
    var input = form.querySelector('input[type="search"], input[type="text"][name="q"], input[name="q"]');
    if (!input) return;
    var customerSearchInput = document.getElementById("customer-search-input") || input;

    var isHomeSearch = form.dataset.touchHomeSearch === "1";
    var voiceSearchBtn = isHomeSearch ? document.getElementById("voice-search-button") : null;
    var voiceFailureEl = isHomeSearch ? document.getElementById("voice-search-failure") : null;
    var voiceRetryBtn = isHomeSearch ? document.getElementById("voice-search-retry") : null;
    var customerSearchClearBtn = isHomeSearch ? document.getElementById("customer-search-clear") : null;
    var voiceMissTimer = null;

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
    var isListening = false;
    var voiceGotTranscript = false;
    var voiceSuccessTimer = null;
    var userScrolledResults = false;
    var lastScrollQuery = null;
    var activeIndex = -1;
    var lastKeyboardInset = 0;

    function emptyHomePanelHtml() {
      return (
        '<div id="touch-search-results-panel" class="customer-search-results-panel" data-query=""></div>'
      );
    }

    function clearSearchResults() {
      updateResultsHtml(emptyHomePanelHtml());
    }

    function clearVoiceFailureUI() {
      if (voiceMissTimer) {
        clearTimeout(voiceMissTimer);
        voiceMissTimer = null;
      }
      if (voiceFailureEl) voiceFailureEl.hidden = true;
      if (voiceRetryBtn) voiceRetryBtn.hidden = true;
    }

    function showVoiceFailure(title, sub) {
      if (!voiceFailureEl) return;
      var t = voiceFailureEl.querySelector(".voice-search-failure__title");
      var s = voiceFailureEl.querySelector(".voice-search-failure__sub");
      if (t) t.textContent = title || "沒有找到這位客戶";
      if (s) s.textContent = sub || "請再說一次";
      voiceFailureEl.hidden = false;
    }

    function syncCustomerClearButton() {
      if (!customerSearchClearBtn) return;
      var hasText = customerSearchInput.value.trim().length > 0;
      customerSearchClearBtn.hidden = !hasText;
    }

    function clearCustomerSearchInput() {
      customerSearchInput.value = "";
      resetScrollBehaviorForQuery("");
      customerSearchInput.blur();
      dismissSearchKeyboard();
      syncCustomerClearButton();
    }

    function updateKeyboardInset(force) {
      var vv = window.visualViewport;
      if (!vv) {
        if (force) {
          lastKeyboardInset = 0;
          document.documentElement.style.setProperty("--touch-keyboard-pad", "0px");
          document.documentElement.style.removeProperty("--touch-vvh");
          document.body.classList.remove("touch-keyboard-open");
        }
        return;
      }
      var inset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      if (!force && Math.abs(inset - lastKeyboardInset) < 2) return;
      lastKeyboardInset = inset;
      document.documentElement.style.setProperty("--touch-keyboard-pad", inset + "px");
      if (inset > 48) {
        var vvh = Math.round(vv.height);
        if (vvh < 200) {
          vvh = Math.max(200, Math.round(window.innerHeight - inset));
        }
        document.documentElement.style.setProperty("--touch-vvh", vvh + "px");
      } else {
        document.documentElement.style.removeProperty("--touch-vvh");
      }
      document.body.classList.toggle("touch-keyboard-open", inset > 48);
    }

    function syncKeyboardViewportAfterDismiss() {
      updateKeyboardInset(true);
      window.requestAnimationFrame(function () {
        updateKeyboardInset(true);
      });
    }

    function dismissSearchKeyboard() {
      if (document.activeElement === customerSearchInput) {
        customerSearchInput.blur();
      } else if (document.activeElement === input) {
        input.blur();
      } else {
        syncKeyboardViewportAfterDismiss();
      }
    }

    function scrollResultsIntoView() {
      if (!isHomeSearch) return;
      var target =
        document.getElementById("touch-search-results-mount") ||
        document.getElementById("touch-search-results-panel");
      if (!target) return;
      requestAnimationFrame(function () {
        setTimeout(function () {
          syncKeyboardViewportAfterDismiss();
          try {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
          } catch (err) {
            target.scrollIntoView(true);
          }
        }, 300);
      });
    }

    function submitCustomerSearch() {
      if (isComposingNow()) return;
      clearTimeout(timer);
      var q = customerSearchInput.value.trim();
      if (!q.length) {
        dismissSearchKeyboard();
        return;
      }
      resetScrollBehaviorForQuery(q);
      dismissSearchKeyboard();
      runFetch(false, { fromSubmit: true });
    }

    function isHomeSearchChromeTarget(el) {
      if (!el || !el.closest) return false;
      if (el.closest(".touch-search-input-row")) return true;
      if (el.closest("#touch-search-results-mount")) return true;
      return false;
    }

    function resetScrollBehaviorForQuery(q) {
      if (q === lastScrollQuery) return;
      lastScrollQuery = q;
      userScrolledResults = false;
      activeIndex = -1;
    }

    function markUserScrolledResults() {
      if (userScrolledResults) return;
      userScrolledResults = true;
      activeIndex = -1;
      clearResultHighlight();
    }

    function onResultsScrollStart() {
      markUserScrolledResults();
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

    function bindResultsScrollGuards() {
      if (!mount || mount.dataset.touchResultsScrollBound === "1") return;
      mount.dataset.touchResultsScrollBound = "1";
      mount.addEventListener("scroll", onResultsScrollStart, { passive: true });
      mount.addEventListener("touchmove", onResultsScrollStart, { passive: true });
    }

    bindResultsScrollGuards();

    function bindHomeKeyboardViewport() {
      if (!isHomeSearch) return;
      var vv = window.visualViewport;
      if (vv) {
        vv.addEventListener("resize", function () {
          updateKeyboardInset(true);
        });
      }
      input.addEventListener("focus", function () {
        updateKeyboardInset(true);
      });
      input.addEventListener("blur", function () {
        syncKeyboardViewportAfterDismiss();
      });
      updateKeyboardInset(true);
    }

    bindHomeKeyboardViewport();

    function bindHomeDismissKeyboard() {
      if (!isHomeSearch) return;
      var homeMain = form.closest(".touch-home-app");
      if (!homeMain || homeMain.dataset.touchDismissKbBound === "1") return;
      homeMain.dataset.touchDismissKbBound = "1";
      homeMain.addEventListener(
        "pointerdown",
        function (e) {
          if (isHomeSearchChromeTarget(e.target)) return;
          dismissSearchKeyboard();
        },
        { passive: true }
      );
    }

    bindHomeDismissKeyboard();

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
      var inputWasFocused = document.activeElement === input;
      var caret = inputWasFocused ? saveCaret() : null;
      var scrollEl = resultsScrollEl();
      var savedScrollTop = scrollEl ? scrollEl.scrollTop : 0;
      var q = customerSearchInput.value.trim();

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
      }

      if (inputWasFocused && document.activeElement === input) {
        restoreCaret(caret);
      }
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
      if (opts.fromVoice) {
        opts.voice = true;
      }
      if (isComposingNow()) return;

      var q = customerSearchInput.value.trim();
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
          if (customerSearchInput.value.trim() !== q) return;
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
          if (opts.fromVoice) {
            if (!data.total || data.total === 0) {
              handleVoiceNoCustomerFound();
              return;
            }
            if (typeof data.html === "string") {
              updateResultsHtml(data.html);
            }
            scrollResultsIntoView();
            scheduleVoiceIdleReset(1000);
            return;
          }
          if (typeof data.html === "string") {
            updateResultsHtml(data.html);
          }
          if (opts.fromSubmit) {
            scrollResultsIntoView();
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

    function voiceSearchLines() {
      if (!voiceSearchBtn) return { line1: null, line2: null };
      return {
        line1: voiceSearchBtn.querySelector(".voice-search-button__line1"),
        line2: voiceSearchBtn.querySelector(".voice-search-button__line2"),
      };
    }

    function setVoiceSearchState(mode, detail) {
      if (!voiceSearchBtn) return;
      var lines = voiceSearchLines();
      voiceSearchBtn.classList.remove(
        "voice-search-button--idle",
        "voice-search-button--starting",
        "voice-search-button--listening",
        "voice-search-button--success",
        "voice-search-button--error",
        "voice-search-button--blocked"
      );
      voiceSearchBtn.disabled = false;
      voiceSearchBtn.removeAttribute("aria-disabled");

      if (mode === "starting") {
        voiceSearchBtn.classList.add("voice-search-button--starting");
        voiceSearchBtn.disabled = true;
        voiceSearchBtn.setAttribute("aria-pressed", "true");
        if (lines.line1) lines.line1.textContent = "🔴 正在啟動麥克風…";
        if (lines.line2) lines.line2.textContent = "";
        return;
      }
      if (mode === "listening") {
        voiceSearchBtn.classList.add("voice-search-button--listening");
        voiceSearchBtn.setAttribute("aria-pressed", "true");
        if (isIOSDevice()) {
          voiceSearchBtn.disabled = false;
          if (lines.line1) lines.line1.textContent = "🔴 正在錄音";
          if (lines.line2) lines.line2.textContent = "再按一次停止";
        } else {
          voiceSearchBtn.disabled = true;
          if (lines.line1) lines.line1.textContent = "🔴 正在聽";
          if (lines.line2) lines.line2.textContent = "請說客戶名稱";
        }
        return;
      }
      if (mode === "processing") {
        voiceSearchBtn.classList.add("voice-search-button--starting");
        voiceSearchBtn.disabled = true;
        voiceSearchBtn.setAttribute("aria-pressed", "false");
        if (lines.line1) lines.line1.textContent = "🎤 正在辨識…";
        if (lines.line2) lines.line2.textContent = "";
        return;
      }
      if (mode === "success") {
        voiceSearchBtn.classList.add("voice-search-button--success");
        voiceSearchBtn.setAttribute("aria-pressed", "false");
        if (lines.line1) lines.line1.textContent = "✓ 已聽到：" + (detail || "");
        return;
      }
      if (mode === "error") {
        voiceSearchBtn.classList.add("voice-search-button--error");
        voiceSearchBtn.setAttribute("aria-pressed", "false");
        if (lines.line1) lines.line1.textContent = detail || "沒有聽清楚，請再按一次";
        if (lines.line2) lines.line2.textContent = "";
        return;
      }
      if (mode === "blocked") {
        voiceSearchBtn.classList.add("voice-search-button--blocked", "voice-search-button--error");
        voiceSearchBtn.disabled = true;
        voiceSearchBtn.setAttribute("aria-disabled", "true");
        voiceSearchBtn.setAttribute("aria-pressed", "false");
        if (lines.line1) lines.line1.textContent = "語音搜尋尚未開啟，請家人協助設定";
        if (lines.line2) lines.line2.textContent = "";
        return;
      }
      voiceSearchBtn.classList.add("voice-search-button--idle");
      voiceSearchBtn.setAttribute("aria-pressed", "false");
      voiceSearchBtn.setAttribute("aria-label", "按這裡說話找客戶");
      if (lines.line1) lines.line1.textContent = "🎤 按這裡說話找客戶";
      if (lines.line2) lines.line2.textContent = "點一下，再說客戶名稱";
    }

    function hapticVoiceTap() {
      try {
        if (navigator.vibrate) navigator.vibrate(40);
      } catch (e) {
        /* ignore */
      }
    }

    function clearVoiceSuccessTimer() {
      if (voiceSuccessTimer) {
        clearTimeout(voiceSuccessTimer);
        voiceSuccessTimer = null;
      }
    }

    function scheduleVoiceIdleReset(ms) {
      clearVoiceSuccessTimer();
      voiceSuccessTimer = setTimeout(function () {
        isListening = false;
        voiceGotTranscript = false;
        setVoiceSearchState("idle");
      }, ms || 1000);
    }

    function readVoiceFlag(key) {
      try {
        return localStorage.getItem(key) === "true";
      } catch (e) {
        return false;
      }
    }

    function writeVoiceFlag(key, value) {
      try {
        localStorage.setItem(key, value ? "true" : "false");
      } catch (e) {
        /* ignore */
      }
    }

    function isVoicePermissionDenied() {
      return readVoiceFlag(VOICE_LS_DENIED);
    }

    function markVoicePermissionDenied() {
      writeVoiceFlag(VOICE_LS_DENIED, true);
    }

    function destroySpeechRecognition() {
      if (!speechRec) return;
      speechRec.onstart = null;
      speechRec.onresult = null;
      speechRec.onerror = null;
      speechRec.onend = null;
      try {
        speechRec.abort();
      } catch (e) {
        /* ignore */
      }
      speechRec = null;
    }

    function bestVoiceTranscript(ev) {
      if (!ev.results || !ev.results.length) return "";
      var best = "";
      var bestConf = -1;
      for (var i = 0; i < ev.results.length; i++) {
        var alts = ev.results[i];
        for (var j = 0; j < alts.length; j++) {
          var alt = alts[j];
          var t = (alt.transcript || "").trim();
          var c = typeof alt.confidence === "number" ? alt.confidence : 0;
          if (t && c >= bestConf) {
            bestConf = c;
            best = t;
          }
        }
      }
      if (best) return best;
      return ((ev.results[0][0] && ev.results[0][0].transcript) || "").trim();
    }

    function voiceErrorMessage(code) {
      if (code === "no-speech") return "沒有聽到聲音，請再按一次";
      if (code === "not-allowed" || code === "service-not-allowed") {
        return "語音搜尋尚未開啟，請家人協助設定";
      }
      if (code === "audio-capture") return "目前無法使用麥克風，請改用文字搜尋";
      return "沒有聽清楚，請再按一次";
    }

    function handleVoiceRecognitionError(code) {
      isListening = false;
      voiceGotTranscript = false;
      if (code === "aborted") {
        setVoiceSearchState("idle");
        return;
      }
      if (code === "not-allowed" || code === "service-not-allowed") {
        markVoicePermissionDenied();
        setVoiceSearchState("blocked");
        return;
      }
      setVoiceSearchState("error", voiceErrorMessage(code));
    }

    function handleVoiceSearchApiFailure() {
      clearSearchResults();
      showVoiceFailure("沒有找到這位客戶", "請再說一次或改用文字搜尋");
      if (voiceRetryBtn) voiceRetryBtn.hidden = false;
      clearVoiceSuccessTimer();
      scheduleVoiceIdleReset(1500);
    }

    function handleVoiceNoCustomerFound() {
      clearSearchResults();
      showVoiceFailure("沒有找到這位客戶", "請再說一次");
      if (voiceRetryBtn) voiceRetryBtn.hidden = true;
      clearVoiceSuccessTimer();
      if (voiceMissTimer) clearTimeout(voiceMissTimer);
      voiceMissTimer = setTimeout(function () {
        customerSearchInput.value = "";
        syncCustomerClearButton();
        clearSearchResults();
        showVoiceFailure("沒有找到這位客戶", "請按下面，再說一次");
        if (voiceRetryBtn) voiceRetryBtn.hidden = false;
        setVoiceSearchState("idle");
        voiceMissTimer = null;
      }, 1000);
    }

    function prepareForNewVoiceSession() {
      customerSearchInput.value = "";
      clearSearchResults();
      clearVoiceFailureUI();
      syncCustomerClearButton();
    }

    function applyVoiceTranscript(text) {
      var resolved = (text || "").trim();
      if (!resolved) {
        showVoiceUnclear();
        return;
      }
      voiceGotTranscript = true;
      isListening = false;
      setVoiceSearchState("success", resolved);
      customerSearchInput.value = resolved;
      resetScrollBehaviorForQuery(resolved);
      customerSearchInput.blur();
      dismissSearchKeyboard();
      syncCustomerClearButton();
      runFetch(false, { fromVoice: true });
    }

    function showVoiceUnclear() {
      isListening = false;
      voiceGotTranscript = false;
      setVoiceSearchState("error", VOICE_UNCLEAR_TEXT);
    }

    function showVoiceServiceError(detail) {
      isListening = false;
      voiceGotTranscript = false;
      setVoiceSearchState("error", detail || "語音辨識暫時無法使用，請改用文字搜尋");
    }

    function beginSpeechRecognition() {
      if (isIOSDevice()) return;
      if (!voiceSearchBtn || isListening) return;

      var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        voiceSearchBtn.hidden = true;
        return;
      }

      prepareForNewVoiceSession();

      hapticVoiceTap();
      isListening = true;
      voiceGotTranscript = false;
      clearVoiceSuccessTimer();
      setVoiceSearchState("starting");

      destroySpeechRecognition();
      speechRec = new SpeechRecognition();
      speechRec.lang = "zh-TW";
      speechRec.continuous = false;
      speechRec.interimResults = false;
      speechRec.maxAlternatives = 3;

      speechRec.onstart = function () {
        setVoiceSearchState("listening");
      };

      speechRec.onresult = function (ev) {
        var text = bestVoiceTranscript(ev);
        voiceGotTranscript = true;
        if (!text) {
          handleVoiceRecognitionError("no-speech");
          return;
        }
        applyVoiceTranscript(text);
      };

      speechRec.onerror = function (ev) {
        var code = ev && ev.error ? ev.error : "";
        handleVoiceRecognitionError(code);
      };

      speechRec.onend = function () {
        isListening = false;
        voiceSearchBtn.disabled = false;
        if (voiceGotTranscript) return;
        if (
          voiceSearchBtn.classList.contains("voice-search-button--listening") ||
          voiceSearchBtn.classList.contains("voice-search-button--starting")
        ) {
          handleVoiceRecognitionError("no-speech");
        }
      };

      try {
        speechRec.start();
      } catch (e) {
        isListening = false;
        setVoiceSearchState("error", "沒有聽清楚，請再按一次");
      }
    }

    function onVoiceSearchClick(e) {
      e.preventDefault();
      if (!voiceSearchBtn || isListening) return;
      if (isVoicePermissionDenied()) {
        setVoiceSearchState("blocked");
        return;
      }
      beginSpeechRecognition();
    }

    window.__yousinTouchVoice = {
      applyTranscript: applyVoiceTranscript,
      showUnclear: showVoiceUnclear,
      showServiceError: showVoiceServiceError,
      prepareSession: prepareForNewVoiceSession,
      setState: setVoiceSearchState,
      setBlocked: function () {
        setVoiceSearchState("blocked");
      },
      isPermissionDenied: isVoicePermissionDenied,
      markPermissionDenied: markVoicePermissionDenied,
      haptic: hapticVoiceTap,
      showRetry: function () {
        if (voiceRetryBtn) voiceRetryBtn.hidden = false;
      },
    };

    function initHomeVoiceSearch() {
      if (!isHomeSearch || !voiceSearchBtn) return;
      if (isVoiceSearchIOSEnabled() && isIOSDevice()) return;
      var hasDesktopSpeech =
        !isIOSDevice() && (window.SpeechRecognition || window.webkitSpeechRecognition);
      if (!hasDesktopSpeech) {
        voiceSearchBtn.hidden = true;
        return;
      }
      if (isVoicePermissionDenied()) {
        setVoiceSearchState("blocked");
        return;
      }
      setVoiceSearchState("idle");
      voiceSearchBtn.addEventListener("click", onVoiceSearchClick);
      if (voiceRetryBtn) {
        voiceRetryBtn.addEventListener("click", function (e) {
          e.preventDefault();
          if (isVoicePermissionDenied()) {
            setVoiceSearchState("blocked");
            return;
          }
          if (isListening) return;
          beginSpeechRecognition();
        });
      }
      if (customerSearchClearBtn) {
        customerSearchClearBtn.addEventListener("click", function (e) {
          e.preventDefault();
          clearCustomerSearchInput();
          clearSearchResults();
          clearVoiceFailureUI();
        });
      }
      syncCustomerClearButton();
    }

    initHomeVoiceSearch();

    form.addEventListener(
      "submit",
      function (e) {
        e.preventDefault();
        e.stopPropagation();
        submitCustomerSearch();
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
      resetScrollBehaviorForQuery(customerSearchInput.value.trim());
      scheduleLatinFetch();
      syncCustomerClearButton();
    });

    input.addEventListener("keydown", function (e) {
      if (e.key !== "Enter") return;
      if (isComposingNow() || (e && e.isComposing)) {
        clearTimeout(timer);
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.dispatchEvent(
          new Event("submit", {
            bubbles: true,
            cancelable: true,
          })
        );
      }
    });

    if (mount) {
      mount.addEventListener("click", function (e) {
        var moreBtn = e.target.closest("[data-touch-search-more]");
        if (moreBtn) {
          e.preventDefault();
          runFetch(true);
          return;
        }
        var card = e.target.closest(".customer-search-result-card");
        if (!card || card.dataset.navPending === "1") return;
        var href = card.getAttribute("href");
        if (!href) return;
        e.preventDefault();
        dismissSearchKeyboard();
        card.classList.add("customer-search-result-card--pressed");
        card.dataset.navPending = "1";
        window.setTimeout(function () {
          window.location.href = href;
        }, 150);
      });
    }
  }

  document.querySelectorAll(".touch-search-form").forEach(bindForm);
  window.__touchCustomerSearchVersion = ASSET_TAG;
})();
