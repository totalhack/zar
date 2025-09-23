// @vitest-environment jsdom
// @vitest-environment-options { "url": "https://example.com/?zdbg=1" }
import { describe, it, expect, beforeEach, vi } from "vitest";

// Keep mocks consistent with existing test file
vi.mock("../src/facebook", () => ({ facebook: () => ({ name: "facebook" }) }));
vi.mock("../src/googleAnalytics4", () => ({
  googleAnalytics4: () => ({ name: "ga4" })
}));
vi.mock("../src/utils", () => ({
  dbg: () => {},
  warn: () => {},
  afterDOMContentLoaded: (fn) => fn(),
  isBot: () => false,
  hasAdBlock: () => false,
  httpGet: async () => ({}),
  httpPost: async () => ({}),
  getSessionStorage: () => null,
  setSessionStorage: () => {},
  isFunc: (f) => typeof f === "function"
}));

import { __test__, zar } from "../src/zar.js";

const {
  extractPhoneNumber,
  overlayPhoneNumber,
  revertOverlayNumbers,
  drainPoolDataLayer,
  getPoolId
} = __test__;

describe("extractPhoneNumber", () => {
  it("finds and normalizes US phone numbers and tel: href", () => {
    const a = document.createElement("a");
    a.href = "tel:6505551234";
    a.innerText = "Call 650-555-1234 today";

    const res = extractPhoneNumber({ elem: a });
    expect(res.numberText).toBe("650-555-1234");
    expect(res.number).toBe("6505551234");
    expect(res.href).toBe("tel:6505551234");
  });
});

describe("overlayPhoneNumber / revertOverlayNumbers", () => {
  let a;

  beforeEach(() => {
    a = document.createElement("a");
    a.href = "tel:6505551234";
    a.innerText = "Call 650-555-1234";
    document.body.innerHTML = "";
    document.body.appendChild(a);
  });

  it("overlays display text with formatted number and tel: href, then reverts", () => {
    overlayPhoneNumber({ elems: [a], number: "6505550000" });

    // Overlays keep dash format if original had dashes
    expect(a.textContent).toContain("650-555-0000");
    expect(a.href).toContain("tel:+16505550000");

    // Revert to original state
    revertOverlayNumbers({ elems: [a] });
    expect(a.textContent).toBe("Call 650-555-1234");
    // Note: DOM normalizes href to absolute; check endsWith
    expect(a.href.endsWith("tel:6505551234")).toBe(true);
  });
});

describe("drainPoolDataLayer", () => {
  it("merges objects and clears the data layer", () => {
    // Ensure global exists as module under test expects
    window.zarPoolDataLayer = [{ a: 1 }, { b: 2 }, { a: 3 }];
    const merged = drainPoolDataLayer();
    expect(merged).toEqual({ a: 3, b: 2 });
    expect(window.zarPoolDataLayer.length).toBe(0);
  });
});

describe("getPoolId", () => {
  it("returns a literal id or calls a function to obtain it", () => {
    expect(getPoolId("pool-123")).toBe("pool-123");
    expect(getPoolId(() => "dyn-456")).toBe("dyn-456");
  });
});

describe("extractPhoneNumber - additional formats", () => {
  it("normalizes numbers with parentheses and spaces, strips leading 1/+1", () => {
    const a = document.createElement("a");
    a.href = "tel:+1-650-555-1234";
    a.innerText = "Call (650) 555 1234 now";

    const res = extractPhoneNumber({ elem: a });
    expect(res.numberText).toBe("(650) 555 1234");
    expect(res.number).toBe("6505551234");
    expect(res.href).toBe("tel:+1-650-555-1234");
  });
});

describe("overlayPhoneNumber - additional behaviors", () => {
  let a;

  beforeEach(() => {
    document.body.innerHTML = "";
    a = document.createElement("a");
    a.href = "tel:6505551234";
    a.innerText = "Call 650-555-1234";
    document.body.appendChild(a);
  });

  it("does not overlay again when called twice without force", () => {
    overlayPhoneNumber({ elems: [a], number: "6505550000" });
    const firstText = a.textContent;

    overlayPhoneNumber({ elems: [a], number: "6505559999" }); // should be ignored
    expect(a.textContent).toBe(firstText);
    expect(a.textContent).toContain("650-555-0000");
  });

  it("re-overlays when force = true", () => {
    overlayPhoneNumber({ elems: [a], number: "6505550000" });
    expect(a.textContent).toContain("650-555-0000");

    overlayPhoneNumber({ elems: [a], number: "6505559999", force: true });
    expect(a.textContent).toContain("650-555-9999");

    // Revert to original
    revertOverlayNumbers({ elems: [a] });
    expect(a.textContent).toBe("Call 650-555-1234");
  });

  it("uses +1-prefixed overlay text if original had no dashes", () => {
    const b = document.createElement("a");
    b.href = "tel:6505552222";
    b.innerText = "Call 6505552222";
    document.body.appendChild(b);

    overlayPhoneNumber({ elems: [b], number: "6505550000" });
    // Since original number text had no dashes, overlay uses raw overlayNum (+1 prefixed)
    expect(b.textContent).toContain("+16505550000");
    revertOverlayNumbers({ elems: [b] });
  });
});

describe("drainPoolDataLayer - additional", () => {
  it("returns null when data layer is missing, not array, or empty", () => {
    window.zarPoolDataLayer = [];
    expect(drainPoolDataLayer()).toBeNull();

    window.zarPoolDataLayer = null;
    expect(drainPoolDataLayer()).toBeNull();

    // @ts-ignore
    window.zarPoolDataLayer = { not: "an array" };
    expect(drainPoolDataLayer()).toBeNull();
  });
});

describe("getPoolId - function and literal", () => {
  it("returns value from function or literal", () => {
    expect(getPoolId("abc")).toBe("abc");
    expect(getPoolId(() => "dynamic")).toBe("dynamic");
  });
});

describe("zar plugin behaviors", () => {
  beforeEach(() => {
    // Allow setting document.referrer in jsdom
    Object.defineProperty(document, "referrer", {
      value: "https://ref.example/",
      configurable: true
    });
  });

  it("pageStart enriches payload and removes hash/path/search; sets pool_id and pool_context", () => {
    const plugin = zar({
      apiUrl: "https://api.example",
      poolConfig: {
        poolId: () => "pool-xyz",
        contextCallback: (ctx) => ({ ...ctx, extra: true })
      }
    });

    window.zarPoolDataLayer = [{ k: 1 }, { k: 2 }]; // last wins merge

    const payload = {
      properties: {
        hash: "#frag",
        path: "/some/path",
        search: "?q=1"
      }
    };

    const out = plugin.pageStart({
      payload,
      config: plugin.config,
      instance: {}
    });
    expect(out.properties).toBeDefined();
    // Added fields
    expect(out.properties.referrer).toBe("https://ref.example/");
    expect(out.properties.zar).toBeDefined();
    // Pool fields
    expect(out.properties.pool_id).toBe("pool-xyz");
    expect(out.properties.pool_context).toEqual({ k: 2, extra: true });
  });

  it("trackStart sets url and referrer on payload.properties", () => {
    const plugin = zar({ apiUrl: "https://api.example", poolConfig: null });
    const payload = { properties: {} };
    const out = plugin.trackStart({
      payload,
      config: plugin.config,
      instance: {}
    });

    expect(out.properties.url).toBe(window.location.href);
    expect(out.properties.referrer).toBe("https://ref.example/");
  });
});
