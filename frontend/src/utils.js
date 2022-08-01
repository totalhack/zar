export var urlParams = new URLSearchParams(window.location.search);
var DEBUG = urlParams.get('zdbg');
var zarGlobal = {};
const undef = 'undefined';

export function dbg() {
  if (DEBUG != 1) return;
  console.debug(...arguments);
}

export function warning(msg) {
  console.warn(msg)
  if (window.Rollbar) {
    window.Rollbar.warning(msg);
  }
}

export function isFunc(value) {
  return value && (Object.prototype.toString.call(value) === "[object Function]" || "function" === typeof value || value instanceof Function);
}

export function isBot() {
  var ua = navigator.userAgent || ''
  var bots = new RegExp([
    /bot/, /spider/, /crawl/, /mediapartners/, /Google-Read-Aloud/, /semrush/
  ].map((r) => r.source).join("|"), "i")
  return bots.test(ua)
}

export function afterDOMContentLoaded(func) {
  if (document.readyState === "complete"
    || document.readyState === "loaded"
    || document.readyState === "interactive") {
    func()
  } else {
    window.addEventListener('DOMContentLoaded', func);
  }
}

// Copied from analytics-utils to keep bundle size down

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
  var globalValue = zarGlobal[key];
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
  zarGlobal[key] = value_str;
}

export function removeSessionStorage(key) {
  // Remove both SS (if supported) and global
  if (supportsSessionStorage) {
    sessionStorage.removeItem(key);
  }
  delete zarGlobal[key];
}

export function hasAdBlock() {
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
      const blob = new Blob([JSON.stringify(data)], { type: 'text/plain; charset=UTF-8' });
      if (window.navigator.sendBeacon(url, blob)) {
        return true;
      }
      return false;
    } catch (e) {
      warning("postBeacon:", e)
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

