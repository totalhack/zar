import { Analytics } from 'analytics';
import { getItem, setItem, removeItem } from '@analytics/storage-utils';
import { getSessionItem, setSessionItem, removeSessionItem } from '@analytics/session-storage-utils';
import googleAnalytics from '@analytics/google-analytics';
import googleTagManager from '@analytics/google-tag-manager';

import { uuid, hasAdBlock, paramsParse, httpGet, httpPost } from './utils';

var CID_KEY = '__zar_cid';
var SID_KEY = '__zar_sid';
var VID_KEY = '__zar_vid';
var NUMBER_POOL_KEY = '__zar_pool';
var NUMBER_POOL_SUCCESS = 'success';
var NUMBER_POOL_ERROR = 'error';
var NUMBER_POOL_RENEWAL_TIME_MS = 30 * 1000;
var POOL_DEFAULT_URL_FLAG = 'pl';
var DAY_TTL = 1000 * 60 * 60 * 24; // In milliseconds
// Pool session data is in localStorage but we don't want the pool flag to
// stay set forever, even though the backend controls max renewal time.
var POOL_STORAGE_TTL = DAY_TTL * 7;

// Tracks original phone numbers that have been replaced so
// we can revert if necessary.
// eslint-disable-next-line
var numberOverlayMap = new Map();

function generateClientId() {
  return uuid();
}

function generateSessionId() {
  return uuid();
}

function generateVisitId() {
  return Date.now().toString(36) + '.' + Math.random().toString(36).substring(2);
}

function setSessionStorage(key, obj) {
  setSessionItem(key, JSON.stringify(obj));
}

function getSessionStorage(key) {
  var val = getSessionItem(key);
  if (typeof val === 'undefined') {
    return null;
  }
  try {
    return JSON.parse(val);
  } catch (e) {
    var msg = "getSessionStorage: JSON parse error for val: " + JSON.stringify(val) + " error: " + JSON.stringify(e);
    if (window.Rollbar) {
      window.Rollbar.warning(msg);
    }
    console.warn(msg);
    return null;
  }
}

function removeSessionStorage(key) {
  removeSessionItem(key);
}

function initId(key, generator, getter, setter, debug = false) {
  var id;
  var isNew = false;
  var origReferrer = null;
  var idObj = getter(key);

  if (!idObj || !idObj.id) {
    id = generator();
    origReferrer = document.referrer;
    isNew = true;
    if (debug) {
      console.log('Generated ID for', key, '-', id);
    }
  } else {
    id = idObj.id;
    origReferrer = idObj.origReferrer;
  }

  var result = { id, t: Date.now(), origReferrer, isNew };
  setter(key, result);
  return result;
}

function initIds({ debug = false } = {}) {
  var vidResult = initId(VID_KEY, generateVisitId, getSessionStorage, setSessionStorage, debug);
  var sidResult = initId(SID_KEY, generateSessionId, getSessionStorage, setSessionStorage, debug);
  var cidResult = initId(CID_KEY, generateClientId, getSessionStorage, setSessionStorage, debug);

  // We store values globally in case the storage is reset mid-session
  window[CID_KEY] = cidResult;
  window[SID_KEY] = sidResult;
  window[VID_KEY] = vidResult;

  return { cid: cidResult.id, sid: sidResult.id, vid: vidResult.id };
}

function getDefaultApiUrl() {
  return window.location.host + '/api/v1';
}

function getIDObj(key) {
  var obj = getSessionStorage(key);
  if ((!obj) && window[key]) {
    console.warn("got " + key + " from global var");
    setSessionStorage(key, window[key]);
    return window[key];
  }
  return obj;
}

function getID(key) {
  var obj = getIDObj(key);
  return obj ? obj.id : null;
}

function getStorage() {
  return {
    cid: getIDObj(CID_KEY),
    sid: getIDObj(SID_KEY),
    vid: getIDObj(VID_KEY)
  };
}

function getIds() {
  return {
    cid: getID(CID_KEY),
    sid: getID(SID_KEY),
    vid: getID(VID_KEY)
  };
}

function updateID(key, val) {
  var obj = getIDObj(key);
  if (!obj) {
    console.warn("could not update " + key);
    return;
  }
  obj.id = val;
  setSessionStorage(key, obj);
  window[key] = obj;
}

function removeID(key) {
  removeSessionStorage(key);
  if (window[key]) {
    delete window[key];
  }
}

function removeIds() {
  removeID(VID_KEY);
  removeID(SID_KEY);
  removeID(CID_KEY);
}

async function getPoolNumber({ poolId, apiUrl, number = null, context = null }) {
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

async function getPoolStats({ apiUrl, key = null, with_contexts = false }) {
  var params = {
    key,
    with_contexts
  };
  var resp = await httpGet({ url: `${apiUrl}/number_pool_stats`, params: params });
  return resp;
}

function extractPhoneNumber({ elem }) {
  // NOTE: only tested for US numbers!
  var numberText = null;
  var number = null;
  var href = null;
  var regex = new RegExp("\\+?\\(?\\d*\\)? ?\\(?\\d+\\)?\\d*([\\s./-]?\\d{2,})+", "g");

  if (elem.href && elem.href.startsWith("tel:")) {
    href = elem.href;
  }
  var text = elem.innerText;
  var html = elem.innerHTML;
  var match = regex.exec(text);
  if (match) {
    numberText = match[0].trim();
    number = numberText.replace("+", "").replace(/-/g, "").replace(/ /g, "").replace("(", "").replace(")", "").replace(/^1/, '');
  }
  return { text, html, numberText, href, number };
}

function overlayPhoneNumber({ elems, number, debug = false }) {
  var origNum;
  var overlayNum = number;
  if (!number.startsWith("+1")) {
    overlayNum = "+1" + number; // NOTE: expects 10-digit US numbers
  }

  for (var i = 0; i < elems.length; i++) {
    if (numberOverlayMap.has(elems[i])) {
      if (debug) {
        console.log("pool: skipping element already in overlay map:", elems[i]);
      }
      continue;
    }

    var elemNum = extractPhoneNumber({ elem: elems[i] });

    if (!origNum) {
      origNum = elemNum;
    } else if ((elemNum.number && origNum.number) && (origNum.number !== elemNum.number)) {
      console.warn('pool: overlaying multiple phone numbers with a single number!', origNum.number, elemNum.number);
    }

    if (debug) {
      console.log("pool: overlaying number", overlayNum, "on", elems[i]);
    }

    // Store the original values
    numberOverlayMap.set(elems[i], elemNum);

    if (elemNum.href) {
      elems[i].href = "tel:" + overlayNum;
    }

    if (elemNum.numberText) {
      // If there is a phone number present in the text...
      elems[i].innerHTML = "";
      if (elemNum.text) {
        var overlay = overlayNum;
        if (elemNum.numberText.indexOf("-") > -1) {
          overlay = overlayNum.slice(2, 5) + "-" + overlayNum.slice(5, 8) + "-" + overlayNum.slice(8, 12);
        }
        var numberText = elemNum.text.replace(elemNum.numberText, overlay);
        elems[i].appendChild(document.createTextNode(numberText));
      } else {
        elems[i].appendChild(document.createTextNode(overlayNum));
      }
    } else {
      if (debug) {
        console.log("pool: no number text found on", elems[i]);
      }
    }
  }
}

function revertOverlayNumbers({ elems, debug = false }) {
  for (var i = 0; i < elems.length; i++) {
    if (numberOverlayMap.has(elems[i])) {
      var currentHTML = elems[i].innerHTML;
      var origElemData = numberOverlayMap.get(elems[i]);
      if (debug) {
        console.log("orig:", origElemData);
      }
      var origHTML = origElemData.html;
      if (debug) {
        console.log("pool: reverting", currentHTML, "to", origHTML);
      }
      elems[i].innerHTML = origHTML;
      if (origElemData.href) {
        elems[i].href = origElemData.href;
      }
      numberOverlayMap.delete(elems[i]);
    } else {
      if (debug) {
        console.log("pool: element not in map:", elems[i]);
      }
    }
  }
}

function removePoolSession({ overlayElements }) {
  removeItem(NUMBER_POOL_KEY);
  if (window[NUMBER_POOL_KEY]) {
    delete window[NUMBER_POOL_KEY];
  }
  revertOverlayNumbers({ elems: overlayElements });
}

function clearPoolIntervals(poolData) {
  if (!poolData || !poolData.poolNumbers) {
    return;
  }
  for (var poolId in poolData.poolNumbers) {
    clearInterval(poolData.poolNumbers[poolId].interval);
  }
}

function poolSessionExpired(obj) {
  if (obj && obj.t && (obj.t + POOL_STORAGE_TTL < Date.now())) {
    return true;
  }
  return false;
}

function getPoolSession({ overlayElements }) {
  var data = getItem(NUMBER_POOL_KEY);
  if ((!data) && window[NUMBER_POOL_KEY]) {
    if (poolSessionExpired(window[NUMBER_POOL_KEY])) {
      clearPoolIntervals(window[NUMBER_POOL_KEY]);
      removePoolSession({ overlayElements });
      return null;
    }
    console.warn("got number pool session from global var");
    setItem(NUMBER_POOL_KEY, window[NUMBER_POOL_KEY]);
    return window[NUMBER_POOL_KEY];
  }
  if (poolSessionExpired(data)) {
    clearPoolIntervals(data);
    removePoolSession({ overlayElements });
    return null;
  }
  return data;
}

async function initTrackingPool({
  poolId,
  overlayElements,
  apiUrl = getDefaultApiUrl(),
  urlParam = POOL_DEFAULT_URL_FLAG,
  renew = true,
  renewalInterval = NUMBER_POOL_RENEWAL_TIME_MS,
  callback = null,
  debug = false
} = {}) {
  var poolEnabled = false;
  var seshData = getPoolSession({ overlayElements });

  if (seshData && seshData.poolEnabled) {
    poolEnabled = true;
  } else {
    var params = paramsParse(window.location.search);
    if (urlParam in params && params[urlParam] === "1") {
      poolEnabled = true;
    }
  }

  if (!poolEnabled) {
    if (debug) {
      console.log('pool: not enabled');
    }
    if (callback) {
      callback(null);
    }
    return null;
  }

  var seshNumber = null;
  var seshInterval = null;

  if (seshData && seshData.poolNumbers && seshData.poolNumbers[poolId]) {
    var poolResult = seshData.poolNumbers[poolId];
    seshInterval = poolResult.interval;
    if (poolResult.status !== NUMBER_POOL_SUCCESS) {
      // Prevents previously failed sessions from trying again
      if (debug) {
        console.log('pool: returning cached unsuccessful pool result: ' + JSON.stringify(poolResult));
      }
      if (callback) {
        callback(poolResult);
      }
      return poolResult;
    }
    if (poolResult.number) {
      seshNumber = poolResult.number;
      if (debug) {
        console.log('pool: found session number ' + seshNumber);
      }
    }
  }

  var resp = {};
  try {
    resp = await getPoolNumber({ poolId, apiUrl, number: seshNumber, context: {} });
  } catch (e) {
    // We catch and return errors but don't cache the result. It is assumed
    // this only happens when the number service is down. If this wasn't the first
    // call with an error, this would allow the retries to just start working again
    // once the service is back up. If it is the first call and the interval has never
    // been set, the service wouldn't retry unless initTrackingPool was called again.
    var msg = "pool: error getting number: " + JSON.stringify(e);
    if (window.Rollbar) {
      window.Rollbar.warning(msg);
    }
    console.warn(msg);
    var errorRes = { status: NUMBER_POOL_ERROR, msg: e.message, interval: seshInterval };
    if (callback) {
      callback(errorRes);
    }
    return errorRes;
  }

  if (resp.status === NUMBER_POOL_SUCCESS && resp.number) {
    if (overlayElements) {
      overlayPhoneNumber({ elems: overlayElements, number: resp.number, debug });
    }

    if (renew) {
      if (debug) {
        console.log("pool: setting up renewal");
      }
      resp.interval = setInterval(
        function () { initTrackingPool({ poolId, overlayElements, apiUrl, urlParam, renew: false, debug }); },
        renewalInterval
      );
    }
  } else {
    if (overlayElements) {
      revertOverlayNumbers({ elems: overlayElements, debug });
    }
    if (seshInterval) {
      clearInterval(seshInterval);
    }
    resp.interval = null;
  }

  if (seshData) {
    if (seshData.poolNumbers[poolId]) {
      Object.assign(seshData.poolNumbers[poolId], resp);
    } else {
      seshData.poolNumbers[poolId] = resp;
    }
    if (renew) {
      // Assume its the initial call, reset pool session expiration
      seshData.t = Date.now();
    }
  } else {
    var poolNumbers = {};
    poolNumbers[poolId] = resp;
    seshData = {
      poolEnabled: true,
      poolNumbers,
      t: Date.now()
    };
  }

  window[NUMBER_POOL_KEY] = seshData;
  setItem(NUMBER_POOL_KEY, seshData);
  if (debug) {
    console.log('pool: saved session data ' + JSON.stringify(seshData));
  }
  if (callback) {
    callback(resp);
  }
  return resp;
}

function zar({ apiUrl }) {
  return {
    name: 'zar',
    config: {
      apiUrl: apiUrl,
    },
    initialize: function ({ config }) { },
    loaded: function () { return true; },
    pageStart: function ({ payload, config, instance }) {
      payload.properties.zar = getStorage();
      // Remove redundant values since url has all of this
      if ("hash" in payload.properties) {
        delete payload.properties["hash"];
      }
      if ("path" in payload.properties) {
        delete payload.properties["path"];
      }
      if ("search" in payload.properties) {
        delete payload.properties["search"];
      }
      return payload;
    },
    trackStart: function ({ payload, config, instance }) {
      payload.properties.zar = getStorage();
      return payload;
    },
    page: async function ({ payload, options, instance, config }) {
      if (instance.getState('context').debug) {
        console.log('page', payload, options, config);
      }
      var result = await httpPost({ url: `${config.apiUrl}/page`, data: payload });
      // We overwrite the session / client ID in case server-side values are different
      if (result.sid) {
        updateID(SID_KEY, result.sid);
      }
      if (result.cid) {
        updateID(CID_KEY, result.cid);
        instance.setAnonymousId(result.cid);
      }
    },
    track: function ({ payload, options, instance, config }) {
      if (instance.getState('context').debug) {
        console.log('track', payload);
      }
      httpPost({ url: `${config.apiUrl}/track`, data: payload });
    },
    reset: function ({ instance }) {
      removeIds();
    },
    bootstrap: function ({ payload, config, instance }) {
      var result = initIds({ debug: instance.getState('context').debug });
      instance.setAnonymousId(result.cid); // Override analytics' anonymous ID with client ID
    },
    methods: {
      apiUrl() {
        return apiUrl;
      },
      initIds() {
        var result = initIds({ debug: this.instance.getState('context').debug });
        this.instance.setAnonymousId(result.cid); // Override analytics' anonymous ID with client ID
        return result;
      },
      getIds() {
        return getIds();
      },
      getStorage() {
        return getStorage();
      },
      getCID() {
        return getID(CID_KEY);
      },
      getSID() {
        return getID(SID_KEY);
      },
      getVID() {
        return getID(VID_KEY);
      },
      hasAdBlock() {
        return hasAdBlock();
      },
      initTrackingPool({ poolId, overlayElements, urlParam = POOL_DEFAULT_URL_FLAG, renew = true, renewalInterval = NUMBER_POOL_RENEWAL_TIME_MS, callback = null }) {
        return initTrackingPool({
          poolId,
          overlayElements,
          apiUrl: this.instance.plugins.zar.apiUrl(),
          urlParam,
          renew,
          renewalInterval,
          callback,
          debug: this.instance.getState('context').debug
        });
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
      removePoolSession({ overlayElements }) {
        removePoolSession({ overlayElements });
      },
      getPoolStats({ key = null, with_contexts = false }) {
        return getPoolStats({ apiUrl: this.instance.plugins.zar.apiUrl(), key, with_contexts });
      }
    }
  };
}

function init({ app, gtmConfig, gaConfig, apiUrl = null, debug = false }) {
  // Opinionated init of Analytics - Loads GA and GTM separately
  if (!apiUrl) {
    apiUrl = getDefaultApiUrl();
  }
  return Analytics({
    app,
    debug,
    plugins: [
      zar({ apiUrl }),
      googleAnalytics(gaConfig),
      googleTagManager(gtmConfig)
    ]
  });
}

export { init, zar, Analytics };


