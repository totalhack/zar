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


const inBrowser = typeof document !== 'undefined';

// Copied from analytics-utils/src/detectAdBlock.js
function hasAdBlock() {
  if (!inBrowser) return false;
  // Create fake ad
  const fakeAd = document.createElement('div');
  fakeAd.innerHTML = '&nbsp;';
  fakeAd.className = 'pub_300x250 pub_300x250m pub_728x90 text-ad textAd text_ad text_ads text-ads text-ad-links';
  fakeAd.style = 'width: 1px !important; height: 1px !important; position: absolute !important; left: -10000px !important; top: -1000px !important;';
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
      const css = window.getComputedStyle(fakeAd, null);
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

export { uuid, hasAdBlock };
