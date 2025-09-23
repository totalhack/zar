/* eslint-disable no-empty */
export function Analytics({ app, plugins = [] } = {}) {
  const instance = {
    app,
    plugins: {},
    page: (payload = {}) => runPage(instance, payload),
    track: (event, properties = {}, options) =>
      runTrack(
        instance,
        options ? { event, properties, options } : { event, properties }
      ),
    reset: async (...args) => runReset(instance, ...args)
  };

  // Register plugins and bind/hoist methods to plugin object
  plugins.forEach((p) => {
    if (!p || !p.name) return;
    p.instance = instance;
    if (p.methods) {
      Object.keys(p.methods).forEach((k) => {
        const fn = p.methods[k];
        if (typeof fn === "function") {
          const bound = fn.bind(p);
          p.methods[k] = bound;
          p[k] = bound;
        }
      });
    }
    instance.plugins[p.name] = p;
  });

  // Initialize plugins
  plugins.forEach((p) => {
    try {
      p.initialize && p.initialize({ config: p.config, instance });
    } catch (_) {}
  });

  return instance;
}

const hashRegex = /#.*$/;

function currentUrl() {
  if (typeof window === "undefined") return "";
  return window.location.href.replace(hashRegex, "");
}

function getPageData(pageData = {}) {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return pageData;
  }
  const { title, referrer } = document;
  const { innerWidth, innerHeight } = window;
  const url = currentUrl();
  const page = {
    title: title,
    url: url,
    width: innerWidth,
    height: innerHeight
  };
  if (referrer && referrer !== "") {
    page.referrer = referrer;
  }
  return Object.assign({}, page, pageData);
}

async function runPage(instance, payload = {}) {
  if (!payload.type) payload.type = "page";
  payload.properties = getPageData(payload.properties || {});

  Object.values(instance.plugins).forEach((p) => {
    if (typeof p.pageStart === "function") {
      try {
        const next = p.pageStart({ payload, config: p.config, instance });
        if (next) payload = next;
      } catch (_) {}
    }
  });

  for (const p of Object.values(instance.plugins)) {
    if (typeof p.page === "function") {
      try {
        await p.page({ payload, options: {}, instance, config: p.config });
      } catch (_) {}
    }
  }
  return payload;
}

async function runTrack(instance, payload = {}) {
  if (!payload.type) payload.type = "track";
  const base = getPageData();
  const props = payload.properties || {};
  if (props.url === undefined) props.url = base.url;
  if (props.referrer === undefined && base.referrer !== undefined) {
    props.referrer = base.referrer;
  }
  payload.properties = props;

  const options = payload.options || {};
  const perCallPlugins =
    options && typeof options.plugins === "object" ? options.plugins : null;
  const isDisabled = (p) => perCallPlugins && perCallPlugins[p.name] === false;

  Object.values(instance.plugins).forEach((p) => {
    if (isDisabled(p)) return;
    if (typeof p.trackStart === "function") {
      try {
        const next = p.trackStart({
          payload,
          options,
          config: p.config,
          instance
        });
        if (next) payload = next;
      } catch (_) {}
    }
  });

  for (const p of Object.values(instance.plugins)) {
    if (isDisabled(p)) continue;
    if (typeof p.track === "function") {
      try {
        await p.track({ payload, options, instance, config: p.config });
      } catch (_) {}
    }
  }
  return payload;
}

async function runReset(instance, ...args) {
  for (const p of Object.values(instance.plugins)) {
    if (typeof p.reset === "function") {
      try {
        await p.reset(...args);
      } catch (_) {}
    }
  }
}
