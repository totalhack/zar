import { Analytics } from 'analytics';
import { getItem, setItem, removeItem } from '@analytics/storage-utils';
import googleTagManager from '@analytics/google-tag-manager';

const CID_KEY = '__zar_cid';
const SID_KEY = '__zar_sid';
const VID_KEY = '__zar_vid';

// In milliseconds
const DAY_TTL = 1000 * 60 * 60 * 24
const CID_TTL = DAY_TTL * 365 * 2 // 2 years, ~like GA
// const SID_TTL = DAY_TTL; // 1 day, ~like GA
const SID_TTL = 1000 * 10;

/* ref: http://bit.ly/2daP79j */
var lut = []; for (var i = 0; i < 256; i++) { lut[i] = (i < 16 ? '0' : '') + (i).toString(16); }
function uuid() {
  var d0 = Math.random() * 0x100000000 >>> 0;
  var d1 = Math.random() * 0x100000000 >>> 0;
  var d2 = Math.random() * 0x100000000 >>> 0;
  var d3 = Math.random() * 0x100000000 >>> 0;
  return lut[d0 & 0xff] + lut[d0 >> 8 & 0xff] + lut[d0 >> 16 & 0xff] + lut[d0 >> 24 & 0xff] + '-' +
    lut[d1 & 0xff] + lut[d1 >> 8 & 0xff] + '-' + lut[d1 >> 16 & 0x0f | 0x40] + lut[d1 >> 24 & 0xff] + '-' +
    lut[d2 & 0x3f | 0x80] + lut[d2 >> 8 & 0xff] + '-' + lut[d2 >> 16 & 0xff] + lut[d2 >> 24 & 0xff] +
    lut[d3 & 0xff] + lut[d3 >> 8 & 0xff] + lut[d3 >> 16 & 0xff] + lut[d3 >> 24 & 0xff];
}

function generateClientId() {
  // TODO: Get this from GA if its present?
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

function init({ app, gtmContainerId, debug = false }) {
  // TODO: way to pass other plugins?

  initIds();

  return {
    analytics: Analytics({
      app,
      debug,
      plugins: [
        googleTagManager({
          containerId: gtmContainerId
        })
      ]
    })
  };
}

export {
  init,
  initIds,
  getIds,
  getClientId,
  getSessionId,
  getVisitId,
  removeIds
};

