(function (global) {
  "use strict";

  var GEO = global.navigator && global.navigator.geolocation;
  var PERM = global.navigator && global.navigator.permissions;

  var CODE = {
    PERMISSION_DENIED: 1,
    POSITION_UNAVAILABLE: 2,
    TIMEOUT: 3,
  };

  var MSG = {
    denied: "尚未允許使用定位，請在 Safari 設定中允許此網站",
    disabled:
      "定位服務已關閉，請到「設定 → 隱私權與安全性 → 定位服務」開啟",
    timeout: "定位逾時，請再試一次",
    unavailable: "目前無法取得定位，仍可開啟地圖導航",
    unsupported: "此裝置不支援定位，仍可開啟地圖導航",
    unknown: "無法取得定位，仍可開啟地圖導航",
  };

  function normalizeMessage(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/\u2019/g, "'");
  }

  function isLocationServicesDisabledMessage(message) {
    var msg = normalizeMessage(message);
    if (!msg) return false;
    if (msg.indexOf("location services") === -1 && msg.indexOf("定位服务") === -1) {
      return false;
    }
    return (
      msg.indexOf("turned off") !== -1 ||
      msg.indexOf("disabled") !== -1 ||
      msg.indexOf("已关闭") !== -1 ||
      msg.indexOf("已關閉") !== -1
    );
  }

  function messageFromGeolocationError(error) {
    if (!GEO) {
      return { kind: "unsupported", message: MSG.unsupported, showBanner: false };
    }
    if (!error || typeof error.code !== "number") {
      return { kind: "unknown", message: MSG.unknown, showBanner: false };
    }

    if (error.code === CODE.PERMISSION_DENIED) {
      return { kind: "denied", message: MSG.denied, showBanner: true };
    }
    if (error.code === CODE.TIMEOUT) {
      return { kind: "timeout", message: MSG.timeout, showBanner: false };
    }
    if (error.code === CODE.POSITION_UNAVAILABLE) {
      if (isLocationServicesDisabledMessage(error.message)) {
        return { kind: "disabled", message: MSG.disabled, showBanner: true };
      }
      return { kind: "unavailable", message: MSG.unavailable, showBanner: false };
    }
    return { kind: "unknown", message: MSG.unknown, showBanner: false };
  }

  /** Never surface browser GeolocationPositionError.message (often English) in UI. */
  function coerceMappedError(err) {
    if (err && typeof err.kind === "string" && typeof err.message === "string") {
      return {
        kind: err.kind,
        message: err.message,
        showBanner:
          err.showBanner === true ||
          err.kind === "denied" ||
          err.kind === "disabled",
      };
    }
    var raw = err && err.raw ? err.raw : err;
    if (raw && typeof raw.code === "number") {
      return messageFromGeolocationError(raw);
    }
    return messageFromGeolocationError(null);
  }

  function queryGeolocationPermission() {
    if (!PERM || typeof PERM.query !== "function") {
      return Promise.resolve({ state: "unknown", supported: false });
    }
    return PERM.query({ name: "geolocation" })
      .then(function (status) {
        return { state: status && status.state ? status.state : "unknown", supported: true };
      })
      .catch(function () {
        return { state: "unknown", supported: false };
      });
  }

  function getCurrentPosition(options) {
    options = options || {};
    var timeout = typeof options.timeout === "number" ? options.timeout : 12000;
    var maximumAge = typeof options.maximumAge === "number" ? options.maximumAge : 60000;

    return new Promise(function (resolve, reject) {
      if (!GEO || typeof GEO.getCurrentPosition !== "function") {
        reject({ kind: "unsupported", message: MSG.unsupported });
        return;
      }
      GEO.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: timeout,
        maximumAge: maximumAge,
      });
    });
  }

  function requestCurrentPosition(options) {
    return queryGeolocationPermission().then(function (perm) {
      if (perm.state === "denied") {
        return Promise.reject({ kind: "denied", message: MSG.denied, fromPermission: true });
      }
      return getCurrentPosition(options).catch(function (err) {
        var mapped = messageFromGeolocationError(err);
        return Promise.reject({
          kind: mapped.kind,
          message: mapped.message,
          showBanner: mapped.showBanner,
          raw: err,
        });
      });
    });
  }

  function appleMapsHref(destinationHref, coords) {
    if (!destinationHref) return destinationHref;
    if (!coords || typeof coords.latitude !== "number") return destinationHref;
    try {
      var url = new URL(destinationHref);
      url.searchParams.set(
        "saddr",
        coords.latitude + "," + coords.longitude
      );
      return url.toString();
    } catch (e) {
      return destinationHref;
    }
  }

  function showLocationBanner(text, bannerEl) {
    if (!bannerEl || !text) return;
    var textEl = bannerEl.querySelector(".touch-location-banner__text");
    if (textEl) textEl.textContent = text;
    bannerEl.hidden = false;
    bannerEl.setAttribute("aria-hidden", "false");
  }

  function hideLocationBanner(bannerEl) {
    if (!bannerEl) return;
    bannerEl.hidden = true;
    bannerEl.setAttribute("aria-hidden", "true");
  }

  function openMapsWithOptionalOrigin(destinationHref, isApple, bannerEl) {
    if (!destinationHref) return;
    if (!GEO) {
      global.location.href = destinationHref;
      return;
    }

    requestCurrentPosition()
      .then(function (pos) {
        hideLocationBanner(bannerEl);
        var coords = pos && pos.coords;
        var href = isApple
          ? appleMapsHref(destinationHref, coords)
          : destinationHref;
        global.location.href = href;
      })
      .catch(function (err) {
        var mapped = coerceMappedError(err);
        if (mapped.showBanner) {
          showLocationBanner(mapped.message, bannerEl);
        } else if (mapped.message && mapped.kind !== "denied") {
          showLocationBanner(mapped.message, bannerEl);
          global.setTimeout(function () {
            hideLocationBanner(bannerEl);
          }, 3500);
        }
        global.location.href = destinationHref;
      });
  }

  function bindNavigateButtons(bannerEl) {
    document.querySelectorAll("[data-touch-navigate]").forEach(function (btn) {
      if (btn.dataset.touchNavigateBound === "1") return;
      btn.dataset.touchNavigateBound = "1";
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var isApple = /iPhone|iPad|iPod|Macintosh|Mac OS X/i.test(
          global.navigator.userAgent
        );
        var href = isApple ? btn.dataset.mapsApple : btn.dataset.mapsGoogle;
        openMapsWithOptionalOrigin(href, isApple, bannerEl);
      });
    });
  }

  function initLocationBanner(bannerEl) {
    if (!bannerEl) return;
    hideLocationBanner(bannerEl);
  }

  function init() {
    var bannerEl = document.getElementById("touch-location-banner");
    initLocationBanner(bannerEl);
    bindNavigateButtons(bannerEl);

    var retryBtn = document.getElementById("touch-location-retry");
    if (retryBtn && bannerEl) {
      retryBtn.addEventListener("click", function () {
        hideLocationBanner(bannerEl);
        requestCurrentPosition()
          .then(function () {
            hideLocationBanner(bannerEl);
          })
          .catch(function (err) {
            var mapped = coerceMappedError(err);
            if (mapped.showBanner || mapped.kind === "denied") {
              showLocationBanner(mapped.message, bannerEl);
            }
          });
      });
    }
  }

  var api = {
    CODE: CODE,
    MSG: MSG,
    messageFromGeolocationError: messageFromGeolocationError,
    coerceMappedError: coerceMappedError,
    isLocationServicesDisabledMessage: isLocationServicesDisabledMessage,
    queryGeolocationPermission: queryGeolocationPermission,
    requestCurrentPosition: requestCurrentPosition,
    openMapsWithOptionalOrigin: openMapsWithOptionalOrigin,
    init: init,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  global.TouchGeolocation = api;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(typeof window !== "undefined" ? window : globalThis);
