import { Analytics } from 'analytics';
import { getItem, setItem, removeItem } from '@analytics/storage-utils';
import googleAnalytics from '@analytics/google-analytics';
import googleTagManager from '@analytics/google-tag-manager';

import { uuid, hasAdBlock, paramsParse, httpGet, httpPost } from './utils';

const CID_KEY = '__zar_cid';
const SID_KEY = '__zar_sid';
const VID_KEY = '__zar_vid';
const NUMBER_POOL_KEY = '__zar_pool';
const NUMBER_POOL_SUCCESS = 'success';
const NUMBER_POOL_ERROR = 'error';
const NUMBER_POOL_RENEWAL_TIME_MS = 30 * 1000;
const POOL_DEFAULT_URL_FLAG = 'pl';
const DAY_TTL = 1000 * 60 * 60 * 24; // In milliseconds
const CID_TTL = DAY_TTL * 365 * 3; // N years, ~like GA
const SID_TTL = DAY_TTL * 2; // N days, ~like GA
// Pool session data is in localStorage but we don't want the pool flag to
// stay set forever, even though the backend controls max renewal time.
const POOL_STORAGE_TTL = DAY_TTL * 7;

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
  sessionStorage.setItem(key, JSON.stringify(obj));
}

function getSessionStorage(key) {
  return JSON.parse(sessionStorage.getItem(key));
}

function removeSessionStorage(key) {
  sessionStorage.removeItem(key);
}

function expireByTTL(idObj, ttl, debug) {
  const diff = Date.now() - idObj.t;
  if (diff >= ttl) {
    if (debug) {
      console.log('Expired after ', diff / 1000.0, 'seconds');
    }
    return true;
  }
  return false;
}

function expireSessionId(idObj, newVisit, debug) {
  if (!newVisit) {
    return false;
  }
  return expireByTTL(idObj, SID_TTL, debug);
}

function initId(key, expirationCallback, generator, getter, setter, newVisit, debug = false) {
  var id;
  var isNew = false;
  var visits;
  var origReferrer = null;
  const idObj = getter(key);

  if (!idObj || !idObj.id || (expirationCallback && expirationCallback(idObj, newVisit, debug))) {
    id = generator();
    origReferrer = document.referrer;
    visits = 1;
    isNew = true;
    if (debug) {
      console.log('Generated ID for', key, '-', id);
    }
  } else {
    id = idObj.id;
    origReferrer = idObj.origReferrer;
    visits = (idObj.visits || 1) + (newVisit ? 1 : 0);
  }

  const result = { id, t: Date.now(), origReferrer, isNew, visits };
  setter(key, result);
  return result;
}

function initIds({
  clientIdExpired = (idObj, debug) => { return expireByTTL(idObj, CID_TTL, debug); },
  sessionIdExpired = expireSessionId,
  visitIdExpired = null,
  debug = false
} = {}) {
  const vidResult = initId(VID_KEY, visitIdExpired, generateVisitId, getSessionStorage, setSessionStorage, null, debug);
  const cidResult = initId(CID_KEY, clientIdExpired, generateClientId, getItem, setItem, vidResult.isNew, debug);

  // SID logic is a bit more complicated, as we rely on both sessionStorage
  // and analytics' storage (usually localStorage) to track the session.
  // The goal is to reuse non-expired SIDs when possible across visits but
  // to also prevent an SID from being overwritten in an old tab due to
  // an expiration in a new visit.

  var sidResult;
  var sidObj = getSIDObj(); // Checks sessionStorage
  var sessionSid = sidObj && sidObj.id ? sidObj.id : null;
  if (vidResult.isNew && sessionSid) {
    console.warn('Found old sessionStorage SID with new VID');
  }

  if (!sessionSid) {
    sidResult = initId(SID_KEY, sessionIdExpired, generateSessionId, getItem, setItem, vidResult.isNew, debug);
    if (debug && !sidResult.isNew) {
      console.log('Using existing SID from analytics storage');
    }
    sessionSid = sidResult.id;
  } else {
    // SID is in sessionStorage already. There should be one in analytics' storage too.
    sidResult = sidObj;
    sidResult.visits = sidResult.visits + (vidResult.isNew ? 1 : 0);
    sidResult.isNew = false;
    const analyticsSIDObj = getSIDObj({ getter: getItem });
    if (!analyticsSIDObj || !analyticsSIDObj.id) {
      console.warn('SID missing in analytics storage, setting from sessionStorage value');
      setItem(SID_KEY, { id: sidResult.id, t: Date.now(), origReferrer: sidResult.origReferrer, isNew: sidResult.isNew, visits: sidResult.visits });
    }
  }
  // Set/reset sessionStorage SID either way
  setSessionStorage(SID_KEY, { id: sessionSid, t: Date.now(), origReferrer: sidResult.origReferrer, isNew: sidResult.isNew, visits: sidResult.visits });

  // We store values globally in case the storage is reset mid-session
  window[CID_KEY] = cidResult;
  window[SID_KEY] = sidResult;
  window[VID_KEY] = vidResult;
  return { cid: cidResult.id, sid: sidResult.id, vid: vidResult.id };
}

function getDefaultApiUrl() {
  return window.location.origin + '/api/v1';
}

async function getPoolNumber({ poolId, apiUrl, number = null, context = null }) {
  const payload = {
    pool_id: poolId,
    number: number,
    context: context,
    properties: {
      zar: getStorage()
    }
  };
  const resp = await httpPost({ url: `${apiUrl}/number_pool`, data: payload });
  return resp;
}

async function getPoolStats({ apiUrl, key = null, with_contexts = false }) {
  const params = {
    key,
    with_contexts
  };
  const resp = await httpGet({ url: `${apiUrl}/number_pool_stats`, params: params });
  return resp;
}

function extractPhoneNumber({ elem }) {
  // NOTE: only tested for US numbers!
  var numberText = null;
  var number = null;
  var href = null;
  const regex = new RegExp("\\+?\\(?\\d*\\)? ?\\(?\\d+\\)?\\d*([\\s./-]?\\d{2,})+", "g");

  if (elem.href && elem.href.startsWith("tel:")) {
    href = elem.href;
  }
  const text = elem.innerText;
  const html = elem.innerHTML;
  const match = regex.exec(text);
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

    const elemNum = extractPhoneNumber({ elem: elems[i] });

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
        const numberText = elemNum.text.replace(elemNum.numberText, overlay);
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
      const currentHTML = elems[i].innerHTML;
      const origElemData = numberOverlayMap.get(elems[i]);
      if (debug) {
        console.log("orig:", origElemData);
      }
      const origHTML = origElemData.html;
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
  const data = getItem(NUMBER_POOL_KEY);
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
    const params = paramsParse(window.location.search);
    if (urlParam in params && params[urlParam] === "1") {
      poolEnabled = true;
    }
  }

  if (!poolEnabled) {
    if (debug) {
      console.log('pool: not enabled');
    }
    return null;
  }

  var seshNumber = null;
  var seshInterval = null;

  if (seshData && seshData.poolNumbers && seshData.poolNumbers[poolId]) {
    const poolResult = seshData.poolNumbers[poolId];
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
    const msg = "pool: error getting number: " + JSON.stringify(e);
    if (window.rollbar) {
      window.rollbar.warning(msg);
    }
    console.warn(msg);
    const errorRes = { status: NUMBER_POOL_ERROR, msg: e.message, interval: seshInterval };
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
  } else {
    const poolNumbers = {};
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

function getCIDObj({ getter = getItem, setter = setItem } = {}) {
  const obj = getter(CID_KEY);
  if ((!obj) && window[CID_KEY]) {
    console.warn("got CID from global var");
    setter(CID_KEY, window[CID_KEY]);
    return window[CID_KEY];
  }
  return obj;
}

function getSIDObj({ getter = getSessionStorage, setter = setSessionStorage } = {}) {
  const obj = getter(SID_KEY);
  if ((!obj) && window[SID_KEY]) {
    console.warn("got SID from global var");
    setter(SID_KEY, window[SID_KEY]);
    return window[SID_KEY];
  }
  return obj;
}

function getVIDObj({ getter = getSessionStorage, setter = setSessionStorage } = {}) {
  const obj = getter(VID_KEY);
  if ((!obj) && window[VID_KEY]) {
    console.warn("got VID from global var");
    setter(VID_KEY, window[VID_KEY]);
    return window[VID_KEY];
  }
  return obj;
}

function getCID({ getter = getItem } = {}) {
  const obj = getCIDObj({ getter });
  return obj ? obj.id : null;
}

function getSID({ getter = getSessionStorage } = {}) {
  const obj = getSIDObj({ getter });
  return obj ? obj.id : null;
}

function getVID({ getter = getSessionStorage } = {}) {
  const obj = getVIDObj({ getter });
  return obj ? obj.id : null;
}

function getStorage() {
  return {
    cid: getCIDObj(),
    sid: getSIDObj(),
    vid: getVIDObj()
  };
}

function getIds() {
  return {
    cid: getCID(),
    sid: getSID(),
    vid: getVID()
  };
}

function removeCID() {
  removeItem(CID_KEY);
  if (window[CID_KEY]) {
    delete window[CID_KEY];
  }
}

function removeSID() {
  removeSessionStorage(SID_KEY);
  removeItem(SID_KEY);
  if (window[SID_KEY]) {
    delete window[SID_KEY];
  }
}

function removeVID() {
  removeSessionStorage(VID_KEY);
  if (window[VID_KEY]) {
    delete window[VID_KEY];
  }
}

function removeIds() {
  removeVID();
  removeSID();
  removeCID();
}

function zar({ apiUrl }) {
  return {
    name: 'zar',
    config: {
      apiUrl: apiUrl,
    },
    initialize: ({ config }) => { },
    loaded: () => { return true; },
    pageStart: ({ payload, config, instance }) => {
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
    trackStart: ({ payload, config, instance }) => {
      payload.properties.zar = getStorage();
      return payload;
    },
    page: ({ payload, options, instance, config }) => {
      if (instance.getState('context').debug) {
        console.log('page', payload, options, config);
      }
      httpPost({ url: `${config.apiUrl}/page`, data: payload });
    },
    track: ({ payload, options, instance, config }) => {
      if (instance.getState('context').debug) {
        console.log('track', payload);
      }
      httpPost({ url: `${config.apiUrl}/track`, data: payload });
    },
    reset: ({ instance }) => {
      removeIds();
    },
    bootstrap: ({ payload, config, instance }) => {
      // TODO: ability to override initIds params with zar() args
      const result = initIds({ debug: instance.getState('context').debug });
      instance.setAnonymousId(result.cid); // Override analytics' anonymous ID with client ID
    },
    methods: {
      apiUrl() {
        return apiUrl;
      },
      initIds() {
        const result = initIds({ debug: this.instance.getState('context').debug });
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
        return getCID();
      },
      getSID() {
        return getSID();
      },
      getVID() {
        return getVID();
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
          const elemRes = extractPhoneNumber({ elem: elems[i] });
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


