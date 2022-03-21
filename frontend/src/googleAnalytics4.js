function gtag() {
  window.dataLayer.push(arguments);
}

window.gtag = gtag;

// https://github.com/idmadj/ga-gtag/blob/master/src/index.js
function gtagInit({ trackingId, configParams = {}, setParams = {} }) {
  var scriptId = 'ga-gtag';

  if (document.getElementById(scriptId)) return;

  var head = document.head;
  var script = document.createElement('script');
  script.id = scriptId;
  script.type = 'text/javascript';
  script.async = true;
  script.src = 'https://www.googletagmanager.com/gtag/js?id=' + trackingId;
  head.insertBefore(script, head.firstChild);

  window.dataLayer = window.dataLayer || [];

  gtag('js', new Date());
  if (setParams) {
    gtag('set', setParams);
  }
  gtag('config', trackingId, configParams);
}

function googleAnalytics4(pluginConfig = {}) {
  return {
    name: 'google-analytics-4',
    config: pluginConfig,
    initialize: function ({ config, instance }) {
      if (!config.trackingId) throw new Error('No GA trackingId defined');

      var configParams = {};
      var setParams = {};
      if (config.customDimensions) {
        var customMap = {};
        for (var i = 0; i < config.customDimensions.length; i++) {
          var customDim = config.customDimensions[i];
          configParams[customDim.name] = customDim.callback(instance, config);
          customMap['dimension' + (i + 1)] = customDim.name;
        }
        setParams['custom_map'] = customMap;
      }

      gtagInit({ trackingId: config.trackingId, configParams, setParams });
    },
    page: function ({ payload, config, instance }) {
      // no-op: GA4 sends page on init and page is just another "event"
    },
    track: function ({ payload, config, instance }) {
      gtag('event', payload.event, payload.properties);
    },
    identify: function ({ payload, config }) {
      // not supported yet
    },
    loaded: function () {
      return !!window.gtag;
    }
  };
}

export { gtag, googleAnalytics4 };