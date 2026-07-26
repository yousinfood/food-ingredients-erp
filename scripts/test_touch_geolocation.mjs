import fs from "fs";
import path from "path";
import vm from "vm";
import { fileURLToPath } from "url";

const jsPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "../static/js/touch-geolocation.js"
);
const source = fs.readFileSync(jsPath, "utf8");

const window = { navigator: { geolocation: {}, permissions: null } };
vm.runInNewContext(source, { window, navigator: window.navigator, module: { exports: {} } });
const T = window.TouchGeolocation;

let failed = 0;

function assert(cond, label) {
  if (!cond) {
    console.error("FAIL:", label);
    failed += 1;
  }
}

assert(
  T.messageFromGeolocationError({ code: 1 }).kind === "denied",
  "PERMISSION_DENIED → denied"
);
assert(
  T.messageFromGeolocationError({ code: 1 }).message !== T.MSG.disabled,
  "denied must not use disabled copy"
);
assert(
  T.messageFromGeolocationError({ code: 3 }).kind === "timeout",
  "TIMEOUT → timeout"
);
assert(
  T.messageFromGeolocationError({
    code: 2,
    message: "Location services are turned off",
  }).kind === "disabled",
  "POSITION_UNAVAILABLE + turned off → disabled"
);
assert(
  T.messageFromGeolocationError({ code: 2, message: "Position update is unavailable" })
    .kind === "unavailable",
  "generic POSITION_UNAVAILABLE → unavailable not disabled"
);
assert(
  T.messageFromGeolocationError({ code: 2 }).kind === "unavailable",
  "POSITION_UNAVAILABLE without message → unavailable not disabled"
);
assert(
  T.coerceMappedError({ code: 2, message: "Location services are turned off" }).message ===
    T.MSG.disabled,
  "raw browser error → 繁中 disabled"
);
assert(
  T.coerceMappedError({ code: 2, message: "Location services are turned off" }).message.indexOf(
    "Location"
  ) === -1,
  "never show English browser geolocation message in UI"
);
assert(
  T.coerceMappedError({ code: 2 }).kind === "unavailable",
  "iPad-like code 2 without message → unavailable"
);

if (failed) {
  process.exit(1);
}
console.log("touch-geolocation message mapping OK");
