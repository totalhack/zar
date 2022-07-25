import { Analytics } from 'analytics';
import { getItem, setItem, removeItem, ALL } from '@analytics/storage-utils';
import googleTagManager from '@analytics/google-tag-manager';

import { googleAnalytics4 } from './googleAnalytics4';
import {
  dbg,
  getSessionStorage,
  setSessionStorage,
  removeSessionStorage,
  uuid,
  hasAdBlock,
  urlParams,
  httpGet,
  httpPost,
  rbWarning
} from './utils';

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

function initId(key, generator, getter, setter) {
  var id;
  var isNew = false;
  var origReferrer = null;
  var idObj = getter(key);

  if (!idObj || !idObj.id) {
    id = generator();
    origReferrer = document.referrer;
    isNew = true;
    dbg('Generated ID for', key, '-', id);
  } else {
    id = idObj.id;
    origReferrer = idObj.origReferrer;
  }

  var result = { id, t: Date.now(), origReferrer, isNew };
  setter(key, result);
  return result;
}

function initIds() {
  var vidResult = initId(VID_KEY, generateVisitId, getSessionStorage, setSessionStorage);
  var sidResult = initId(SID_KEY, generateSessionId, getSessionStorage, setSessionStorage);
  var cidResult = initId(CID_KEY, generateClientId, getSessionStorage, setSessionStorage);
  return { cid: cidResult.id, sid: sidResult.id, vid: vidResult.id };
}

function getDefaultApiUrl() {
  return window.location.host + '/api/v1';
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
}

function removeID(key) {
  removeSessionStorage(key);
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

function overlayPhoneNumber({ elems, number }) {
  var origNum;
  var overlayNum = number;
  if (!number.startsWith("+1")) {
    overlayNum = "+1" + number; // NOTE: expects 10-digit US numbers
  }

  for (var i = 0; i < elems.length; i++) {
    if (numberOverlayMap.has(elems[i])) {
      dbg("pool: skipping element already in overlay map:", elems[i]);
      continue;
    }

    var elemNum = extractPhoneNumber({ elem: elems[i] });

    if (!origNum) {
      origNum = elemNum;
    } else if ((elemNum.number && origNum.number) && (origNum.number !== elemNum.number)) {
      console.warn('pool: overlaying multiple phone numbers with a single number!', origNum.number, elemNum.number);
    }

    dbg("pool: overlaying number", overlayNum, "on", elems[i]);

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
        if (elemNum.html.indexOf('<img') > -1) {
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
      dbg("pool: no number text found on", elems[i]);
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
      dbg("pool: reverting", currentHTML, "to", origHTML);
      elems[i].innerHTML = origHTML;
      if (origElemData.href) {
        elems[i].href = origElemData.href;
      }
      numberOverlayMap.delete(elems[i]);
    } else {
      dbg("pool: element not in map:", elems[i]);
    }
  }
}

function removePoolSession({ overlayElements }) {
  removeItem(NUMBER_POOL_KEY, ALL);
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

function getPoolSession() {
  return getItem(NUMBER_POOL_KEY);
}

async function initTrackingPool({
  poolId,
  overlayElements,
  apiUrl = getDefaultApiUrl(),
  urlParam = POOL_DEFAULT_URL_FLAG,
  renew = true,
  renewalInterval = NUMBER_POOL_RENEWAL_TIME_MS,
  callback = null
} = {}) {
  var poolEnabled = false;
  var seshData = getPoolSession();
  var expired = poolSessionExpired(seshData);

  if (!expired) {
    if (seshData && seshData.poolEnabled) {
      poolEnabled = true;
    } else {
      if (urlParams.get(urlParam) === "1") {
        poolEnabled = true;
      }
    }
  } else {
    clearPoolIntervals(seshData);
    removePoolSession({ overlayElements });
  }

  if (!poolEnabled) {
    dbg('pool: not enabled');
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
      dbg('pool: returning cached unsuccessful pool result: ' + JSON.stringify(poolResult));
      if (callback) {
        callback(poolResult);
      }
      return poolResult;
    }
    if (poolResult.number) {
      seshNumber = poolResult.number;
      dbg('pool: found session number ' + seshNumber);
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
    rbWarning(msg);
    console.warn(msg);
    var errorRes = { status: NUMBER_POOL_ERROR, msg: e.message, interval: seshInterval };
    if (callback) {
      callback(errorRes);
    }
    return errorRes;
  }

  if (resp.status === NUMBER_POOL_SUCCESS && resp.number) {
    if (overlayElements) {
      overlayPhoneNumber({ elems: overlayElements, number: resp.number });
    }

    if (renew) {
      dbg("pool: setting up renewal");
      resp.interval = setInterval(
        function () {
          try {
            initTrackingPool({ poolId, overlayElements, apiUrl, urlParam, renew: false });
          } catch (e) {
            var msg = "pool: error on interval call: " + JSON.stringify(e);
            rbWarning(msg)
            console.warn(msg);
          }
        },
        renewalInterval
      );
    }
  } else {
    if (overlayElements) {
      revertOverlayNumbers({ elems: overlayElements });
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

  setItem(NUMBER_POOL_KEY, seshData, ALL);
  dbg('pool: saved session data ' + JSON.stringify(seshData));
  if (callback) {
    callback(resp);
  }
  return resp;
}

function zar({ apiUrl }) {
  return {
    name: 'zar',
    config: {
      apiUrl: apiUrl
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
      payload.properties.url = window.location.href;
      return payload;
    },
    page: async function ({ payload, options, instance, config }) {
      dbg('page', payload, options, config);
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
      dbg('track', payload);
      httpPost({ url: `${config.apiUrl}/track`, data: payload, beacon: true });
    },
    reset: function ({ instance }) {
      removeIds();
    },
    bootstrap: function ({ payload, config, instance }) {
      var result = initIds();
      instance.setAnonymousId(result.cid); // Override analytics' anonymous ID with client ID
    },
    methods: {
      apiUrl() {
        return apiUrl;
      },
      initIds() {
        var result = initIds();
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
          callback
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

function init({ app, gtmConfig = null, ga4Config = null, apiUrl = null }) {
  // Opinionated init of Analytics
  if (!apiUrl) {
    apiUrl = getDefaultApiUrl();
  }

  var plugins = [zar({ apiUrl })];
  if (ga4Config) {
    plugins.push(googleAnalytics4(ga4Config));
  }
  if (gtmConfig) {
    plugins.push(googleTagManager(gtmConfig));
  }

  return Analytics({ app, plugins });
}

export { init, zar, Analytics };
