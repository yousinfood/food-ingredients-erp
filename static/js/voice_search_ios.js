(function () {
  "use strict";

  var MAX_RECORD_MS = 6000;
  var STOP_FLUSH_MS = 120;
  var MIN_BLOB_BYTES = 100;
  var TRANSCRIBE_URL = "/api/voice/transcribe/";

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
    if (!isIOS()) return;

    var btn = document.getElementById("voice-search-button");
    var retry = document.getElementById("voice-search-retry");
    if (!btn) return;

    var hooks = window.__yousinTouchVoice;
    if (!hooks) {
      console.error("[voice-ios] missing window.__yousinTouchVoice");
      return;
    }

    var recorder = null;
    var stream = null;
    var chunks = [];
    var mimeType = "";
    var recordStartedAt = 0;
    var maxStopTimer = null;
    var isRecording = false;
    var busy = false;

    function clearTimers() {
      if (maxStopTimer) {
        clearTimeout(maxStopTimer);
        maxStopTimer = null;
      }
    }

    function releaseStream() {
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
      hooks.setState("processing");
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
          recorder.stop();
        } catch (e) {
          finishRecording();
        }
      }, STOP_FLUSH_MS);
    }

    function startRecording() {
      if (busy) return;
      busy = true;
      chunks = [];

      if (retry) retry.hidden = true;
      hooks.prepareSession();
      hooks.haptic();
      hooks.setState("starting");

      if (typeof navigator.mediaDevices === "undefined" || !navigator.mediaDevices.getUserMedia) {
        resetBusy();
        hooks.showServiceError("此裝置無法使用麥克風錄音");
        return;
      }
      if (typeof MediaRecorder === "undefined") {
        resetBusy();
        hooks.showServiceError("此瀏覽器不支援語音錄音");
        return;
      }

      navigator.mediaDevices
        .getUserMedia({ audio: true })
        .then(function (s) {
          stream = s;
          var picked = pickMimeType();
          try {
            recorder = picked
              ? new MediaRecorder(s, { mimeType: picked })
              : new MediaRecorder(s);
          } catch (e) {
            releaseStream();
            resetBusy();
            hooks.showServiceError("無法啟動錄音，請改用文字搜尋");
            return;
          }

          mimeType = recorder.mimeType || picked || "audio/mp4";
          recordStartedAt = Date.now();
          isRecording = true;
          hooks.setState("listening");

          recorder.ondataavailable = function (ev) {
            if (ev.data && ev.data.size > 0) chunks.push(ev.data);
          };
          recorder.onstop = function () {
            finishRecording();
          };
          recorder.onerror = function () {
            resetBusy();
            releaseStream();
            hooks.showServiceError("錄音失敗，請再試一次");
            hooks.showRetry();
          };

          recorder.start();
          maxStopTimer = setTimeout(stopRecording, MAX_RECORD_MS);
        })
        .catch(function (err) {
          releaseStream();
          resetBusy();
          if (err && err.name === "NotAllowedError") {
            hooks.markPermissionDenied();
            hooks.setBlocked();
            return;
          }
          hooks.showServiceError("無法使用麥克風，請改用文字搜尋");
          hooks.showRetry();
        });
    }

    function onMicClick(e) {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (busy && !isRecording) return;
      if (hooks.isPermissionDenied()) {
        hooks.setBlocked();
        return;
      }
      if (isRecording) {
        stopRecording();
        return;
      }
      startRecording();
    }

    btn.addEventListener("click", onMicClick, true);
    if (retry) retry.addEventListener("click", onMicClick, true);
    hooks.setState("idle");
    window.__voiceSearchIOS = "20260802";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
