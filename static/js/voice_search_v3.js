(function () {
  "use strict";

  var MAX_RECORD_MS = 6000;
  var STOP_FLUSH_MS = 120;

  var config = window.VOICE_TEST_V3_CONFIG || {};
  var TRANSCRIBE_URL = config.transcribeUrl || "/api/voice/transcribe/";

  var recordBtn = document.getElementById("v3-record-btn");
  var transcribeBtn = document.getElementById("v3-transcribe-btn");
  var recordHint = document.getElementById("v3-record-hint");
  var recordTimer = document.getElementById("v3-record-timer");
  var playbackSection = document.getElementById("v3-playback-section");
  var audioPlayer = document.getElementById("v3-audio-player");
  var metaDuration = document.getElementById("v3-meta-duration");
  var metaBytes = document.getElementById("v3-meta-bytes");
  var metaMime = document.getElementById("v3-meta-mime");
  var resultSection = document.getElementById("v3-result-section");
  var resultBox = document.getElementById("v3-result-box");

  if (!recordBtn) return;

  var recorder = null;
  var stream = null;
  var chunks = [];
  var mimeType = "";
  var recordedBlob = null;
  var recordStartedAt = 0;
  var maxStopTimer = null;
  var elapsedTimer = null;
  var isRecording = false;

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
    return "voice.mp4";
  }

  function formatSeconds(ms) {
    return (ms / 1000).toFixed(2) + " 秒";
  }

  function clearTimers() {
    if (maxStopTimer) {
      clearTimeout(maxStopTimer);
      maxStopTimer = null;
    }
    if (elapsedTimer) {
      clearInterval(elapsedTimer);
      elapsedTimer = null;
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

  function setRecordingUi(active) {
    isRecording = active;
    recordBtn.textContent = active ? "停止錄音" : "開始錄音";
    recordBtn.classList.toggle("v3-btn--recording", active);
    if (recordHint) {
      recordHint.textContent = active
        ? "正在錄音…再按一次可停止（最多 6 秒）"
        : "按一下開始錄音，再按一下停止";
    }
    if (recordTimer) {
      recordTimer.hidden = !active;
      if (!active) recordTimer.textContent = "";
    }
  }

  function hideResult() {
    if (resultSection) resultSection.hidden = true;
    if (resultBox) {
      resultBox.hidden = true;
      resultBox.className = "v3-result-box";
      resultBox.textContent = "";
    }
  }

  function showResult(kind, title, detail) {
    if (!resultSection || !resultBox) return;
    resultSection.hidden = false;
    resultBox.hidden = false;
    resultBox.className = "v3-result-box v3-result-box--" + kind;
    resultBox.textContent = title + (detail ? "\n" + detail : "");
  }

  function hidePlayback() {
    recordedBlob = null;
    if (playbackSection) playbackSection.hidden = true;
    if (audioPlayer) {
      audioPlayer.removeAttribute("src");
      audioPlayer.load();
    }
    if (transcribeBtn) transcribeBtn.disabled = true;
    if (metaDuration) metaDuration.textContent = "—";
    if (metaBytes) metaBytes.textContent = "—";
    if (metaMime) metaMime.textContent = "—";
  }

  function showPlayback(blob, durationMs) {
    recordedBlob = blob;
    if (playbackSection) playbackSection.hidden = false;
    if (audioPlayer) {
      audioPlayer.src = URL.createObjectURL(blob);
      audioPlayer.load();
    }
    if (metaDuration) metaDuration.textContent = formatSeconds(durationMs);
    if (metaBytes) metaBytes.textContent = String(blob.size) + " bytes";
    if (metaMime) metaMime.textContent = blob.type || mimeType || "—";
    if (transcribeBtn) transcribeBtn.disabled = blob.size === 0;
  }

  function showLocalNoSound() {
    showResult("no-sound", "沒錄到聲音", "錄音檔大小為 0，請再試一次。");
  }

  function classifyApiError(message, httpStatus) {
    var msg = (message || "").trim();
    if (msg === "語音服務尚未設定") {
      return { kind: "not-configured", title: "語音服務未設定", detail: msg };
    }
    if (msg.indexOf("格式") >= 0) {
      return { kind: "format", title: "音檔格式錯誤", detail: msg };
    }
    if (msg.indexOf("聽不清楚") >= 0) {
      return { kind: "empty", title: "辨識結果為空", detail: msg };
    }
    if (msg.indexOf("AI 額度不足") >= 0) {
      return { kind: "quota", title: "AI 額度不足", detail: msg };
    }
    if (msg.indexOf("設定錯誤") >= 0 || msg.indexOf("暫時無法") >= 0 || httpStatus >= 500) {
      return { kind: "openai", title: "OpenAI 錯誤", detail: msg || "HTTP " + httpStatus };
    }
    if (msg.indexOf("沒有收到") >= 0) {
      return { kind: "no-sound", title: "沒錄到聲音", detail: msg };
    }
    return { kind: "openai", title: "OpenAI 錯誤", detail: msg || "HTTP " + httpStatus };
  }

  function finishRecording(durationMs) {
    clearTimers();
    setRecordingUi(false);
    releaseStream();

    var blob = new Blob(chunks, { type: mimeType || "audio/mp4" });
    chunks = [];

    if (!blob.size) {
      hidePlayback();
      showLocalNoSound();
      return;
    }

    hideResult();
    showPlayback(blob, durationMs);
  }

  function stopRecording() {
    if (!recorder || recorder.state !== "recording") return;

    clearTimers();
    setRecordingUi(false);

    var durationMs = Math.max(0, Date.now() - recordStartedAt);

    if (typeof recorder.requestData === "function") {
      try {
        recorder.requestData();
      } catch (e) {
        /* ignore */
      }
    }

    setTimeout(function () {
      if (!recorder || recorder.state !== "recording") {
        finishRecording(durationMs);
        return;
      }
      try {
        recorder.stop();
      } catch (e) {
        finishRecording(durationMs);
      }
    }, STOP_FLUSH_MS);
  }

  function startRecording() {
    hideResult();
    hidePlayback();
    chunks = [];
    recordedBlob = null;

    if (typeof navigator.mediaDevices === "undefined" || !navigator.mediaDevices.getUserMedia) {
      showResult("format", "音檔格式錯誤", "此瀏覽器不支援麥克風錄音。");
      return;
    }
    if (typeof MediaRecorder === "undefined") {
      showResult("format", "音檔格式錯誤", "此瀏覽器不支援 MediaRecorder。");
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
          showResult("format", "音檔格式錯誤", "無法建立錄音器：" + (e.message || e.name || e));
          return;
        }

        mimeType = recorder.mimeType || picked || "audio/mp4";
        recordStartedAt = Date.now();
        setRecordingUi(true);

        recorder.ondataavailable = function (ev) {
          if (ev.data && ev.data.size > 0) chunks.push(ev.data);
        };
        recorder.onstop = function () {
          var durationMs = Math.max(0, Date.now() - recordStartedAt);
          finishRecording(durationMs);
        };
        recorder.onerror = function () {
          clearTimers();
          setRecordingUi(false);
          releaseStream();
          showResult("format", "音檔格式錯誤", "錄音過程發生錯誤。");
        };

        recorder.start();
        elapsedTimer = setInterval(function () {
          if (!recordTimer || !isRecording) return;
          var elapsed = Date.now() - recordStartedAt;
          recordTimer.textContent = formatSeconds(elapsed);
        }, 100);
        maxStopTimer = setTimeout(stopRecording, MAX_RECORD_MS);
      })
      .catch(function (err) {
        releaseStream();
        setRecordingUi(false);
        var detail = err && err.name === "NotAllowedError"
          ? "麥克風權限被拒絕。"
          : (err && err.message) || "無法使用麥克風。";
        showResult("format", "音檔格式錯誤", detail);
      });
  }

  function onRecordClick() {
    if (isRecording) {
      stopRecording();
      return;
    }
    startRecording();
  }

  function onTranscribeClick() {
    if (!recordedBlob || recordedBlob.size === 0) {
      showLocalNoSound();
      return;
    }

    hideResult();
    if (transcribeBtn) transcribeBtn.disabled = true;
    if (transcribeBtn) transcribeBtn.textContent = "辨識中…";

    var formData = new FormData();
    formData.append("audio", recordedBlob, filenameForMime(recordedBlob.type || mimeType));

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
          return { status: res.status, ok: res.ok, data: data, raw: text };
        });
      })
      .then(function (result) {
        if (transcribeBtn) {
          transcribeBtn.disabled = false;
          transcribeBtn.textContent = "送出辨識";
        }

        var data = result.data || {};
        var transcript = (data.text || "").trim();
        if (result.ok && data.ok && transcript) {
          showResult("success", "辨識成功", "「" + transcript + "」");
          return;
        }

        var classified = classifyApiError(data.error || "", result.status);
        showResult(classified.kind, classified.title, classified.detail);
      })
      .catch(function () {
        if (transcribeBtn) {
          transcribeBtn.disabled = false;
          transcribeBtn.textContent = "送出辨識";
        }
        showResult("openai", "OpenAI 錯誤", "無法連線到語音辨識服務。");
      });
  }

  recordBtn.addEventListener("click", onRecordClick);
  if (transcribeBtn) transcribeBtn.addEventListener("click", onTranscribeClick);
})();
