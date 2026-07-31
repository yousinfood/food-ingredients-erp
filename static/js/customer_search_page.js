(function () {
  "use strict";

  var page = document.getElementById("customer-search-page");
  if (!page) return;

  var API_PATH = "/api/customers/search/";
  var TRANSCRIBE_PATH = "/api/voice/transcribe/";
  var LS_INTRO = "voice_intro_seen";
  var LS_DENIED = "voice_permission_denied";
  var MIN_CHARS = 1;
  var VOICE_RECORD_MS = 8000;
  var VOICE_RECORD_MS_IOS = 5000;

  var form = document.getElementById("customer-search-form");
  var input = document.getElementById("customer-search-input");
  var resultsMount = document.getElementById("customer-search-results");
  var voiceBtn = document.getElementById("voice-search-button");
  var voiceIcon = document.getElementById("voice-search-icon");
  var voiceTitle = document.getElementById("voice-search-title");
  var voiceSubtitle = document.getElementById("voice-search-subtitle");
  var voiceStatus = document.getElementById("voice-search-status");
  var introEl = document.getElementById("voice-search-intro");
  var introOk = document.getElementById("voice-search-intro-ok");

  if (!form || !input || !resultsMount || !voiceBtn) return;

  function isIOSDevice() {
    var ua = navigator.userAgent || "";
    return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  function isIPhoneSafari() {
    if (!isIOSDevice()) return false;
    var ua = navigator.userAgent || "";
    return /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
  }

  function getSpeechRecognitionCtor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function hasSpeechRecognition() {
    return !!getSpeechRecognitionCtor();
  }

  function hasMediaRecorderVoice() {
    return !!(
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === "function" &&
      typeof MediaRecorder !== "undefined"
    );
  }

  function prefersMediaRecorderVoice() {
    if (!hasSpeechRecognition() && hasMediaRecorderVoice()) return true;
    return false;
  }

  function speechRecognitionConfig() {
    if (isIOSDevice()) {
      return { lang: "zh-TW", continuous: true, interimResults: true, maxAlternatives: 1 };
    }
    return { lang: "zh-TW", continuous: false, interimResults: false, maxAlternatives: 3 };
  }

  function voiceLog(eventName, payload) {
    if (typeof console === "undefined" || !console.log) return;
    console.log("[voice-search][" + eventName + "]", payload !== undefined ? payload : "");
  }

  function serializeSpeechResults(results) {
    if (!results || !results.length) return [];
    var out = [];
    for (var i = 0; i < results.length; i++) {
      var item = results[i];
      var alts = [];
      for (var j = 0; j < item.length; j++) {
        alts.push({
          transcript: item[j].transcript || "",
          confidence: typeof item[j].confidence === "number" ? item[j].confidence : null,
        });
      }
      out.push({ index: i, isFinal: !!item.isFinal, alternatives: alts });
    }
    return out;
  }

  function voiceRecordMs() {
    return isIOSDevice() ? VOICE_RECORD_MS_IOS : VOICE_RECORD_MS;
  }

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var recognition = null;
  var mediaRecorder = null;
  var mediaStream = null;
  var audioChunks = [];
  var recordStopTimer = null;
  var voiceActiveEngine = null;
  var isListening = false;
  var voicePhase = "idle";
  var gotTranscript = false;
  var heardSuccess = false;
  var resetTimer = null;
  var fetchAbort = null;
  var fetchSeq = 0;
  var composeTimer = null;
  var composing = false;

  function emptyResultsHtml() {
    return '<div id="touch-search-results-panel" class="customer-search-results-panel" data-query=""></div>';
  }

  function readFlag(key) {
    try {
      return localStorage.getItem(key) === "true";
    } catch (e) {
      return false;
    }
  }

  function writeFlag(key, val) {
    try {
      localStorage.setItem(key, val ? "true" : "false");
    } catch (e) {
      /* ignore */
    }
  }

  function clearResetTimer() {
    if (resetTimer) {
      clearTimeout(resetTimer);
      resetTimer = null;
    }
  }

  function setStatus(text, tone) {
    if (!voiceStatus) return;
    voiceStatus.textContent = text || "";
    voiceStatus.classList.toggle("customer-search-page__status--blocked", tone === "blocked");
  }

  function setVoiceUi(phase, opts) {
    opts = opts || {};
    voicePhase = phase;
    voiceBtn.classList.remove(
      "voice-search-button--idle",
      "voice-search-button--starting",
      "voice-search-button--listening",
      "voice-search-button--success",
      "voice-search-button--blocked"
    );
    voiceBtn.disabled = false;
    voiceBtn.removeAttribute("aria-disabled");

    if (phase === "starting") {
      voiceBtn.classList.add("voice-search-button--starting");
      voiceBtn.disabled = true;
      voiceBtn.setAttribute("aria-pressed", "false");
      if (voiceTitle) voiceTitle.textContent = "🎤 準備中…";
      if (voiceSubtitle) voiceSubtitle.textContent = "請用國語說客戶名稱";
      if (voiceIcon) voiceIcon.hidden = true;
      return;
    }

    if (phase === "listening") {
      voiceBtn.classList.add("voice-search-button--listening");
      voiceBtn.setAttribute("aria-pressed", "true");
      if (voiceTitle) voiceTitle.textContent = "🎤 正在聽…";
      if (voiceSubtitle) {
        voiceSubtitle.textContent =
          voiceActiveEngine === "media" ? "說完會自動搜尋" : "請用國語說客戶名稱";
      }
      if (voiceIcon) voiceIcon.hidden = true;
      return;
    }

    if (phase === "processing") {
      voiceBtn.classList.add("voice-search-button--starting");
      voiceBtn.disabled = true;
      voiceBtn.setAttribute("aria-pressed", "false");
      if (voiceTitle) voiceTitle.textContent = "🎤 正在辨識…";
      if (voiceSubtitle) voiceSubtitle.textContent = "";
      if (voiceIcon) voiceIcon.hidden = true;
      return;
    }

    if (phase === "success") {
      voiceBtn.classList.add("voice-search-button--success");
      voiceBtn.setAttribute("aria-pressed", "false");
      var heard = opts.heard || "";
      if (voiceTitle) voiceTitle.textContent = "✓ 已聽到：" + heard;
      if (voiceSubtitle) voiceSubtitle.textContent = "";
      if (voiceIcon) voiceIcon.hidden = true;
      return;
    }

    if (phase === "blocked") {
      voiceBtn.classList.add("voice-search-button--idle", "voice-search-button--blocked");
      voiceBtn.disabled = true;
      voiceBtn.setAttribute("aria-disabled", "true");
      voiceBtn.setAttribute("aria-pressed", "false");
      if (voiceTitle) voiceTitle.textContent = "🎤 語音找客戶";
      if (voiceSubtitle) voiceSubtitle.textContent = "點一下開始說話";
      if (voiceIcon) voiceIcon.hidden = true;
      setStatus("語音搜尋尚未開啟，請請家人協助設定", "blocked");
      return;
    }

    voiceBtn.classList.add("voice-search-button--idle");
    voiceBtn.setAttribute("aria-pressed", "false");
    if (voiceTitle) voiceTitle.textContent = "🎤 語音找客戶";
    if (voiceSubtitle) voiceSubtitle.textContent = "點一下開始說話";
    if (voiceIcon) voiceIcon.hidden = true;
    if (!opts.keepStatus) setStatus("");
  }

  function scheduleIdleReset(ms) {
    clearResetTimer();
    resetTimer = setTimeout(function () {
      heardSuccess = false;
      setVoiceUi("idle");
    }, ms || 1000);
  }

  function applyResultsHtml(html) {
    if (typeof html !== "string") return;
    var panel = resultsMount.querySelector("#touch-search-results-panel");
    if (panel) {
      var wrap = document.createElement("div");
      wrap.innerHTML = html.trim();
      var next = wrap.firstElementChild;
      if (next) panel.replaceWith(next);
      else panel.outerHTML = html;
    } else {
      resultsMount.innerHTML = html;
    }
    bindResultsActions();
  }

  function runSearch(opts) {
    opts = opts || {};
    var q = input.value.trim();
    if (q.length < MIN_CHARS) {
      if (!q.length) applyResultsHtml(emptyResultsHtml());
      return;
    }

    var url =
      API_PATH +
      "?q=" +
      encodeURIComponent(q) +
      "&home=1" +
      (opts.voice ? "&voice=1" : "") +
      (opts.more ? "&more=1" : "");

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
        if (!data || !data.ok) return;

        if (opts.voice && data.normalized_q && typeof data.normalized_q === "string") {
          var norm = data.normalized_q.trim();
          if (norm && norm !== input.value.trim()) input.value = norm;
        }

        if (typeof data.html === "string") applyResultsHtml(data.html);

        if (opts.voice && data.redirect && data.total === 1) {
          clearResetTimer();
          resetTimer = setTimeout(function () {
            window.location.href = data.redirect;
          }, 1000);
          return;
        }

        if (opts.voice && heardSuccess) scheduleIdleReset(1000);
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") return;
        if (opts.voice && heardSuccess) scheduleIdleReset(1000);
      });
  }

  function bindResultsActions() {
    if (!resultsMount) return;
    resultsMount.querySelectorAll("[data-empty-voice]").forEach(function (btn) {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", function () {
        onVoiceButtonClick();
      });
    });
    resultsMount.querySelectorAll("[data-empty-type]").forEach(function (btn) {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", function () {
        input.focus();
      });
    });
    resultsMount.querySelectorAll("[data-touch-search-more]").forEach(function (btn) {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", function () {
        runSearch({ more: true });
      });
    });
  }

  function destroyRecognition() {
    if (!recognition) return;
    recognition.onstart = null;
    recognition.onresult = null;
    recognition.onerror = null;
    recognition.onend = null;
    try {
      recognition.abort();
    } catch (e) {
      try {
        recognition.stop();
      } catch (err) {
        /* ignore */
      }
    }
    recognition = null;
  }

  function stopMediaStream() {
    if (!mediaStream) return;
    mediaStream.getTracks().forEach(function (track) {
      track.stop();
    });
    mediaStream = null;
  }

  function destroyVoiceRecording() {
    if (recordStopTimer) {
      clearTimeout(recordStopTimer);
      recordStopTimer = null;
    }
    if (mediaRecorder) {
      mediaRecorder.ondataavailable = null;
      mediaRecorder.onstop = null;
      mediaRecorder.onerror = null;
      if (mediaRecorder.state !== "inactive") {
        try {
          mediaRecorder.stop();
        } catch (e) {
          /* ignore */
        }
      }
      mediaRecorder = null;
    }
    stopMediaStream();
  }

  function stopAllVoiceCapture() {
    destroyRecognition();
    destroyVoiceRecording();
    voiceActiveEngine = null;
    isListening = false;
  }

  function pickAudioMimeType() {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
    var types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/aac"];
    for (var i = 0; i < types.length; i++) {
      if (MediaRecorder.isTypeSupported(types[i])) return types[i];
    }
    return "";
  }

  function bestTranscript(ev) {
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

  function applyVoiceTranscript(text) {
    gotTranscript = true;
    heardSuccess = true;
    input.value = text;
    setVoiceUi("success", { heard: text });
    runSearch({ voice: true });
  }

  function handleRecognitionError(code) {
    stopAllVoiceCapture();
    gotTranscript = false;
    heardSuccess = false;
    if (code === "not-allowed" || code === "service-not-allowed") {
      writeFlag(LS_DENIED, true);
      setVoiceUi("blocked");
      return;
    }
    setVoiceUi("idle", { keepStatus: true });
    if (code === "no-speech") setStatus("沒有聽到聲音，請再按一次");
    else if (code === "audio-capture") setStatus("目前無法使用麥克風，請改用文字搜尋");
    else if (code === "network") setStatus("沒有網路，請改用文字搜尋");
    else setStatus("沒有聽清楚，請再按一次");
  }

  function uploadVoiceRecording(mimeType) {
    isListening = false;
    voiceActiveEngine = null;
    voiceBtn.disabled = false;
    if (!audioChunks.length) {
      handleRecognitionError("no-speech");
      return;
    }
    var blob = new Blob(audioChunks, { type: mimeType || "audio/webm" });
    audioChunks = [];
    var ext = mimeType && mimeType.indexOf("mp4") >= 0 ? "mp4" : "webm";
    var formData = new FormData();
    formData.append("audio", blob, "voice." + ext);

    setVoiceUi("processing");

    fetch(TRANSCRIBE_PATH, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": getCsrfToken(),
      },
    })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (!data || !data.ok || !data.text) {
          handleRecognitionError("no-speech");
          return;
        }
        var text = String(data.text).trim();
        if (!text) {
          handleRecognitionError("no-speech");
          return;
        }
        applyVoiceTranscript(text);
      })
      .catch(function () {
        handleRecognitionError("network");
      });
  }

  function beginMediaRecorderVoice() {
    if (!hasMediaRecorderVoice() || isListening) return;

    try {
      if (navigator.vibrate) navigator.vibrate(40);
    } catch (e) {
      /* ignore */
    }

    setVoiceUi("starting");
    isListening = true;
    voiceActiveEngine = "media";
    gotTranscript = false;
    heardSuccess = false;
    clearResetTimer();
    audioChunks = [];
    destroyVoiceRecording();
    destroyRecognition();

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then(function (stream) {
        if (!isListening || voiceActiveEngine !== "media") {
          stream.getTracks().forEach(function (track) {
            track.stop();
          });
          return;
        }
        mediaStream = stream;
        var mimeType = pickAudioMimeType();
        try {
          mediaRecorder = mimeType
            ? new MediaRecorder(stream, { mimeType: mimeType })
            : new MediaRecorder(stream);
        } catch (e) {
          stopMediaStream();
          handleRecognitionError("audio-capture");
          return;
        }

        mediaRecorder.ondataavailable = function (ev) {
          if (ev.data && ev.data.size > 0) audioChunks.push(ev.data);
        };
        mediaRecorder.onstop = function () {
          stopMediaStream();
          uploadVoiceRecording(mimeType);
        };
        mediaRecorder.onerror = function () {
          stopAllVoiceCapture();
          handleRecognitionError("audio-capture");
        };

        setVoiceUi("listening");
        mediaRecorder.start();
        recordStopTimer = setTimeout(function () {
          if (mediaRecorder && mediaRecorder.state === "recording") {
            try {
              mediaRecorder.stop();
            } catch (e) {
              /* ignore */
            }
          }
        }, voiceRecordMs());
      })
      .catch(function (err) {
        if (err && err.name === "NotAllowedError") {
          writeFlag(LS_DENIED, true);
          handleRecognitionError("not-allowed");
          return;
        }
        handleRecognitionError("audio-capture");
      });
  }

  function startSpeechRecognition() {
    var SpeechRecognitionCtor = getSpeechRecognitionCtor();
    if (!SpeechRecognitionCtor || isListening) return;
    if (readFlag(LS_DENIED)) {
      setVoiceUi("blocked");
      return;
    }

    try {
      if (navigator.vibrate) navigator.vibrate(40);
    } catch (e) {
      /* ignore */
    }

    setVoiceUi("starting");
    isListening = true;
    voiceActiveEngine = "speech";
    gotTranscript = false;
    heardSuccess = false;
    clearResetTimer();

    destroyRecognition();
    destroyVoiceRecording();
    recognition = new SpeechRecognitionCtor();
    recognition.lang = "zh-TW";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 3;

    recognition.onstart = function () {
      if (voiceActiveEngine !== "speech") return;
      setVoiceUi("listening");
    };

    recognition.onresult = function (ev) {
      if (voiceActiveEngine !== "speech") return;
      var text = bestTranscript(ev);
      gotTranscript = true;
      destroyRecognition();
      voiceActiveEngine = null;
      isListening = false;
      voiceBtn.disabled = false;
      if (!text) {
        handleRecognitionError("no-speech");
        return;
      }
      applyVoiceTranscript(text);
    };

    recognition.onerror = function (ev) {
      if (voiceActiveEngine !== "speech") return;
      var code = ev && ev.error ? ev.error : "";
      if (code === "aborted") return;
      handleRecognitionError(code);
    };

    recognition.onend = function () {
      if (gotTranscript) return;
      if (voiceActiveEngine !== "speech") return;
      handleRecognitionError("no-speech");
    };

    try {
      recognition.start();
    } catch (e) {
      destroyRecognition();
      voiceActiveEngine = null;
      isListening = false;
      if (hasMediaRecorderVoice()) {
        beginMediaRecorderVoice();
        return;
      }
      setVoiceUi("idle", { keepStatus: true });
      setStatus("沒有聽清楚，請再按一次");
    }
  }

  function beginVoiceSession() {
    if (isListening) return;
    if (readFlag(LS_DENIED)) {
      setVoiceUi("blocked");
      return;
    }
    if (prefersMediaRecorderVoice()) {
      if (hasMediaRecorderVoice()) {
        beginMediaRecorderVoice();
        return;
      }
      if (hasSpeechRecognition()) {
        startSpeechRecognition();
        return;
      }
      voiceBtn.hidden = true;
      setStatus("此裝置不支援語音，請改用文字搜尋");
      return;
    }
    if (hasSpeechRecognition()) {
      startSpeechRecognition();
      return;
    }
    if (hasMediaRecorderVoice()) {
      beginMediaRecorderVoice();
      return;
    }
    voiceBtn.hidden = true;
    setStatus("此裝置不支援語音，請改用文字搜尋");
  }

  function showIntroThenStart() {
    if (!introEl || !introOk) {
      writeFlag(LS_INTRO, true);
      beginVoiceSession();
      return;
    }
    introEl.hidden = false;
    document.body.classList.add("voice-search-intro-open");
    function closeIntro() {
      introEl.hidden = true;
      document.body.classList.remove("voice-search-intro-open");
      introOk.removeEventListener("click", onOk);
      writeFlag(LS_INTRO, true);
      beginVoiceSession();
    }
    function onOk(e) {
      e.preventDefault();
      closeIntro();
    }
    introOk.addEventListener("click", onOk);
  }

  function onVoiceButtonClick() {
    if (isListening) return;
    if (!hasSpeechRecognition() && !hasMediaRecorderVoice()) {
      voiceBtn.hidden = true;
      setStatus("此裝置不支援語音，請改用文字搜尋");
      return;
    }
    if (readFlag(LS_DENIED)) {
      setVoiceUi("blocked");
      return;
    }
    if (!readFlag(LS_INTRO)) {
      showIntroThenStart();
      return;
    }
    beginVoiceSession();
  }

  function scheduleTypeSearch() {
    clearTimeout(composeTimer);
    composeTimer = setTimeout(function () {
      runSearch({});
    }, 280);
  }

  voiceBtn.addEventListener("click", function (e) {
    e.preventDefault();
    onVoiceButtonClick();
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearTimeout(composeTimer);
    runSearch({});
  });

  input.addEventListener("compositionstart", function () {
    composing = true;
    clearTimeout(composeTimer);
    if (fetchAbort) fetchAbort.abort();
  });

  input.addEventListener("compositionend", function () {
    composing = false;
    scheduleTypeSearch();
  });

  input.addEventListener("input", function (e) {
    if (composing || (e && e.isComposing)) return;
    scheduleTypeSearch();
  });

  function syncViewport() {
    var vv = window.visualViewport;
    if (!vv) return;
    var inset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
    document.documentElement.style.setProperty("--customer-search-kb-pad", inset + "px");
    document.documentElement.style.setProperty("--customer-search-vvh", Math.round(vv.height) + "px");
  }

  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", syncViewport);
  }
  syncViewport();

  bindResultsActions();

  if (!hasSpeechRecognition() && !hasMediaRecorderVoice()) {
    voiceBtn.hidden = true;
    setStatus("此裝置不支援語音，請改用文字搜尋");
  } else if (readFlag(LS_DENIED)) {
    setVoiceUi("blocked");
  } else {
    setVoiceUi("idle");
  }

  window.__customerSearchPageVersion = "voice-search-safari-028";
})();
