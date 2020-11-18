import { Analytics } from 'analytics';
import { getItem, setItem, removeItem } from '@analytics/storage-utils';
import googleAnalytics from '@analytics/google-analytics';
import googleTagManager from '@analytics/google-tag-manager';
import axios from 'axios';

import { uuid } from './utils';

const CID_KEY = '__zar_cid';
const SID_KEY = '__zar_sid';
const VID_KEY = '__zar_vid';
const DAY_TTL = 1000 * 60 * 60 * 24; // In milliseconds
const CID_TTL = DAY_TTL * 365 * 3; // N years, ~like GA
const SID_TTL = DAY_TTL * 2; // N days, ~like GA

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

function expireByReferrer(idObj, newVisit, debug) {
  if (document.referrer.indexOf(window.location.hostname) == -1) {
    if (debug) {
      console.log('Host not in referrer: ', window.location.hostname, '//', document.referrer);
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
  const sidObj = getSIDObj(); // Checks sessionStorage
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

  return { cid: cidResult.id, sid: sidResult.id, vid: vidResult.id };
}

function getCIDObj({ getter = getItem } = {}) {
  return getter(CID_KEY);
}

function getSIDObj({ getter = getSessionStorage } = {}) {
  return getter(SID_KEY);
}

function getVIDObj({ getter = getSessionStorage } = {}) {
  return getter(VID_KEY);
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
}

function removeSID() {
  removeSessionStorage(SID_KEY);
  removeItem(SID_KEY);
}

function removeVID() {
  removeSessionStorage(VID_KEY);
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
      const resp = axios.post(`${config.apiUrl}/page`, payload);
    },
    track: ({ payload, options, instance, config }) => {
      if (instance.getState('context').debug) {
        console.log('track', payload);
      }
      const resp = axios.post(`${config.apiUrl}/track`, payload);
    },
    reset: ({ instance }) => {
      removeIds();
    },
    bootstrap: ({ payload, config, instance }) => {
      // TODO: ability to override initIds params with zar() args
      const result = initIds({ debug: instance.getState('context').debug });
      instance.setAnonymousId(result.cid); // Override analytics' anonymouse ID with client ID
    },
    methods: {
      initIds() {
        const result = initIds({ debug: this.instance.getState('context').debug });
        this.instance.setAnonymousId(result.cid); // Override analytics' anonymouse ID with client ID
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
    }
  };
}

function getDefaultApiUrl() {
  return window.location.origin + '/api/v1';
}

function init({ app, gtmConfig, gaConfig, apiUrl = null, debug = false }) {
  // Opiniated init of Analytics - Loads GA and GTM separately
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


