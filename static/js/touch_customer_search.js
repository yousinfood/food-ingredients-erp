(function () {
  "use strict";

  if (document.getElementById("customer-search-page")) {
    return;
  }

  var MIN_CHARS = 1;
  var ASSET_TAG = "20260729fix-vvh";
  var VOICE_LS_COMPLETED = "voice_permission_completed";
  var VOICE_LS_DENIED = "voice_permission_denied";
  var API_PATH = "/api/customers/search/";

  function bindForm(form) {
    if (!form || form.dataset.touchLiveSearch === "bound") return;
    form.dataset.touchLiveSearch = "bound";
    var input = form.querySelector('input[type="search"], input[type="text"][name="q"], input[name="q"]');
    if (!input) return;

    var isHomeSearch = form.dataset.touchHomeSearch === "1";
    var voicePrimaryBtn = isHomeSearch ? document.getElementById("touch-home-voice-primary") : null;

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
    var voiceStatusEl = isHomeSearch ? form.querySelector("#touch-home-voice-status") : null;
    var voiceState = "idle";
    var voiceSessionActive = false;
    var voiceGotTranscript = false;
    var voiceSuccessTimer = null;
    var userScrolledResults = false;
    var lastScrollQuery = null;
    var activeIndex = -1;
    var lastKeyboardInset = 0;

    function emptyHomePanelHtml() {
      return (
        '<div id="touch-search-results-panel" class="touch-search-results-panel touch-search-results-panel--home" data-query=""></div>'
      );
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
      if (document.activeElement === input) {
        input.blur();
      } else {
        syncKeyboardViewportAfterDismiss();
      }
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
          if (!data || !data.ok) {
            if (opts.voice && isHomeSearch) {
              setVoicePrimaryState("fail");
            }
            return;
          }
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
          if (opts.voice && isHomeSearch) {
            if (typeof data.html === "string") {
              updateResultsHtml(data.html);
            }
            if (data.redirect && data.total >= 1) {
              var cname = (data.customer_name || "").trim() || "客戶";
              setVoicePrimaryState("success", cname);
              clearVoiceSuccessTimer();
              voiceSuccessTimer = setTimeout(function () {
                window.location.href = data.redirect;
              }, 1000);
              return;
            }
            if (!data.total) {
              setVoicePrimaryState("fail");
            }
            return;
          }
          if (typeof data.html === "string") {
            updateResultsHtml(data.html);
          }
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") return;
          if (opts.voice && isHomeSearch) {
            setVoicePrimaryState("fail");
          }
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

    function voicePrimaryLines() {
      if (!voicePrimaryBtn) return { line1: null, line2: null };
      return {
        line1: voicePrimaryBtn.querySelector(".touch-home-voice-primary__line1"),
        line2: voicePrimaryBtn.querySelector(".touch-home-voice-primary__line2"),
      };
    }

    function setVoicePrimaryState(mode, detail) {
      if (!voicePrimaryBtn) return;
      voiceState = mode;
      var lines = voicePrimaryLines();
      voicePrimaryBtn.classList.remove(
        "touch-home-voice-primary--idle",
        "touch-home-voice-primary--listening",
        "touch-home-voice-primary--success",
        "touch-home-voice-primary--fail"
      );
      voicePrimaryBtn.disabled = false;
      voicePrimaryBtn.removeAttribute("aria-disabled");

      if (mode === "listening") {
        voicePrimaryBtn.classList.add("touch-home-voice-primary--listening");
        voicePrimaryBtn.setAttribute("aria-pressed", "true");
        voicePrimaryBtn.setAttribute("aria-label", "正在錄音，點擊停止");
        if (lines.line1) lines.line1.textContent = "🔴 正在聽...";
        if (lines.line2) {
          lines.line2.textContent = "請說客戶名稱";
          lines.line2.hidden = false;
        }
        setVoiceStatusMessage("");
        return;
      }
      if (mode === "success") {
        voicePrimaryBtn.classList.add("touch-home-voice-primary--success");
        voicePrimaryBtn.setAttribute("aria-pressed", "false");
        voicePrimaryBtn.setAttribute("aria-label", "語音找客戶");
        if (lines.line1) lines.line1.textContent = "🟢 已找到：";
        if (lines.line2) {
          lines.line2.textContent = detail || "客戶";
          lines.line2.hidden = false;
        }
        setVoiceStatusMessage("");
        return;
      }
      if (mode === "fail") {
        voicePrimaryBtn.classList.add("touch-home-voice-primary--fail");
        voicePrimaryBtn.setAttribute("aria-pressed", "false");
        voicePrimaryBtn.setAttribute("aria-label", "語音找客戶，點一下再試");
        if (lines.line1) lines.line1.textContent = "沒有聽清楚，";
        if (lines.line2) {
          lines.line2.textContent = "請再按一次。";
          lines.line2.hidden = false;
        }
        setVoiceStatusMessage("");
        return;
      }
      if (mode === "blocked") {
        voicePrimaryBtn.classList.add("touch-home-voice-primary--idle");
        voicePrimaryBtn.disabled = true;
        voicePrimaryBtn.setAttribute("aria-disabled", "true");
        voicePrimaryBtn.setAttribute("aria-pressed", "false");
        if (lines.line1) lines.line1.textContent = "🎤 語音找客戶";
        if (lines.line2) lines.line2.hidden = true;
        setVoiceStatusMessage("語音搜尋尚未啟用，請聯絡管理員協助設定。", "error");
        return;
      }
      voicePrimaryBtn.classList.add("touch-home-voice-primary--idle");
      voicePrimaryBtn.setAttribute("aria-pressed", "false");
      voicePrimaryBtn.setAttribute("aria-label", "語音找客戶");
      if (lines.line1) lines.line1.textContent = "🎤 語音找客戶";
      if (lines.line2) lines.line2.hidden = true;
      setVoiceStatusMessage("");
    }

    function hapticVoiceTap() {
      try {
        if (navigator.vibrate) navigator.vibrate(40);
      } catch (e) {
        /* ignore */
      }
    }

    function setVoiceStatusMessage(text, tone) {
      if (!voiceStatusEl) return;
      voiceStatusEl.textContent = text || "";
      voiceStatusEl.classList.toggle("touch-home-voice-status--error", tone === "error");
      voiceStatusEl.classList.toggle("touch-home-voice-status--success", tone === "success");
    }

    function clearVoiceSuccessTimer() {
      if (voiceSuccessTimer) {
        clearTimeout(voiceSuccessTimer);
        voiceSuccessTimer = null;
      }
    }

    function finishVoiceIdle() {
      voiceSessionActive = false;
      voiceGotTranscript = false;
      clearVoiceSuccessTimer();
      setVoicePrimaryState("idle");
    }

    function stopVoiceInput() {
      if (speechRec) {
        try {
          speechRec.stop();
        } catch (e) {
          try {
            speechRec.abort();
          } catch (e2) {
            /* ignore */
          }
        }
      }
      finishVoiceIdle();
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

    function isVoicePermissionCompleted() {
      return readVoiceFlag(VOICE_LS_COMPLETED);
    }

    function isVoicePermissionDenied() {
      return readVoiceFlag(VOICE_LS_DENIED);
    }

    function markVoicePermissionCompleted() {
      writeVoiceFlag(VOICE_LS_COMPLETED, true);
      writeVoiceFlag(VOICE_LS_DENIED, false);
    }

    function markVoicePermissionDenied() {
      writeVoiceFlag(VOICE_LS_DENIED, true);
    }

    function showVoiceBlockedMessage() {
      setVoicePrimaryState("blocked");
    }

    function showVoicePermissionIntro(onConfirm) {
      var overlay = document.getElementById("touch-voice-permission-intro");
      var okBtn = document.getElementById("touch-voice-permission-intro-ok");
      if (!overlay || !okBtn) {
        onConfirm();
        return;
      }
      overlay.hidden = false;
      document.body.classList.add("touch-voice-intro-open");
      function cleanup() {
        overlay.hidden = true;
        document.body.classList.remove("touch-voice-intro-open");
        okBtn.removeEventListener("click", onOk);
      }
      function onOk(e) {
        e.preventDefault();
        cleanup();
        onConfirm();
      }
      okBtn.addEventListener("click", onOk);
    }

    function requestMicrophoneAccess(thenStart) {
      if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function") {
        navigator.mediaDevices
          .getUserMedia({ audio: true })
          .then(function (stream) {
            if (stream && stream.getTracks) {
              stream.getTracks().forEach(function (track) {
                track.stop();
              });
            }
            markVoicePermissionCompleted();
            thenStart();
          })
          .catch(function () {
            markVoicePermissionDenied();
            showVoiceBlockedMessage();
          });
        return;
      }
      thenStart();
    }

    function beginSpeechRecognition() {
      if (!voicePrimaryBtn || voiceSessionActive) return;

      var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        voicePrimaryBtn.hidden = true;
        setVoiceStatusMessage("此裝置暫不支援語音搜尋，請使用文字搜尋", "error");
        return;
      }

      hapticVoiceTap();
      voiceSessionActive = true;
      voiceGotTranscript = false;
      clearVoiceSuccessTimer();
      setVoicePrimaryState("listening");

      if (speechRec) {
        try {
          speechRec.abort();
        } catch (e) {
          /* ignore */
        }
      }

      speechRec = new SpeechRecognition();
      speechRec.lang = "zh-TW";
      speechRec.continuous = false;
      speechRec.interimResults = false;
      speechRec.maxAlternatives = 1;

      speechRec.onresult = function (ev) {
        var text = "";
        if (ev.results && ev.results.length) {
          text = (ev.results[0][0] && ev.results[0][0].transcript) || "";
        }
        text = text.trim();
        voiceGotTranscript = true;
        if (!isVoicePermissionCompleted()) {
          markVoicePermissionCompleted();
        }
        if (text) {
          input.value = text;
          resetScrollBehaviorForQuery(text);
          runFetch(false, { voice: true });
        } else {
          voiceSessionActive = false;
          setVoicePrimaryState("fail");
        }
      };

      speechRec.onerror = function (ev) {
        var code = ev && ev.error ? ev.error : "";
        voiceSessionActive = false;
        voiceGotTranscript = false;
        clearVoiceSuccessTimer();
        if (code === "not-allowed" || code === "service-not-allowed") {
          markVoicePermissionDenied();
          showVoiceBlockedMessage();
          return;
        }
        if (code === "aborted") {
          finishVoiceIdle();
          return;
        }
        setVoicePrimaryState("fail");
      };

      speechRec.onend = function () {
        if (voiceGotTranscript) {
          voiceSessionActive = false;
          return;
        }
        if (voiceState === "listening") {
          voiceSessionActive = false;
          setVoicePrimaryState("fail");
        }
      };

      try {
        speechRec.start();
      } catch (e) {
        voiceSessionActive = false;
        setVoicePrimaryState("fail");
      }
    }

    function onVoicePrimaryClick(e) {
      e.preventDefault();
      if (isVoicePermissionDenied()) {
        showVoiceBlockedMessage();
        return;
      }
      if (voiceState === "success") return;
      if (voiceSessionActive && voiceState === "listening") {
        stopVoiceInput();
        return;
      }
      if (voiceSessionActive) return;

      if (!isVoicePermissionCompleted()) {
        showVoicePermissionIntro(startVoiceInputAfterConsent);
        return;
      }
      beginSpeechRecognition();
    }

    function startVoiceInputAfterConsent() {
      if (isVoicePermissionDenied()) {
        showVoiceBlockedMessage();
        return;
      }
      if (isVoicePermissionCompleted()) {
        beginSpeechRecognition();
        return;
      }
      requestMicrophoneAccess(beginSpeechRecognition);
    }

    function initHomeVoiceSearch() {
      if (!isHomeSearch || !voicePrimaryBtn) return;
      var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        voicePrimaryBtn.hidden = true;
        setVoiceStatusMessage("此裝置暫不支援語音搜尋，請使用文字搜尋", "error");
        return;
      }
      if (isVoicePermissionDenied()) {
        showVoiceBlockedMessage();
        return;
      }
      setVoicePrimaryState("idle");
      voicePrimaryBtn.addEventListener("click", onVoicePrimaryClick);
    }

    initHomeVoiceSearch();

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
