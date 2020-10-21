import { Analytics } from 'analytics';
import { getItem, setItem, removeItem } from '@analytics/storage-utils';
import googleTagManager from '@analytics/google-tag-manager';

import { uuid } from './utils';

const CID_KEY = '__zar_cid';
const SID_KEY = '__zar_sid';
const VID_KEY = '__zar_vid';
const DAY_TTL = 1000 * 60 * 60 * 24 // In milliseconds
const CID_TTL = DAY_TTL * 365 * 2 // 2 years, ~like GA
// const SID_TTL = DAY_TTL; // 1 day, ~like GA
const SID_TTL = 1000 * 10;

function generateClientId() {
  return uuid();
}

function generateSessionId() {
  return uuid();
}

function generateVisitId() {
  return Date.now().toString(36) + '.' + Math.random().toString(36).substring(2);
}

function objectExpired(idObj, ttl) {
  const diff = Date.now() - idObj.t
  if (diff >= ttl) {
    // console.log('Expired after ', diff / 1000.0, 'seconds');
    return true;
  }
  return false;
}

function initId(key, expirationCallback, generator) {
  var id;
  var isNew = false;
  const idObj = getItem(key);
  if (!idObj || !idObj.id || (expirationCallback && expirationCallback(idObj))) {
    id = generator();
    isNew = true;
  } else {
    id = idObj.id;
  }
  const t = Date.now(); // Set or reset the time
  setItem(key, { id, t });
  return { id, isNew }
}

function expireByReferrer() {
  // console.log('referrer', document.referrer);
  // XXX If referrer is blank maybe we don't consider it a new visit?
  if (document.referrer.indexOf(window.location.hostname) == -1) {
    // console.log('new visit');
    return true;
  }
  return false;
}

function initIds(
  clientIdExpired = (idObj) => { return objectExpired(idObj, CID_TTL) },
  sessionIdExpired = (idObj) => { return objectExpired(idObj, SID_TTL) },
  visitIdExpired = expireByReferrer) {
  const cidResult = initId(CID_KEY, clientIdExpired, generateClientId);
  const sidResult = initId(SID_KEY, sessionIdExpired, generateSessionId);
  if (sidResult.isNew) {
    // Force a reset of the visit ID on new session
    removeVisitId();
  }
  const vidResult = initId(VID_KEY, visitIdExpired, generateVisitId);
  return { cid: cidResult.id, sid: sidResult.id, vid: vidResult.id }
}

function getClientId() {
  return getItem(CID_KEY).id;
}

function getSessionId() {
  return getItem(SID_KEY).id;
}

function getVisitId() {
  return getItem(VID_KEY).id;
}

function getIds() {
  return {
    cid: getClientId(),
    sid: getSessionId(),
    vid: getVisitId()
  }
}

function removeClientId() {
  return removeItem(CID_KEY);
}

function removeSessionId() {
  return removeItem(SID_KEY);
}

function removeVisitId() {
  return removeItem(VID_KEY);
}

function removeIds() {
  removeVisitId();
  removeSessionId();
  removeClientId();
}

function zar() {
  return {
    name: 'zar',
    initialize: ({ config }) => { },
    loaded: () => { return true; },
    pageStart: ({ payload, config, instance }) => {
      return Object.assign({}, payload, { zar: getIds() })
    },
    trackStart: ({ payload, config, instance }) => {
      return Object.assign({}, payload, { zar: getIds() })
    },
    page: ({ payload, options, instance, config }) => {
      console.log('page', payload, options, config);
      // axios call to custom backend
    },
    track: ({ payload }) => {
      console.log('track', payload);
      // axios call to custom backend
    },
    identify: ({ payload }) => {
      console.log('identify', payload);
      // axios call to custom backend
    },
    reset: ({ instance }) => {
      removeIds();
    },
    bootstrap: ({ payload, config, instance }) => {
      // TODO: ability to override initIds params with zar() args
      const result = initIds();
      // Override analytics' anonymouse ID with client ID
      instance.setAnonymousId(result.cid);
    },
    methods: {
      initIds() {
        const result = initIds();
        // Override analytics' anonymouse ID with client ID
        this.instance.setAnonymousId(result.cid);
        return result;
      },
      getIds() {
        return getIds();
      },
      getClientId() {
        return getClientId();
      },
      getSessionId() {
        return getSessionId();
      },
      getVisitId() {
        return getVisitId();
      },
    }
  }
}

function init({ app, gtmContainerId, debug = false }) {
  // Convenient opiniated init of Analytics
  return Analytics({
    app,
    debug,
    plugins: [
      zar(),
      googleTagManager({
        containerId: gtmContainerId
      })
    ]
  });
}

export { init, zar };


