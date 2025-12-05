import { Analytics } from "./analyticsLite";
import { facebook } from "./facebook";
import { googleAnalytics4 } from "./googleAnalytics4";
import {
  dbg,
  getSessionStorage,
  setSessionStorage,
  isBot,
  httpGet,
  httpPost,
  warn,
  afterDOMContentLoaded,
  isFunc
} from "./utils";

var VID_KEY = "__zar_vid";
var NUMBER_POOL_SUCCESS = "success";
var NUMBER_POOL_ERROR = "error";
var NUMBER_POOL_RENEWAL_INTERVAL_MS = 30 * 1000;
var NUMBER_POOL_RENEWAL_MIN_TIME_MS = 10 * 1000;
var getNumberFailureCount = 0;
var MAX_GET_NUMBER_FAILURES = 3;
var poolIntervals = {};
var lastRenewalAttemptMs = {};
var stopAllRenewals = false;

window.zarPoolData = window.zarPoolData || null;
window.zarPoolDLObserverDone = window.zarPoolDLObserverDone || false;
window.zarPoolDataLayer = window.zarPoolDataLayer || [];

// Tracks original phone numbers that have been replaced so
// we can revert if necessary.
var numberOverlayMap = new Map();

function generateVisitId() {
  return (
    Date.now().toString(36) + "." + Math.random().toString(36).substring(2)
  );
}

function initId(key, generator, getter, setter) {
  var id;
  var isNew = false;
  var t;
  var origReferrer = null;
  var idObj = getter(key);

  if (!idObj || !idObj.id) {
    id = generator();
    origReferrer = document.referrer;
    t = Date.now();
    isNew = true;
    dbg("new ID for", key, "-", id);
  } else {
    id = idObj.id;
    origReferrer = idObj.origReferrer;
    t = idObj.t;
  }

  var result = { id, t, origReferrer, isNew };
  setter(key, result);
  return result;
}

function initIDs() {
  var vidResult = initId(
    VID_KEY,
    generateVisitId,
    getSessionStorage,
    setSessionStorage
  );
  return { vid: vidResult };
}

function getDefaultApiUrl() {
  return window.location.protocol + "://" + window.location.host + "/api/v2";
}

function getIDObj(key) {
  return getSessionStorage(key);
}

function getID(key) {
  var obj = getIDObj(key);
  return obj ? obj.id : null;
}

function getStorage() {
  return {
    vid: getIDObj(VID_KEY)
  };
}

function getIDs() {
  return {
    vid: getID(VID_KEY)
  };
}

function extractPhoneNumber({ elem }) {
  // NOTE: only tested for US numbers!
  var numberText = null;
  var number = null;
  var href = null;
  var regex = new RegExp(
    "\\+?\\(?\\d*\\)? ?\\(?\\d+\\)?\\d*([\\s./-]?\\d{2,})+",
    "g"
  );

  if (elem.href && elem.href.startsWith("tel:")) {
    href = elem.href;
  }
  var text = elem.innerText;
  var html = elem.innerHTML;
  var match = regex.exec(text);
  if (match) {
    numberText = match[0].trim();
    number = numberText
      .replace("+", "")
      .replace(/-/g, "")
      .replace(/ /g, "")
      .replace("(", "")
      .replace(")", "")
      .replace(/^1/, "");
  }
  return { text, html, numberText, href, number };
}

function overlayPhoneNumber({ elems, number, force = false }) {
  var origNum;
  var overlayNum = number;
  if (!number.startsWith("+1")) {
    overlayNum = "+1" + number; // NOTE: expects 10-digit US numbers
  }

  for (var i = 0; i < elems.length; i++) {
    if (numberOverlayMap.has(elems[i])) {
      if (force) {
        origNum = numberOverlayMap.get(elems[i]);
      } else {
        dbg("element already in overlay map:", elems[i]);
        continue;
      }
    }

    var elemNum = extractPhoneNumber({ elem: elems[i] });

    if (!origNum) {
      origNum = elemNum;
    } else if (
      !force &&
      elemNum.number &&
      origNum.number &&
      origNum.number !== elemNum.number
    ) {
      warn(
        "overlaying multiple numbers with a single number",
        origNum.number,
        elemNum.number
      );
    }

    dbg("overlaying", overlayNum, "on", elems[i]);

    // Store the original values if this is the first time overlaying
    if (!numberOverlayMap.has(elems[i])) {
      numberOverlayMap.set(elems[i], elemNum);
    }

    if (elemNum.href) {
      elems[i].href = "tel:" + overlayNum;
    }

    if (elemNum.numberText) {
      // If there is a phone number present in the text...
      elems[i].innerHTML = "";
      if (elemNum.text) {
        var overlay = overlayNum;
        if (elemNum.numberText.indexOf("-") > -1) {
          overlay =
            overlayNum.slice(2, 5) +
            "-" +
            overlayNum.slice(5, 8) +
            "-" +
            overlayNum.slice(8, 12);
        }
        if (elemNum.html.indexOf("<img") > -1) {
          var numberHtml = elemNum.html.replace(elemNum.numberText, overlay);
          elems[i].innerHTML = numberHtml;
        } else {
          var numberText = elemNum.text.replace(elemNum.numberText, overlay);
          elems[i].appendChild(document.createTextNode(numberText));
        }
      } else {
        elems[i].appendChild(document.createTextNode(overlayNum));
      }
    } else {
      dbg("no number text found:", elems[i]);
    }
  }
}

function revertOverlayNumbers({ elems }) {
  for (var i = 0; i < elems.length; i++) {
    if (numberOverlayMap.has(elems[i])) {
      var currentHTML = elems[i].innerHTML;
      var origElemData = numberOverlayMap.get(elems[i]);
      dbg("orig:", origElemData);
      var origHTML = origElemData.html;
      dbg("reverting", currentHTML, "to", origHTML);
      // Prefer restoring original HTML; fall back to original text if HTML is empty/null
      if (origHTML !== undefined && origHTML !== null && origHTML !== "") {
        elems[i].innerHTML = origHTML;
      } else if (
        origElemData.text !== undefined &&
        origElemData.text !== null
      ) {
        elems[i].textContent = origElemData.text;
      } else {
        // As a last resort, clear contents
        elems[i].textContent = "";
      }
      if (origElemData.href) {
        elems[i].setAttribute("href", origElemData.href);
      }
      numberOverlayMap.delete(elems[i]);
    } else {
      dbg("element not in map:", elems[i]);
    }
  }
}

function clearPoolInterval(poolId) {
  clearInterval(poolIntervals[poolId]);
  delete poolIntervals[poolId];
}

function clearPoolIntervals() {
  for (var poolId in poolIntervals) {
    clearPoolInterval(poolId);
  }
}

async function getPoolNumber({
  poolId,
  apiUrl,
  number = null,
  context = null
}) {
  var payload = {
    pool_id: poolId,
    number: number,
    context: context,
    properties: {
      zar: getStorage()
    }
  };
  var resp = await httpPost({ url: `${apiUrl}/number_pool`, data: payload });
  return resp;
}

function poolActive() {
  return (
    window.zarPoolData &&
    window.zarPoolData.status === NUMBER_POOL_SUCCESS &&
    window.zarPoolData.number
  );
}

function drainPoolDataLayer() {
  if (
    !window.zarPoolDataLayer ||
    !Array.isArray(window.zarPoolDataLayer) ||
    window.zarPoolDataLayer.length === 0
  ) {
    return null;
  }

  var mergedObject = {};
  for (var i = 0; i < window.zarPoolDataLayer.length; i++) {
    var obj = window.zarPoolDataLayer[i];
    for (var key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        mergedObject[key] = obj[key];
      }
    }
  }

  window.zarPoolDataLayer.length = 0;
  return mergedObject;
}

async function updateTrackingNumberContext({
  apiUrl,
  poolId,
  number,
  context
}) {
  if (!poolActive()) {
    warn("no valid pool data, not updating context");
    return;
  }

  var payload = {
    pool_id: poolId,
    number: number,
    context: context,
    properties: {
      zar: getStorage()
    }
  };
  var resp = await httpPost({ url: `${apiUrl}/update_number`, data: payload });
  return resp;
}

async function getPoolStats({ apiUrl, key = null, with_contexts = false }) {
  var params = {
    key,
    with_contexts
  };
  var resp = await httpGet({
    url: `${apiUrl}/number_pool_stats`,
    params: params
  });
  return resp;
}

async function renewTrackingPool({
  overlayElements,
  apiUrl = getDefaultApiUrl(),
  contextCallback = null,
  initCallback = null,
  checkLastRenewal = true
} = {}) {
  if (stopAllRenewals) {
    return { status: NUMBER_POOL_ERROR, msg: "stopped" };
  }

  const poolId = window.zarPoolData.pool_id;
  const number = window.zarPoolData.number;

  // Skip if requested and the last attempt was too recent
  var now = Date.now();
  var last = lastRenewalAttemptMs[poolId];
  if (
    checkLastRenewal &&
    last &&
    now - last < NUMBER_POOL_RENEWAL_MIN_TIME_MS
  ) {
    return { status: NUMBER_POOL_SUCCESS };
  }

  lastRenewalAttemptMs[poolId] = now;

  var context = drainPoolDataLayer() || {};
  if (contextCallback) {
    context = contextCallback(context) || {};
  }

  try {
    var resp = await getPoolNumber({ poolId, apiUrl, number, context });
  } catch (e) {
    var msg = "error getting number: " + JSON.stringify(e);
    warn(msg);
    getNumberFailureCount++;
    if (getNumberFailureCount >= MAX_GET_NUMBER_FAILURES) {
      warn("max failures, stopping pool");
      stopAllRenewals = true;
      clearPoolIntervals();
      if (overlayElements) {
        revertOverlayNumbers({ elems: overlayElements });
      }
    }
    return { status: NUMBER_POOL_ERROR, msg };
  }

  if (resp.status === NUMBER_POOL_SUCCESS && resp.number) {
    var force = false;
    if (resp.number !== window.zarPoolData.number) {
      warn(
        "number changed from " +
          window.zarPoolData.number +
          " to " +
          resp.number
      );
      window.zarPoolData.number = resp.number;
      force = true;
    }
    if (overlayElements) {
      overlayPhoneNumber({
        elems: overlayElements,
        number: resp.number,
        force
      });
    }
  } else {
    if (overlayElements) {
      revertOverlayNumbers({ elems: overlayElements });
    }
    if (poolIntervals[poolId]) {
      clearInterval(poolIntervals[poolId]);
      delete poolIntervals[poolId];
    }
  }

  if (initCallback) {
    resp.renew = true;
    initCallback(resp);
  }

  return resp;
}

function getPoolId(poolId) {
  if (isFunc(poolId)) return poolId();
  return poolId;
}

function initPoolDataLayerObserver(apiUrl) {
  if (window.zarPoolDLObserverDone) {
    return;
  }

  if (!poolActive()) {
    return;
  }

  var originalPush = window.zarPoolDataLayer.push;
  window.zarPoolDataLayer.push = function (...args) {
    var result = originalPush.apply(this, args);
    var context = drainPoolDataLayer();
    if (!context) {
      return result;
    }
    updateTrackingNumberContext({
      apiUrl,
      poolId: window.zarPoolData.pool_id,
      number: window.zarPoolData.number,
      context
    });
    return result;
  };

  // Do an initial drain in case data was added between contextCallback
  // and the observer being set up.
  var context = drainPoolDataLayer();
  if (context) {
    updateTrackingNumberContext({
      apiUrl,
      poolId: window.zarPoolData.pool_id,
      number: window.zarPoolData.number,
      context
    });
  }

  window.zarPoolDLObserverDone = true;
}

async function initTrackingPool({ poolData, poolConfig, apiUrl } = {}) {
  var msg;
  stopAllRenewals = false;

  if (
    !poolConfig ||
    !poolConfig.poolId ||
    !poolConfig.overlayQuerySelector ||
    !apiUrl
  ) {
    msg = "missing pool config: " + JSON.stringify(poolConfig);
    warn(msg);
    if (poolConfig.initCallback) {
      poolConfig.initCallback({ status: NUMBER_POOL_ERROR, msg });
    }
    return poolIntervals;
  }

  var poolId = getPoolId(poolConfig.poolId);
  if (!poolId) {
    msg = "no pool ID";
    warn(msg);
    if (poolConfig.initCallback) {
      poolConfig.initCallback({ status: NUMBER_POOL_ERROR, msg });
    }
    return poolIntervals;
  }

  if (!poolData) {
    var context = drainPoolDataLayer() || {};
    if (poolConfig.contextCallback) {
      context = poolConfig.contextCallback(context) || {};
    }

    try {
      poolData = await getPoolNumber({ poolId, apiUrl, number: null, context });
    } catch (e) {
      msg = "error getting number on init: " + JSON.stringify(e);
      warn(msg);
      if (poolConfig.initCallback) {
        poolConfig.initCallback({ status: NUMBER_POOL_ERROR, msg });
      }
      return poolIntervals;
    }
  }

  window.zarPoolData = poolData;

  if (poolActive()) {
    lastRenewalAttemptMs[poolId] = Date.now();

    try {
      initPoolDataLayerObserver(apiUrl);
    } catch (e) {
      warn("data layer error: " + JSON.stringify(e));
    }

    afterDOMContentLoaded(function () {
      var overlayElements = document.querySelectorAll(
        poolConfig.overlayQuerySelector
      );
      if (!overlayElements) {
        var msg = "No elems found for:" + poolConfig.overlayQuerySelector;
        warn(msg);
        if (poolConfig.initCallback) {
          poolConfig.initCallback({ status: NUMBER_POOL_ERROR, msg });
        }
        return;
      }

      overlayPhoneNumber({ elems: overlayElements, number: poolData.number });

      var renewalInterval =
        poolConfig.renewalInterval || NUMBER_POOL_RENEWAL_INTERVAL_MS;

      var interval = setInterval(function () {
        try {
          renewTrackingPool({
            overlayElements,
            apiUrl,
            contextCallback: poolConfig.contextCallback,
            initCallback: poolConfig.initCallback
          });
        } catch (e) {
          var msg = "error on interval: " + JSON.stringify(e);
          warn(msg);
        }
      }, renewalInterval);

      poolIntervals[poolData.pool_id] = interval;
      if (poolConfig.initCallback) {
        poolConfig.initCallback(poolData);
      }

      var forceRenewOnReturn = function (opts = {}) {
        try {
          if (!poolActive()) return;
          if (
            (opts.type === "vc" && document.visibilityState === "visible") ||
            (opts.type === "ps" && opts.persisted === true)
          ) {
            renewTrackingPool({
              overlayElements,
              apiUrl,
              contextCallback: poolConfig.contextCallback,
              initCallback: poolConfig.initCallback
            });
          }
        } catch (e) {
          warn("error on renew: " + JSON.stringify(e));
        }
      };

      document.addEventListener(
        "visibilitychange",
        function () {
          forceRenewOnReturn({ type: "vc" });
        },
        { passive: true }
      );

      window.addEventListener(
        "pageshow",
        function (e) {
          forceRenewOnReturn({ type: "ps", persisted: e && e.persisted });
        },
        { passive: true }
      );
    });
  }

  return poolIntervals;
}

function zar({ apiUrl, poolConfig }) {
  initIDs();

  return {
    name: "zar",
    config: { apiUrl, poolConfig },
    initialize: function ({ config }) {},
    loaded: function () {
      return true;
    },
    pageStart: function ({ payload, config, instance }) {
      payload.properties.zar = getStorage();
      payload.properties.referrer = document.referrer;
      payload.properties.is_bot = isBot();

      try {
        var pcfg = config.poolConfig;
        if (pcfg && pcfg.poolId) {
          payload.properties.pool_id = getPoolId(pcfg.poolId);
          var context = drainPoolDataLayer() || {};
          if (pcfg.contextCallback) {
            payload.properties.pool_context =
              pcfg.contextCallback(context) || {};
          }
        }
      } catch (e) {
        warn("error getting pool id: " + JSON.stringify(e));
      }
      return payload;
    },
    page: async function ({ payload, options, instance, config }) {
      dbg("page", payload, options, config);
      var tries = 0;
      var maxTries = 3;
      var res;
      while (tries < maxTries) {
        try {
          res = await httpPost({ url: `${config.apiUrl}/page`, data: payload });
          break;
        } catch (e) {
          tries++;
          if (tries >= maxTries) {
            warn("error posting page: " + JSON.stringify(e));
            throw e;
          }
          await new Promise((r) => setTimeout(r, 1000));
        }
      }
      if (res && res.pool_data) {
        initTrackingPool({
          poolData: res.pool_data,
          poolConfig: config.poolConfig,
          apiUrl: config.apiUrl
        });
      }
    },
    trackStart: function ({ payload, config, instance }) {
      payload.properties.zar = getStorage();
      payload.properties.url = window.location.href;
      payload.properties.referrer = document.referrer;
      return payload;
    },
    track: function ({ payload, options, instance, config }) {
      dbg("track", payload);
      httpPost({ url: `${config.apiUrl}/track`, data: payload, beacon: true });
    },
    methods: {
      apiUrl() {
        return apiUrl;
      },
      poolConfig() {
        return poolConfig;
      },
      initIDs() {
        return initIDs();
      },
      getIDs() {
        return getIDs();
      },
      getStorage() {
        return getStorage();
      },
      getVID() {
        return getID(VID_KEY);
      },
      isBot() {
        return isBot();
      },
      initTrackingPool({ poolConfig }) {
        var plugin = this.instance.plugins.zar;
        return initTrackingPool({
          poolData: null,
          poolConfig: Object.assign(plugin.poolConfig(), poolConfig || {}),
          apiUrl: plugin.apiUrl()
        });
      },
      updateTrackingNumberContext({ number, context }) {
        var plugin = this.instance.plugins.zar;
        var poolConfig = plugin.poolConfig();
        return updateTrackingNumberContext({
          apiUrl: this.instance.plugins.zar.apiUrl(),
          poolId: getPoolId(poolConfig.poolId),
          number,
          context
        });
      },
      getPoolIntervals() {
        return poolIntervals;
      },
      clearPoolInterval({ poolId }) {
        clearPoolInterval(poolId);
      },
      clearPoolIntervals() {
        clearPoolIntervals();
      },
      extractPhoneNumbers({ elems }) {
        var res = [];
        for (var i = 0; i < elems.length; i++) {
          var elemRes = extractPhoneNumber({ elem: elems[i] });
          res.push(elemRes);
        }
        return res;
      },
      overlayPhoneNumber({ overlayElements, number }) {
        overlayPhoneNumber({ elems: overlayElements, number });
      },
      revertOverlayNumbers({ overlayElements }) {
        revertOverlayNumbers({ elems: overlayElements });
      },
      getPoolStats({ key = null, with_contexts = false }) {
        return getPoolStats({
          apiUrl: this.instance.plugins.zar.apiUrl(),
          key,
          with_contexts
        });
      }
    }
  };
}

function init({
  app,
  ga4Config = null,
  facebookConfig = null,
  apiUrl = null,
  poolConfig = null
}) {
  if (!apiUrl) {
    apiUrl = getDefaultApiUrl();
  }

  var plugins = [zar({ apiUrl, poolConfig })];
  if (ga4Config) {
    plugins.push(googleAnalytics4(ga4Config));
  }
  if (facebookConfig) {
    plugins.push(facebook(facebookConfig));
  }

  return Analytics({ app, plugins });
}

// Internal test helpers export
export const __test__ = {
  extractPhoneNumber,
  overlayPhoneNumber,
  revertOverlayNumbers,
  drainPoolDataLayer,
  getPoolId
};

export { init, zar, Analytics };
