(function () {
  "use strict";

  var MAX_RECORD_MS = 3000;
  var SILENCE_STOP_MS = 700;
  var SILENCE_THRESHOLD = 0.018;
  var STOP_FLUSH_MS = 120;
  var MIN_BLOB_BYTES = 100;
  var MIC_START_FAIL_MSG = "麥克風無法啟動，請重新按一次";
  var TRANSCRIBE_URL = "/api/voice/transcribe/";
  var DEBUG_TAG = "[ys-debug-voice-ios]";
  var PERF_TAG = "[ys-voice-perf]";
  var TS_TAG = "[ys-voice-ts]";
  var perfT0 = 0;
  var perfPrev = 0;
  var perfSearchActive = false;
  var tsMicPress = 0;
  var tsSpeechStartLogged = false;
  var tsSilenceLogged = false;

  function tsMirrorToServer(label, sinceMic, detail) {
    try {
      var xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/voice/ts-log/", true);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.setRequestHeader("Accept", "application/json");
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
      xhr.send(
        JSON.stringify({
          label: label,
          since_mic_ms: sinceMic,
          detail: detail !== undefined ? detail : null,
        })
      );
    } catch (e) {
      /* ignore */
    }
  }

  function tsMark(label, detail) {
    try {
      var now = performance.now();
      if (!tsMicPress) tsMicPress = now;
      var sinceMic = Math.round(now - tsMicPress);
      if (detail !== undefined) console.log(TS_TAG, label, "since_mic_ms=" + sinceMic, detail);
      else console.log(TS_TAG, label, "since_mic_ms=" + sinceMic);
      tsMirrorToServer(label, sinceMic, detail);
    } catch (e) {
      /* ignore */
    }
  }

  function tsReset() {
    tsMicPress = performance.now();
    tsSpeechStartLogged = false;
    tsSilenceLogged = false;
    tsMark("按下麥克風");
  }

  function perfMark(step, label, detail) {
    try {
      var now = Date.now();
      if (!perfT0) perfT0 = now;
      var totalMs = now - perfT0;
      var stepMs = perfPrev ? now - perfPrev : 0;
      perfPrev = now;
      if (detail !== undefined) console.log(PERF_TAG, "step=" + step, label, "total_ms=" + totalMs, "step_ms=" + stepMs, detail);
      else console.log(PERF_TAG, "step=" + step, label, "total_ms=" + totalMs, "step_ms=" + stepMs);
    } catch (e) {
      /* ignore */
    }
  }

  function perfReset() {
    perfT0 = Date.now();
    perfPrev = perfT0;
    perfSearchActive = false;
  }

  function watchSearchResultsDisplay() {
    var mount = document.getElementById("touch-search-results-mount");
    if (!mount) {
      perfMark(12, "顯示搜尋結果", { note: "missing mount" });
      return;
    }
    var observer = new MutationObserver(function () {
      var panel = mount.querySelector("#touch-search-results-panel");
      if (!panel || panel.classList.contains("customer-search-results-panel--loading")) return;
      perfMark(12, "顯示搜尋結果");
      observer.disconnect();
    });
    observer.observe(mount, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
  }

  function debugLog(label, data) {
    try {
      if (data !== undefined) console.log(DEBUG_TAG, label, data);
      else console.log(DEBUG_TAG, label);
    } catch (e) {
      /* ignore */
    }
  }

  function debugSessionStorageAll() {
    var out = {};
    try {
      for (var i = 0; i < sessionStorage.length; i++) {
        var key = sessionStorage.key(i);
        out[key] = sessionStorage.getItem(key);
      }
      if (!sessionStorage.length) out._empty = true;
    } catch (e) {
      out._readError = String(e);
    }
    return out;
  }

  function debugLogPermissions() {
    if (!navigator.permissions || typeof navigator.permissions.query !== "function") {
      debugLog("navigator.permissions", { supported: false });
      return;
    }
    navigator.permissions
      .query({ name: "microphone" })
      .then(function (perm) {
        debugLog("navigator.permissions.query(microphone)", { supported: true, state: perm.state });
      })
      .catch(function (err) {
        debugLog("navigator.permissions.query(microphone)", {
          supported: true,
          error: err && err.name,
          message: err && err.message,
        });
      });
  }

  function isIOS() {
    var ua = navigator.userAgent || "";
    return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function pickMimeType() {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
    var types = ["audio/mp4", "audio/aac", "audio/webm;codecs=opus", "audio/webm"];
    for (var i = 0; i < types.length; i++) {
      if (MediaRecorder.isTypeSupported(types[i])) return types[i];
    }
    return "";
  }

  function filenameForMime(mime) {
    if (!mime || mime.indexOf("webm") >= 0) return "voice.webm";
    if (mime.indexOf("aac") >= 0 || mime.indexOf("m4a") >= 0) return "voice.m4a";
    return "voice.m4a";
  }

  function init() {
    debugLog("init enter", {
      readyState: document.readyState,
      userAgent: navigator.userAgent,
      isIOS: isIOS(),
      sessionStorage: debugSessionStorageAll(),
      hasMediaDevices: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
      hasMediaRecorder: typeof MediaRecorder !== "undefined",
      location: { origin: location.origin, href: location.href, protocol: location.protocol },
      userActivation: navigator.userActivation
        ? {
            isActive: navigator.userActivation.isActive,
            hasBeenActive: navigator.userActivation.hasBeenActive,
          }
        : null,
    });
    debugLogPermissions();

    if (!isIOS()) {
      debugLog("init exit", "not iOS");
      return;
    }

    var btn = document.getElementById("voice-search-button");
    var retry = document.getElementById("voice-search-retry");
    if (!btn) {
      debugLog("init exit", "missing #voice-search-button");
      return;
    }

    var hooks = window.__yousinTouchVoice;
    if (!hooks) {
      console.error("[voice-ios] missing window.__yousinTouchVoice");
      debugLog("init exit", "missing window.__yousinTouchVoice");
      return;
    }

    var origApplyTranscript = hooks.applyTranscript;
    var origFetch = window.fetch;
    hooks.applyTranscript = function (text) {
      perfMark(8, "開始搜尋客戶", { text: text });
      perfSearchActive = true;
      watchSearchResultsDisplay();
      return origApplyTranscript(text);
    };
    window.fetch = function (input, init) {
      var url = typeof input === "string" ? input : input && input.url ? input.url : "";
      var promise = origFetch.apply(this, arguments);
      if (perfSearchActive && url.indexOf("/api/customers/search/") >= 0 && url.indexOf("voice=1") >= 0) {
        var searchFetchStart = Date.now();
        return promise.then(function (res) {
          perfMark(11, "前端收到結果", {
            status: res.status,
            fetch_ms: Date.now() - searchFetchStart,
          });
          perfSearchActive = false;
          return res;
        });
      }
      return promise;
    };

    var recorder = null;
    var stream = null;
    var chunks = [];
    var mimeType = "";
    var recordStartedAt = 0;
    var maxStopTimer = null;
    var silenceCheckTimer = null;
    var silenceStartedAt = 0;
    var hasHeardSpeech = false;
    var audioCtx = null;
    var isRecording = false;
    var busy = false;

    function clearTimers() {
      if (maxStopTimer) {
        clearTimeout(maxStopTimer);
        maxStopTimer = null;
      }
      if (silenceCheckTimer) {
        clearInterval(silenceCheckTimer);
        silenceCheckTimer = null;
      }
      silenceStartedAt = 0;
      hasHeardSpeech = false;
    }

    function stopSilenceMonitor() {
      clearTimers();
      if (audioCtx) {
        try {
          audioCtx.close();
        } catch (e) {
          /* ignore */
        }
        audioCtx = null;
      }
    }

    function setRecordingUI() {
      hooks.setState("listening");
      var line1 = btn.querySelector(".voice-search-button__line1");
      var line2 = btn.querySelector(".voice-search-button__line2");
      if (line1) line1.textContent = "🔴 請說客戶名稱";
      if (line2) line2.textContent = "";
    }

    function startSilenceMonitor(mediaStream) {
      try {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        var source = audioCtx.createMediaStreamSource(mediaStream);
        var analyser = audioCtx.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser);
        var data = new Uint8Array(analyser.fftSize);
        silenceCheckTimer = setInterval(function () {
          if (!isRecording) return;
          analyser.getByteTimeDomainData(data);
          var sum = 0;
          for (var i = 0; i < data.length; i++) {
            var sample = (data[i] - 128) / 128;
            sum += sample * sample;
          }
          if (Math.sqrt(sum / data.length) > SILENCE_THRESHOLD) {
            if (!hasHeardSpeech && !tsSpeechStartLogged) {
              tsSpeechStartLogged = true;
              tsMark("偵測到開始說話", { rms: Math.sqrt(sum / data.length) });
            }
            hasHeardSpeech = true;
            silenceStartedAt = 0;
            return;
          }
          if (!hasHeardSpeech) return;
          if (!silenceStartedAt) {
            silenceStartedAt = Date.now();
            if (!tsSilenceLogged) {
              tsSilenceLogged = true;
              tsMark("偵測到靜音");
            }
            return;
          }
          if (Date.now() - silenceStartedAt >= SILENCE_STOP_MS) {
            tsMark("靜音達標，觸發 stopRecording", { silence_stop_ms: SILENCE_STOP_MS });
            stopRecording();
          }
        }, 50);
      } catch (e) {
        debugLog("silence monitor failed", e);
      }
    }

    function releaseStream() {
      stopSilenceMonitor();
      if (recorder) {
        recorder.ondataavailable = null;
        recorder.onstop = null;
        recorder.onerror = null;
        recorder = null;
      }
      if (stream) {
        stream.getTracks().forEach(function (track) {
          track.stop();
        });
        stream = null;
      }
    }

    function resetBusy() {
      busy = false;
      isRecording = false;
      clearTimers();
    }

    function mapApiError(message, httpStatus) {
      var msg = (message || "").trim();
      if (msg === "語音服務尚未設定") return "語音服務尚未設定，請聯絡管理員";
      if (msg.indexOf("格式") >= 0) return msg;
      if (msg.indexOf("聽不清楚") >= 0) return msg;
      if (msg.indexOf("AI 額度不足") >= 0) return msg;
      if (msg.indexOf("設定錯誤") >= 0) return msg;
      if (msg.indexOf("暫時無法") >= 0 || httpStatus >= 500) {
        return msg || "語音辨識暫時無法使用，請改用文字搜尋";
      }
      if (msg.indexOf("沒有收到") >= 0) return "沒有聽到聲音，請再按一次";
      return msg || "語音辨識暫時無法使用，請改用文字搜尋";
    }

    function uploadBlob(blob) {
      tsMark("開始 upload /api/voice/transcribe/", { bytes: blob.size });
      perfMark(4, "開始上傳", { bytes: blob.size });
      hooks.setState("processing");
      var line1 = btn.querySelector(".voice-search-button__line1");
      if (line1) line1.textContent = "🎤 正在辨識，請稍候";
      var formData = new FormData();
      formData.append("audio", blob, filenameForMime(blob.type || mimeType));

      fetch(TRANSCRIBE_URL, {
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
          return res.text().then(function (text) {
            var data = null;
            try {
              data = text ? JSON.parse(text) : null;
            } catch (e) {
              data = null;
            }
            return { status: res.status, ok: res.ok, data: data || {} };
          });
        })
        .then(function (result) {
          tsMark("upload 完成", { status: result.status, ok: result.ok });
          resetBusy();
          var transcript = ((result.data && result.data.text) || "").trim();
          if (result.ok && result.data.ok && transcript) {
            hooks.applyTranscript(transcript);
            return;
          }
          var errMsg = mapApiError(result.data.error || "", result.status);
          if (errMsg.indexOf("聽不清楚") >= 0) {
            hooks.showUnclear();
            hooks.showRetry();
            return;
          }
          hooks.showServiceError(errMsg);
          hooks.showRetry();
        })
        .catch(function () {
          resetBusy();
          hooks.showServiceError("語音辨識暫時無法使用，請改用文字搜尋");
          hooks.showRetry();
        });
    }

    function finishRecording() {
      perfMark(3, "停止錄音");
      clearTimers();
      isRecording = false;
      releaseStream();

      var blob = new Blob(chunks, { type: mimeType || "audio/mp4" });
      chunks = [];

      if (!blob.size || blob.size < MIN_BLOB_BYTES) {
        busy = false;
        hooks.showUnclear();
        hooks.showRetry();
        return;
      }

      uploadBlob(blob);
    }

    function stopRecording() {
      if (!recorder || recorder.state !== "recording") {
        finishRecording();
        return;
      }

      isRecording = false;
      if (typeof recorder.requestData === "function") {
        try {
          recorder.requestData();
        } catch (e) {
          /* ignore */
        }
      }

      setTimeout(function () {
        if (!recorder || recorder.state !== "recording") {
          finishRecording();
          return;
        }
        try {
          tsMark("呼叫 MediaRecorder.stop()");
          recorder.stop();
        } catch (e) {
          finishRecording();
        }
      }, STOP_FLUSH_MS);
    }

    function startRecording() {
      if (busy) {
        debugLog("startRecording skip", "busy");
        return;
      }
      busy = true;
      chunks = [];

      if (retry) retry.hidden = true;
      hooks.prepareSession();
      hooks.haptic();
      hooks.setState("starting");

      if (typeof navigator.mediaDevices === "undefined" || !navigator.mediaDevices.getUserMedia) {
        resetBusy();
        hooks.showServiceError(MIC_START_FAIL_MSG);
        debugLog("startRecording exit", "no mediaDevices.getUserMedia");
        return;
      }
      if (typeof MediaRecorder === "undefined") {
        resetBusy();
        hooks.showServiceError(MIC_START_FAIL_MSG);
        debugLog("startRecording exit", "no MediaRecorder");
        return;
      }

      debugLog("getUserMedia before", {
        sessionStorage: debugSessionStorageAll(),
        isPermissionDenied: hooks.isPermissionDenied(),
        userAgent: navigator.userAgent,
        userActivation: navigator.userActivation
          ? {
              isActive: navigator.userActivation.isActive,
              hasBeenActive: navigator.userActivation.hasBeenActive,
            }
          : null,
        visibilityState: document.visibilityState,
        hasFocus: document.hasFocus(),
      });

      navigator.mediaDevices
        .getUserMedia({ audio: true })
        .then(function (s) {
          debugLog("getUserMedia after", {
            ok: true,
            trackCount: s && s.getTracks ? s.getTracks().length : null,
            trackLabels: s && s.getTracks ? s.getTracks().map(function (t) { return t.label; }) : null,
          });
          stream = s;
          var picked = pickMimeType();
          try {
            recorder = picked
              ? new MediaRecorder(s, { mimeType: picked })
              : new MediaRecorder(s);
          } catch (e) {
            releaseStream();
            resetBusy();
            hooks.showServiceError(MIC_START_FAIL_MSG);
            debugLog("MediaRecorder construct error", { name: e.name, message: e.message });
            return;
          }

          mimeType = recorder.mimeType || picked || "audio/mp4";
          recordStartedAt = Date.now();
          isRecording = true;
          setRecordingUI();

          recorder.ondataavailable = function (ev) {
            if (ev.data && ev.data.size > 0) chunks.push(ev.data);
          };
          recorder.onstop = function () {
            tsMark("onstop");
            finishRecording();
          };
          recorder.onerror = function () {
            resetBusy();
            releaseStream();
            hooks.showServiceError("錄音失敗，請再試一次");
            hooks.showRetry();
          };

          recorder.start();
          perfMark(2, "開始錄音");
          startSilenceMonitor(s);
          maxStopTimer = setTimeout(function () {
            tsMark("MAX_RECORD_MS 達標，觸發 stopRecording", { max_record_ms: MAX_RECORD_MS });
            stopRecording();
          }, MAX_RECORD_MS);
        })
        .catch(function (err) {
          debugLog("getUserMedia catch", {
            name: err && err.name,
            message: err && err.message,
            sessionStorage: debugSessionStorageAll(),
          });
          releaseStream();
          resetBusy();
          if (err && err.name === "NotAllowedError") {
            hooks.markPermissionDenied();
            hooks.setBlocked();
            return;
          }
          hooks.showServiceError(MIC_START_FAIL_MSG);
          hooks.showRetry();
        });
    }

    function onMicClick(e) {
      debugLog("click enter", {
        type: e && e.type,
        busy: busy,
        isRecording: isRecording,
        isPermissionDenied: hooks.isPermissionDenied(),
        sessionStorage: debugSessionStorageAll(),
        userActivation: navigator.userActivation
          ? {
              isActive: navigator.userActivation.isActive,
              hasBeenActive: navigator.userActivation.hasBeenActive,
            }
          : null,
      });
      e.preventDefault();
      e.stopImmediatePropagation();
      if (busy && !isRecording) {
        debugLog("click exit", "busy && !isRecording");
        return;
      }
      if (hooks.isPermissionDenied()) {
        debugLog("click exit", "isPermissionDenied — setBlocked");
        hooks.setBlocked();
        return;
      }
      if (isRecording) {
        debugLog("click exit", "stopRecording");
        stopRecording();
        return;
      }
      debugLog("click → startRecording", null);
      perfReset();
      tsReset();
      perfMark(1, "按下麥克風");
      startRecording();
    }

    btn.addEventListener("click", onMicClick, true);
    debugLog("addEventListener voice-search-button click", "registered capture=true");
    if (retry) {
      retry.addEventListener("click", onMicClick, true);
      debugLog("addEventListener voice-search-retry click", "registered capture=true");
    }
    hooks.setState("idle");
    window.__voiceSearchIOS = "20260804debug-v1";
    debugLog("init complete", { tag: window.__voiceSearchIOS });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      debugLog("DOMContentLoaded", { readyState: document.readyState });
      init();
    });
  } else {
    debugLog("DOMContentLoaded skipped", "document already past loading");
    init();
  }
})();
