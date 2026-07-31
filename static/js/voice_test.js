(function () {
  "use strict";

  var config = window.VOICE_TEST_CONFIG || {};
  var TRANSCRIBE_URL = config.transcribeUrl || "/api/voice/transcribe/";
  var RECORD_MS = config.recordMs || 8000;

  var startBtn = document.getElementById("voice-test-start");
  var statusEl = document.getElementById("voice-test-status");
  var errorEl = document.getElementById("voice-test-error");
  var resultWrap = document.getElementById("voice-test-result");
  var resultText = document.getElementById("voice-test-result-text");
  var capabilityEl = document.getElementById("voice-test-capability");
  var debugEl = document.getElementById("voice-test-debug");

  if (!startBtn) return;

  var mediaRecorder = null;
  var mediaStream = null;
  var audioChunks = [];
  var recordStopTimer = null;
  var isRecording = false;
  var lastDebug = {
    getUserMedia: "",
    mediaRecorder: "",
    mimeType: "",
    api: "",
  };

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function setStatus(text, mode) {
    if (!statusEl) return;
    statusEl.hidden = !text;
    statusEl.textContent = text || "";
    statusEl.className = "voice-test__status";
    if (mode) statusEl.classList.add("voice-test__status--" + mode);
  }

  function setError(text) {
    if (!errorEl) return;
    errorEl.hidden = !text;
    errorEl.textContent = text || "";
  }

  function clearResult() {
    if (resultWrap) resultWrap.hidden = true;
    if (resultText) resultText.textContent = "";
  }

  function showResult(text) {
    if (resultWrap) resultWrap.hidden = false;
    if (resultText) resultText.textContent = "「" + text + "」";
  }

  function renderDebug() {
    if (!debugEl) return;
    var lines = [];
    if (lastDebug.getUserMedia) lines.push("getUserMedia：" + lastDebug.getUserMedia);
    if (lastDebug.mediaRecorder) lines.push("MediaRecorder：" + lastDebug.mediaRecorder);
    if (lastDebug.mimeType) lines.push("音訊格式：" + lastDebug.mimeType);
    if (lastDebug.api) lines.push("辨識 API：" + lastDebug.api);
    debugEl.hidden = !lines.length;
    debugEl.textContent = lines.join("\n");
  }

  function formatMediaError(err) {
    if (!err) return "未知錯誤";
    var name = err.name || "Error";
    var message = err.message || "";
    if (name === "NotAllowedError") return "NotAllowedError（麥克風權限被拒絕）";
    if (name === "NotFoundError") return "NotFoundError（找不到麥克風）";
    if (name === "NotSupportedError") return "NotSupportedError（此瀏覽器不支援 getUserMedia）";
    if (name === "NotReadableError") return "NotReadableError（麥克風被其他 App 占用）";
    if (name === "SecurityError") return "SecurityError（需 HTTPS 才能使用麥克風）";
    if (name === "AbortError") return "AbortError（操作已取消）";
    return name + (message ? "（" + message + "）" : "");
  }

  function formatRecorderError(err) {
    if (!err) return "MediaRecorder 建立失敗";
    var name = err.name || "Error";
    var message = err.message || "";
    return "MediaRecorder：" + name + (message ? "（" + message + "）" : "");
  }

  function checkCapabilities() {
    var hasMediaDevices = !!(navigator.mediaDevices);
    var hasGetUserMedia = !!(
      navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function"
    );
    var hasMediaRecorder = typeof MediaRecorder !== "undefined";
    var mimeType = pickAudioMimeType();

    var lines = [
      "navigator.mediaDevices：" + (hasMediaDevices ? "有" : "無"),
      "getUserMedia：" + (hasGetUserMedia ? "有" : "無"),
      "MediaRecorder：" + (hasMediaRecorder ? "有" : "無"),
      "支援音訊格式：" + (mimeType || "（使用瀏覽器預設）"),
    ];

    if (capabilityEl) {
      capabilityEl.hidden = false;
      capabilityEl.textContent = lines.join("\n");
    }

    if (!hasGetUserMedia) {
      startBtn.disabled = true;
      setError("NotSupportedError（此瀏覽器不支援 getUserMedia）");
    } else if (!hasMediaRecorder) {
      startBtn.disabled = true;
      setError("NotSupportedError（此瀏覽器不支援 MediaRecorder）");
    }

    return hasGetUserMedia && hasMediaRecorder;
  }

  function stopMediaStream() {
    if (!mediaStream) return;
    mediaStream.getTracks().forEach(function (track) {
      track.stop();
    });
    mediaStream = null;
  }

  function destroyRecording() {
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

  function pickAudioMimeType() {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
    var types = [
      "audio/mp4",
      "audio/aac",
      "audio/webm;codecs=opus",
      "audio/webm",
    ];
    for (var i = 0; i < types.length; i++) {
      if (MediaRecorder.isTypeSupported(types[i])) return types[i];
    }
    return "";
  }

  function uploadRecording(mimeType) {
    isRecording = false;
    startBtn.disabled = false;

    if (!audioChunks.length) {
      setStatus("", "");
      setError("沒有收到語音，請再試一次");
      lastDebug.api = "失敗（錄音檔為空）";
      renderDebug();
      return;
    }

    setStatus("正在辨識...", "processing");
    setError("");

    var blob = new Blob(audioChunks, { type: mimeType || "audio/webm" });
    audioChunks = [];
    var ext = mimeType && mimeType.indexOf("mp4") >= 0 ? "mp4" : "webm";
    var formData = new FormData();
    formData.append("audio", blob, "voice." + ext);

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
        return res.json().then(function (data) {
          return { status: res.status, data: data };
        });
      })
      .then(function (result) {
        setStatus("", "");
        var data = result.data;
        if (!data || !data.ok || !data.text) {
          var apiError = (data && data.error) || "辨識失敗";
          lastDebug.api = "失敗（HTTP " + result.status + "：" + apiError + "）";
          renderDebug();
          if (apiError === "語音服務尚未設定") {
            setError(
              "錄音成功。OpenAI 尚未設定：請在 Railway 加入 OPENAI_API_KEY 環境變數"
            );
          } else {
            setError("錄音成功。辨識失敗：" + apiError);
          }
          return;
        }
        lastDebug.api = "成功";
        renderDebug();
        showResult(String(data.text).trim());
      })
      .catch(function (err) {
        setStatus("", "");
        lastDebug.api = "失敗（網路錯誤：" + (err && err.message ? err.message : "unknown") + "）";
        renderDebug();
        setError("錄音成功。上傳失敗：沒有網路，請再試一次");
      });
  }

  function beginRecording() {
    if (isRecording) return;
    if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
      var msg = "NotSupportedError（getUserMedia 不存在）";
      lastDebug.getUserMedia = "失敗（" + msg + "）";
      renderDebug();
      setError(msg);
      return;
    }
    if (typeof MediaRecorder === "undefined") {
      var recMsg = "NotSupportedError（MediaRecorder 不存在）";
      lastDebug.mediaRecorder = "失敗（" + recMsg + "）";
      renderDebug();
      setError(recMsg);
      return;
    }

    clearResult();
    setError("");
    lastDebug = { getUserMedia: "", mediaRecorder: "", mimeType: "", api: "" };
    isRecording = true;
    startBtn.disabled = true;
    setStatus("🎤 錄音中…", "recording");
    audioChunks = [];
    destroyRecording();

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then(function (stream) {
        lastDebug.getUserMedia = "成功";
        renderDebug();

        if (!isRecording) {
          stream.getTracks().forEach(function (track) {
            track.stop();
          });
          return;
        }

        mediaStream = stream;
        var mimeType = pickAudioMimeType();
        lastDebug.mimeType = mimeType || "瀏覽器預設";

        try {
          mediaRecorder = mimeType
            ? new MediaRecorder(stream, { mimeType: mimeType })
            : new MediaRecorder(stream);
          lastDebug.mediaRecorder =
            "成功（state=" + mediaRecorder.state + "）";
          renderDebug();
        } catch (e) {
          lastDebug.mediaRecorder = "失敗（" + formatRecorderError(e) + "）";
          renderDebug();
          stopMediaStream();
          isRecording = false;
          startBtn.disabled = false;
          setStatus("", "");
          setError(formatRecorderError(e));
          return;
        }

        mediaRecorder.ondataavailable = function (ev) {
          if (ev.data && ev.data.size > 0) audioChunks.push(ev.data);
        };
        mediaRecorder.onstop = function () {
          stopMediaStream();
          uploadRecording(mimeType);
        };
        mediaRecorder.onerror = function (ev) {
          isRecording = false;
          destroyRecording();
          startBtn.disabled = false;
          setStatus("", "");
          var recErr = ev && ev.error ? formatRecorderError(ev.error) : "MediaRecorder 錄音錯誤";
          lastDebug.mediaRecorder = "失敗（" + recErr + "）";
          renderDebug();
          setError(recErr);
        };

        mediaRecorder.start();
        recordStopTimer = setTimeout(function () {
          if (mediaRecorder && mediaRecorder.state === "recording") {
            try {
              mediaRecorder.stop();
            } catch (e) {
              /* ignore */
            }
          }
        }, RECORD_MS);
      })
      .catch(function (err) {
        isRecording = false;
        startBtn.disabled = false;
        setStatus("", "");
        var mediaMsg = formatMediaError(err);
        lastDebug.getUserMedia = "失敗（" + mediaMsg + "）";
        renderDebug();
        setError(mediaMsg);
      });
  }

  checkCapabilities();
  startBtn.addEventListener("click", beginRecording);
})();
