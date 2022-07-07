// Much in here is copied from analytics-utils to keep bundle size down

import { get, set, remove, undef } from '@analytics/global-storage-utils';

var urlParams = new URLSearchParams(window.location.search);
var DEBUG = urlParams.get('zdbg');

export function dbg() {
  if (DEBUG != 1) return;
  console.debug(...arguments);
}

var supportsSessionStorage = hasSessionStorage();

function hasSessionStorage() {
  if (typeof supportsSessionStorage !== undef) {
    return supportsSessionStorage;
  }
  supportsSessionStorage = true;
  try {
    sessionStorage.setItem(undef, undef);
    sessionStorage.removeItem(undef);
  } catch (e) {
    supportsSessionStorage = false;
  }
  return supportsSessionStorage;
}

export function getSessionStorage(key) {
  // Get from SS if supported, fall back to global
  var value;
  var globalValue = get(key) || undefined;
  if (supportsSessionStorage) {
    value = sessionStorage.getItem(key);
    if ((!value) && globalValue) {
      value = globalValue;
      // Restore session storage
      sessionStorage.setItem(key, value);
    }
  } else {
    value = globalValue;
  }
  return value ? JSON.parse(value) : undefined;
}

export function setSessionStorage(key, value) {
  // Set both SS (if supported) and global
  var value_str = JSON.stringify(value);
  if (supportsSessionStorage) {
    sessionStorage.setItem(key, value_str);
  }
  set(key, value_str);
}

export function removeSessionStorage(key) {
  // Remove both SS (if supported) and global
  if (supportsSessionStorage) {
    sessionStorage.removeItem(key);
  }
  remove(key);
}

/* ref: http://bit.ly/2daP79j */
var lut = []; for (var i = 0; i < 256; i++) { lut[i] = (i < 16 ? '0' : '') + (i).toString(16); }

export function uuid() {
  var d0 = Math.random() * 0x100000000 >>> 0;
  var d1 = Math.random() * 0x100000000 >>> 0;
  var d2 = Math.random() * 0x100000000 >>> 0;
  var d3 = Math.random() * 0x100000000 >>> 0;
  return lut[d0 & 0xff] + lut[d0 >> 8 & 0xff] + lut[d0 >> 16 & 0xff] + lut[d0 >> 24 & 0xff] + '-' +
    lut[d1 & 0xff] + lut[d1 >> 8 & 0xff] + '-' + lut[d1 >> 16 & 0x0f | 0x40] + lut[d1 >> 24 & 0xff] + '-' +
    lut[d2 & 0x3f | 0x80] + lut[d2 >> 8 & 0xff] + '-' + lut[d2 >> 16 & 0xff] + lut[d2 >> 24 & 0xff] +
    lut[d3 & 0xff] + lut[d3 >> 8 & 0xff] + lut[d3 >> 16 & 0xff] + lut[d3 >> 24 & 0xff];
}

var inBrowser = typeof document !== 'undefined';

function decode(s) {
  try {
    return decodeURIComponent(s.replace(/\+/g, ' '));
  } catch (e) {
    return null;
  }
}

export function hasAdBlock() {
  if (!inBrowser) return false;
  // Create fake ad
  var fakeAd = document.createElement('div');
  fakeAd.innerHTML = '&nbsp;';
  fakeAd.className = 'pub_300x250 pub_300x250m pub_728x90 text-ad textAd text_ad text_ads text-ads text-ad-links';
  fakeAd.setAttribute('style', 'width: 1px !important; height: 1px !important; position: absolute !important; left: -10000px !important; top: -1000px !important;');
  try {
    // insert into page
    document.body.appendChild(fakeAd);
    if (
      document.body.getAttribute('abp') !== null ||
      fakeAd.offsetHeight === 0 ||
      fakeAd.clientHeight === 0
    ) {
      return true;
    }
    if (typeof getComputedStyle !== 'undefined') {
      var css = window.getComputedStyle(fakeAd, null);
      if (css && (css.getPropertyValue('display') === 'none' || css.getPropertyValue('visibility') === 'hidden')) {
        return true;
      }
    }
    // remove from page
    document.body.removeChild(fakeAd);
  } catch (e) {
    // swallow errors
  }
  return false;
}

function getSearchString(url) {
  if (url) {
    var p = url.match(/\?(.*)/);
    return (p && p[1]) ? p[1].split('#')[0] : '';
  }
  return inBrowser && window.location.search.substring(1);
}

export function paramsParse(url) {
  return getParamsAsObject(getSearchString(url));
}

function getParamsAsObject(query) {
  var params = {};
  var temp;
  var re = /([^&=]+)=?([^&]*)/g;

  // eslint-disable-next-line
  while (temp = re.exec(query)) {
    var k = decode(temp[1]);
    var v = decode(temp[2]);
    if (k.substring(k.length - 2) === '[]') {
      k = k.substring(0, k.length - 2);
      (params[k] || (params[k] = [])).push(v);
    } else {
      params[k] = (v === '') ? true : v;
    }
  }

  for (var prop in params) {
    var arr = prop.split('[');
    if (arr.length > 1) {
      assign(params, arr.map(function (x) { return x.replace(/[?[\]\\ ]/g, ''); }), params[prop]);
      delete params[prop];
    }
  }
  return params;
}

function assign(obj, keyPath, value) {
  var lastKeyIndex = keyPath.length - 1;
  for (var i = 0; i < lastKeyIndex; ++i) {
    var key = keyPath[i];
    if (!(key in obj)) {
      obj[key] = {};
    }
    obj = obj[key];
  }
  obj[keyPath[lastKeyIndex]] = value;
}

function makeRequest({ method, url, data, json = true }) {
  return new Promise(function (resolve, reject) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, url);
    xhr.withCredentials = true;

    if (json) {
      xhr.setRequestHeader("Accept", "application/json");
      xhr.setRequestHeader("Content-Type", "application/json");
    }

    xhr.onload = function () {
      if (this.status >= 200 && this.status < 300) {
        if (json) {
          resolve(JSON.parse(xhr.response));
        } else {
          resolve(xhr.response);
        }
      } else {
        reject({
          status: this.status,
          message: xhr.statusText
        });
      }
    };
    xhr.onerror = function () {
      reject({
        status: this.status,
        message: "Network Error"
      });
    };
    if (data) {
      xhr.send(data);
    } else {
      xhr.send();
    }
  });
}

function formatParams(params) {
  return "?" + Object
    .keys(params)
    .map(function (key) {
      return key + "=" + encodeURIComponent(params[key]);
    })
    .join("&");
}

async function postBeacon({ url, data }) {
  if (window &&
    window.navigator &&
    typeof window.navigator.sendBeacon === "function" &&
    typeof window.Blob === "function") {
    try {
      if (window.navigator.sendBeacon(url, JSON.stringify(data))) {
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }
  return false;
}

export async function httpGet({ url, params = null, json = true }) {
  var finalUrl = url;
  if (params) {
    finalUrl = finalUrl + formatParams(params);
  }
  return await makeRequest({ method: "GET", url: finalUrl, json });
}

export async function httpPost({ url, data, json = true, beacon = false }) {
  var finalData = data;
  if (json) {
    finalData = JSON.stringify(finalData);
  }
  if (beacon) {
    var res = await postBeacon({ url, data });
    if (res) {
      return;
    }
    dbg('Beacon failed')
  }
  return await makeRequest({ method: "POST", url, data: finalData, json });
}

