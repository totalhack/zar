function facebookScriptInit(f, b, e, v, n, t, s) {
  if (f.fbq) return;
  n = f.fbq = function () {
    n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
  };
  if (!f._fbq) f._fbq = n;
  n.push = n;
  n.loaded = !0;
  n.version = "2.0";
  n.queue = [];
  t = b.createElement(e);
  t.async = !0;
  t.src = v;
  s = b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t, s);
}

function facebookInit({ trackingId }) {
  facebookScriptInit(
    window,
    document,
    "script",
    "https://connect.facebook.net/en_US/fbevents.js"
  );
  window.fbq("init", trackingId);
}

function facebook(pluginConfig = {}) {
  return {
    name: "facebook",
    config: pluginConfig,
    initialize: function ({ config, instance }) {
      if (!config.trackingId) throw new Error("No Facebook trackingId defined");
      facebookInit({ trackingId: config.trackingId });
    },
    page: function ({ payload, config, instance }) {
      window.fbq("track", "PageView");
    },
    track: function ({ payload, config, instance }) {
      window.fbq("trackCustom", payload.event, payload.properties);
    },
    identify: function ({ payload, config }) {
      // not supported yet
    },
    loaded: function () {
      return !!window.fbq;
    }
  };
}

export { facebookInit, facebook };
