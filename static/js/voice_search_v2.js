(function () {
  "use strict";

  var TRANSCRIBE = "/api/voice/transcribe/";
  var RECORD_MS = 4000;
  var IOS_RECORD_SLICE_MS = 250;
  var UNCLEAR = "聽不清楚，請再說一次";

  function isIOS() {
    var ua = navigator.userAgent || "";
    return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  function getCsrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function pickMime() {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
    var t = ["audio/mp4", "audio/aac", "audio/webm;codecs=opus", "audio/webm"];
    for (var i = 0; i < t.length; i++) if (MediaRecorder.isTypeSupported(t[i])) return t[i];
    return "";
  }

  function filenameFor(mime) {
    if (!mime || mime.indexOf("webm") >= 0) return "voice.webm";
    if (mime.indexOf("aac") >= 0) return "voice.m4a";
    return "voice.mp4";
  }

  function init() {
    console.log("[voice-v2] init() started");
    console.log("[voice-v2] MediaRecorder exists=" + (typeof MediaRecorder !== "undefined"));
    if (!isIOS()) return;
    var btn = document.getElementById("voice-search-button");
    var input = document.getElementById("customer-search-input");
    var retry = document.getElementById("voice-search-retry");
    console.log("[voice-v2] microphone button found=" + !!btn);
    console.log("[voice-v2] retry button found=" + !!retry);
    if (!btn || !input) return;

    var line1 = btn.querySelector(".voice-search-button__line1");
    var line2 = btn.querySelector(".voice-search-button__line2");
    var form = btn.closest("form") || document.getElementById("customer-search-form");
    var recorder, stream, chunks = [], timer, mimeType = "", busy = false;

    function setState(mode, detail) {
      btn.classList.remove("voice-search-button--idle", "voice-search-button--starting", "voice-search-button--listening", "voice-search-button--success", "voice-search-button--error");
      if (mode === "idle") {
        btn.classList.add("voice-search-button--idle");
        btn.disabled = false;
        if (line1) line1.textContent = "🎤 按這裡說話找客戶";
        if (line2) line2.textContent = "請用國語說客戶名稱";
      } else if (mode === "recording") {
        btn.classList.add("voice-search-button--listening");
        btn.disabled = true;
        if (line1) line1.textContent = "🎤 正在錄音…";
        if (line2) line2.textContent = "";
      } else if (mode === "processing") {
        btn.classList.add("voice-search-button--starting");
        btn.disabled = true;
        if (line1) line1.textContent = "🎤 正在辨識…";
        if (line2) line2.textContent = "";
      } else if (mode === "success") {
        btn.classList.add("voice-search-button--success");
        btn.disabled = false;
        if (line1) line1.textContent = "已聽到：" + (detail || "");
        if (line2) line2.textContent = "";
      } else if (mode === "error") {
        btn.classList.add("voice-search-button--error");
        btn.disabled = false;
        if (line1) line1.textContent = UNCLEAR;
        if (line2) line2.textContent = "";
        if (retry) retry.hidden = false;
      }
    }

    function cleanup() {
      if (timer) clearTimeout(timer);
      timer = null;
      if (recorder) {
        recorder.ondataavailable = recorder.onstop = recorder.onerror = null;
        recorder = null;
      }
      if (stream) {
        stream.getTracks().forEach(function (t) { t.stop(); });
        stream = null;
      }
      chunks = [];
      busy = false;
    }

    function applySearch(text) {
      console.log("[voice-v2] returned transcript=" + text);
      input.value = text;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      if (!form) return;
      if (typeof form.requestSubmit === "function") form.requestSubmit();
      else form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    }

    function upload(blob) {
      setState("processing");
      var fd = new FormData();
      fd.append("audio", blob, filenameFor(blob.type || mimeType));
      fetch(TRANSCRIBE, {
        method: "POST",
        body: fd,
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": getCsrf() },
      })
        .then(function (res) {
          return res.text().then(function (text) {
            var data = null;
            try { data = text ? JSON.parse(text) : null; } catch (e) { console.error("[voice-v2]", e); data = null; }
            console.log("[voice-v2] upload status=" + res.status);
            console.log("[voice-v2] response JSON=", data || text);
            return { httpOk: res.ok, data: data };
          });
        })
        .then(function (result) {
          var data = result.data || {};
          var transcript = (data.text || "").trim();
          cleanup();
          if (result.httpOk && data.ok && transcript) {
            setState("success", transcript);
            applySearch(transcript);
          } else {
            setState("error");
          }
        })
        .catch(function (err) {
          console.error("[voice-v2]", err);
          cleanup();
          setState("error");
        });
    }

    function stopRecording() {
      if (!recorder || recorder.state !== "recording") {
        console.log("[voice-v2] stopRecording skipped recorder.state=" + (recorder ? recorder.state : "null"));
        return;
      }
      console.log("[voice-v2] stopRecording recorder.state=" + recorder.state);
      if (typeof recorder.requestData === "function") {
        try {
          recorder.requestData();
          console.log("[voice-v2] requestData() recorder.state=" + recorder.state);
        } catch (e) {
          console.error("[voice-v2]", e);
        }
      }
      setTimeout(function () {
        if (!recorder || recorder.state !== "recording") return;
        try {
          console.log("[voice-v2] stop() recorder.state=" + recorder.state);
          recorder.stop();
        } catch (e) {
          console.error("[voice-v2]", e);
          cleanup();
          setState("error");
        }
      }, 100);
    }

    function startRecording() {
      if (busy) return;
      busy = true;
      if (retry) retry.hidden = true;
      setState("recording");
      chunks = [];
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function (s) {
          console.log("[voice-v2] microphone permission success");
          stream = s;
          var audioTrack = s.getAudioTracks()[0];
          if (audioTrack) {
            console.log("[voice-v2] audio track settings=", audioTrack.getSettings ? audioTrack.getSettings() : null);
          }
          var picked = pickMime();
          try {
            recorder = picked ? new MediaRecorder(s, { mimeType: picked }) : new MediaRecorder(s);
          } catch (e) {
            console.error("[voice-v2] microphone permission failure", e);
            cleanup();
            setState("error");
            return;
          }
          mimeType = recorder.mimeType || picked || "audio/mp4";
          console.log("[voice-v2] selected mimeType=" + mimeType);
          recorder.ondataavailable = function (ev) {
            var chunkSize = ev.data ? ev.data.size : 0;
            console.log("[voice-v2] ondataavailable recorder.state=" + (recorder ? recorder.state : "null") + " chunk size=" + chunkSize);
            if (ev.data && ev.data.size > 0) {
              console.log("[voice-v2] audio chunk size=" + ev.data.size);
              chunks.push(ev.data);
            }
          };
          recorder.onstop = function () {
            console.log("[voice-v2] onstop recorder.state=" + (recorder ? recorder.state : "null") + " chunks=" + chunks.length);
            var blob = new Blob(chunks, { type: mimeType });
            chunks = [];
            console.log("[voice-v2] final blob size=" + blob.size);
            if (!blob.size) { cleanup(); setState("error"); return; }
            upload(blob);
          };
          recorder.onerror = function (ev) {
            console.error("[voice-v2] MediaRecorder error recorder.state=" + (recorder ? recorder.state : "null"), ev);
            cleanup();
            setState("error");
          };
          recorder.start(IOS_RECORD_SLICE_MS);
          console.log("[voice-v2] recording started recorder.state=" + recorder.state);
          timer = setTimeout(stopRecording, RECORD_MS);
        })
        .catch(function (err) {
          console.error("[voice-v2] microphone permission failure", err);
          cleanup();
          setState("error");
        });
    }

    function onMic(e) {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (!busy) startRecording();
    }

    btn.addEventListener("click", onMic, true);
    if (retry) retry.addEventListener("click", onMic, true);
    setState("idle");
    window.__voiceSearchV2 = "20260801";
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
