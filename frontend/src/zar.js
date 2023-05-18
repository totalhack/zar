import { Analytics } from 'analytics';
import { facebook } from './facebook';
import { googleAnalytics4 } from './googleAnalytics4';
import {
  dbg,
  getSessionStorage,
  setSessionStorage,
  removeSessionStorage,
  hasAdBlock,
  isBot,
  httpGet,
  httpPost,
  warning,
  afterDOMContentLoaded,
  isFunc
} from './utils';

var VID_KEY = '__zar_vid';
var NUMBER_POOL_SUCCESS = 'success';
var NUMBER_POOL_ERROR = 'error';
var NUMBER_POOL_RENEWAL_TIME_MS = 30 * 1000;
var getNumberFailureCount = 0
var MAX_GET_NUMBER_FAILURES = 3
var poolIntervals = {}

// Tracks original phone numbers that have been replaced so
// we can revert if necessary.
var numberOverlayMap = new Map();

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
    dbg('new ID for', key, '-', id);
  } else {
    id = idObj.id;
    origReferrer = idObj.origReferrer;
  }

  var result = { id, t: Date.now(), origReferrer, isNew };
  setter(key, result);
  return result;
}

function initIDs() {
  var vidResult = initId(VID_KEY, generateVisitId, getSessionStorage, setSessionStorage);
  return { vid: vidResult };
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
    vid: getIDObj(VID_KEY)
  };
}

function getIDs() {
  return {
    vid: getID(VID_KEY)
  };
}

function removeID(key) {
  removeSessionStorage(key);
}

function removeIDs() {
  removeID(VID_KEY);
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
      dbg("element already in overlay map:", elems[i]);
      continue;
    }

    var elemNum = extractPhoneNumber({ elem: elems[i] });

    if (!origNum) {
      origNum = elemNum;
    } else if ((elemNum.number && origNum.number) && (origNum.number !== elemNum.number)) {
      warning('overlaying multiple numbers with a single number', origNum.number, elemNum.number);
    }

    dbg("overlaying", overlayNum, "on", elems[i]);

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
      elems[i].innerHTML = origHTML;
      if (origElemData.href) {
        elems[i].href = origElemData.href;
      }
      numberOverlayMap.delete(elems[i]);
    } else {
      dbg("element not in map:", elems[i]);
    }
  }
}

function clearPoolInterval(poolId) {
  clearInterval(poolIntervals[poolId]);
  delete poolIntervals[poolId]
}

function clearPoolIntervals() {
  for (var poolId in poolIntervals) {
    clearPoolInterval(poolId)
  }
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

async function renewTrackingPool({
  poolId,
  number,
  overlayElements,
  apiUrl = getDefaultApiUrl(),
  contextCallback = null
} = {}) {
  var context = {};
  if (contextCallback) {
    context = contextCallback() || {};
  }

  try {
    var resp = await getPoolNumber({ poolId, apiUrl, number, context });
  } catch (e) {
    // We don't clear the pool interval in here -- assumes the service is
    // down or the error was intermitten, allows retrying
    var msg = "error getting number: " + JSON.stringify(e);
    warning(msg);
    getNumberFailureCount++;
    if (getNumberFailureCount >= MAX_GET_NUMBER_FAILURES) {
      warning("max failures, stopping pool")
      clearPoolIntervals();
      if (overlayElements) {
        revertOverlayNumbers({ elems: overlayElements });
      }
    }
    return { status: NUMBER_POOL_ERROR, msg }
  }

  if (resp.status === NUMBER_POOL_SUCCESS && resp.number) {
    if (overlayElements) {
      overlayPhoneNumber({ elems: overlayElements, number: resp.number });
    }
  } else {
    if (overlayElements) {
      revertOverlayNumbers({ elems: overlayElements });
    }
    if (poolIntervals[poolId]) {
      clearInterval(poolIntervals[poolId])
      delete poolIntervals[poolId]
    }
  }

  return resp;
}

function getPoolId(poolId) {
  if (isFunc(poolId)) return poolId();
  return poolId;
}

async function initTrackingPool({ poolData, poolConfig, apiUrl } = {}) {
  var msg

  if (!poolConfig || !poolConfig.poolId || !poolConfig.overlayQuerySelector || !apiUrl) {
    msg = 'missing pool config: ' + JSON.stringify(poolConfig);
    warning(msg);
    if (poolConfig.initCallback) {
      poolConfig.initCallback({ status: NUMBER_POOL_ERROR, msg });
    }
    return poolIntervals;
  }

  var context = {};
  if (poolConfig.contextCallback) {
    context = poolConfig.contextCallback() || {};
  }

  var poolId = getPoolId(poolConfig.poolId)
  if (!poolId) {
    msg = 'no pool ID';
    warning(msg);
    if (poolConfig.initCallback) {
      poolConfig.initCallback({ status: NUMBER_POOL_ERROR, msg });
    }
    return poolIntervals;
  }

  if (!poolData) {
    try {
      poolData = await getPoolNumber({ poolId, apiUrl, number: null, context });
    } catch (e) {
      msg = "error getting number on init: " + JSON.stringify(e);
      warning(msg)
      if (poolConfig.initCallback) {
        poolConfig.initCallback({ status: NUMBER_POOL_ERROR, msg });
      }
      return poolIntervals;
    }
  }

  if (poolData && poolData.status === NUMBER_POOL_SUCCESS && poolData.number) {
    afterDOMContentLoaded(function () {
      var overlayElements = document.querySelectorAll(poolConfig.overlayQuerySelector);
      if (!overlayElements) {
        var msg = 'No elems found for:' + poolConfig.overlayQuerySelector
        warning(msg)
        if (poolConfig.initCallback) {
          poolConfig.initCallback({ status: NUMBER_POOL_ERROR, msg });
        }
        return
      }

      overlayPhoneNumber({ elems: overlayElements, number: poolData.number });

      var interval = setInterval(
        function () {
          try {
            renewTrackingPool({
              poolId: poolData.pool_id,
              number: poolData.number,
              overlayElements,
              apiUrl,
              contextCallback: poolConfig.contextCallback
            });
          } catch (e) {
            var msg = "error on interval: " + JSON.stringify(e);
            warning(msg);
          }
        },
        poolConfig.renewalInterval || NUMBER_POOL_RENEWAL_TIME_MS
      );

      poolIntervals[poolData.pool_id] = interval;
      if (poolConfig.initCallback) {
        poolConfig.initCallback(poolData);
      }
    });
  }

  return poolIntervals;
}

function zar({ apiUrl, poolConfig }) {
  initIDs();

  return {
    name: 'zar',
    config: { apiUrl, poolConfig },
    initialize: function ({ config }) { },
    loaded: function () { return true; },
    pageStart: function ({ payload, config, instance }) {
      payload.properties.zar = getStorage();
      payload.properties.referrer = document.referrer;
      payload.properties.is_bot = isBot();
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

      try {
        var pcfg = config.poolConfig;
        if (pcfg && pcfg.poolId) {
          payload.properties.pool_id = getPoolId(pcfg.poolId);
          if (pcfg.contextCallback) {
            payload.properties.pool_context = pcfg.contextCallback() || {};
          }
        }
      } catch (e) {
        warning("error getting pool id: " + JSON.stringify(e));
      }
      return payload;
    },
    page: async function ({ payload, options, instance, config }) {
      dbg('page', payload, options, config);
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
            warning("error posting page: " + JSON.stringify(e));
            throw e;
          }
          await new Promise(r => setTimeout(r, 1000));
        }
      }
      if (res && res.pool_data) {
        initTrackingPool({ poolData: res.pool_data, poolConfig: config.poolConfig, apiUrl: config.apiUrl })
      }
    },
    trackStart: function ({ payload, config, instance }) {
      payload.properties.zar = getStorage();
      payload.properties.url = window.location.href;
      payload.properties.referrer = document.referrer;
      return payload;
    },
    track: function ({ payload, options, instance, config }) {
      dbg('track', payload);
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
      hasAdBlock() {
        return hasAdBlock();
      },
      isBot() {
        return isBot();
      },
      initTrackingPool({ poolConfig }) {
        var plugin = this.instance.plugins.zar
        return initTrackingPool({
          poolData: null,
          poolConfig: Object.assign(plugin.poolConfig(), poolConfig || {}),
          apiUrl: plugin.apiUrl()
        });
      },
      getPoolIntervals() {
        return poolIntervals
      },
      clearPoolInterval({ poolId }) {
        clearPoolInterval(poolId)
      },
      clearPoolIntervals() {
        clearPoolIntervals()
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
        return getPoolStats({ apiUrl: this.instance.plugins.zar.apiUrl(), key, with_contexts });
      }
    }
  };
}

function init({ app, ga4Config = null, facebookConfig = null, apiUrl = null, poolConfig = null }) {
  // Opinionated init of Analytics
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

export { init, zar, Analytics };
