/* eslint-disable no-undef */
/**
 * E2E test for sid_ctx flow.
 *
 * Prerequisites:
 * - Backend running at API_URL (default: http://localhost:8000/api/v2)
 * - A valid pool configured with POOL_ID
 * - POOL_KEY set for track_call auth
 *
 * Run with: VITE_E2E=1 POOL_KEY=your-key npm test -- test/e2e/sidContext.e2e.spec.js
 */
import { describe, it, expect, beforeAll, afterAll } from "vitest";

// Note: process.env in Vitest doesn't auto-load VITE_ prefixed vars
// Use non-prefixed names or import.meta.env for Vite-specific vars
const API_URL = process.env.API_URL || "http://localhost/api/v2";
const POOL_ID = parseInt(process.env.POOL_ID || "1", 10);
const POOL_KEY = process.env.POOL_KEY || "";

// Skip if not running E2E tests
const runE2E = process.env.VITE_E2E === "1";

// Helper for fetch with better error handling
async function fetchJSON(url, options) {
  const resp = await fetch(url, options);
  const text = await resp.text();
  try {
    return { response: resp, data: JSON.parse(text) };
  } catch {
    console.error("Failed to parse JSON response:", text);
    throw new Error(`Non-JSON response: ${text.substring(0, 200)}`);
  }
}

describe.skipIf(!runE2E)("sid_ctx E2E flow", () => {
  let trackingNumber = null;
  let sid = null;
  let vid = null;
  let trackCallSid = null;
  const callerNumber = "5559876543";

  beforeAll(async () => {
    // Reset the pool with preserve=true to keep numbers but clear lease contexts
    console.log("Resetting pool (preserving numbers)...");
    await fetch(
      `${API_URL}/reset_pool?pool_id=${POOL_ID}&preserve=true&key=${POOL_KEY}`
    );

    // Small delay to ensure Redis state is ready
    await new Promise((r) => setTimeout(r, 100));

    // Generate a vid like the frontend does
    vid =
      Date.now().toString(36) + "." + Math.random().toString(36).substring(2);

    // First call /page to establish a session
    const { data: pageData } = await fetchJSON(`${API_URL}/page`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: "page",
        properties: {
          url: "https://example.com/?pl=1",
          pool_id: POOL_ID,
          pool_context: {},
          zar: {
            vid: { id: vid, t: Date.now(), origReferrer: "", isNew: true }
          }
        },
        userId: null,
        anonymousId: null
      })
    });

    console.log("Page response:", pageData);
    sid = pageData.sid;

    // Verify /page response structure
    expect(pageData.vid).toBeDefined();
    expect(pageData.sid).toBeDefined();
    expect(pageData.cid).toBeDefined();
    expect(pageData.id).toBeDefined();

    // If pool_data was returned, grab the number
    if (pageData.pool_data && pageData.pool_data.number) {
      trackingNumber = pageData.pool_data.number;
    } else if (pageData.pool_data && pageData.pool_data.msg === "pool empty") {
      console.error(
        "Pool is empty! Ensure pool_id",
        POOL_ID,
        "has numbers configured in the database."
      );
    }
  });

  afterAll(async () => {
    // Clean up: remove user context for both SIDs
    if (sid && POOL_KEY) {
      await fetch(
        `${API_URL}/remove_user_context?id_type=sid&user_id=${sid}&key=${POOL_KEY}`
      );
    }
    if (trackCallSid && trackCallSid !== sid && POOL_KEY) {
      await fetch(
        `${API_URL}/remove_user_context?id_type=sid&user_id=${trackCallSid}&key=${POOL_KEY}`
      );
    }
  });

  it("step 1: /page returns pool_data with number (no sid_ctx initially)", async () => {
    // Verify we got a number from /page's pool_data response
    if (!trackingNumber) {
      throw new Error(
        "No tracking number received from /page. Pool may be empty or misconfigured."
      );
    }
    console.log("Got number from /page:", trackingNumber);

    // The initial pool_data should NOT have sid_ctx since no call has been made yet
    // We verify this by checking get_user_context returns null
    const { data: ctxData } = await fetchJSON(
      `${API_URL}/get_user_context?id_type=sid&user_id=${sid}&key=${POOL_KEY}`,
      { method: "GET" }
    );
    console.log("Initial user context:", ctxData);

    expect(ctxData.status).toBe("success");
    expect(ctxData.msg).toBeNull(); // No context set yet
  });

  it("step 2: /track_call sets sid context and returns full context", async () => {
    if (!trackingNumber) {
      throw new Error(
        "No tracking number available - skipping track_call test"
      );
    }

    const { data } = await fetchJSON(`${API_URL}/track_call`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        key: POOL_KEY,
        call_id: `e2e-call-${Date.now()}`,
        call_to: trackingNumber,
        call_from: callerNumber
      })
    });
    console.log("track_call response:", data);

    // Verify track_call response structure
    expect(data.status).toBe("success");
    expect(data.msg).toBeDefined();
    expect(data.msg.pool_id).toBe(POOL_ID);
    expect(data.msg.request_context).toBeDefined();
    expect(data.msg.request_context.sid).toBeDefined();
    expect(data.msg.leased_at).toBeGreaterThan(0);
    expect(data.msg.renewed_at).toBeGreaterThan(0);
    expect(typeof data.msg.has_cached_route).toBe("boolean");

    // Capture the SID from track_call response
    trackCallSid = data.msg.request_context.sid;
    console.log("track_call used SID:", trackCallSid);
    console.log("Our test SID:", sid);

    // If pool was reset properly, these should match
    // If not, we'll use trackCallSid for subsequent tests
    if (trackCallSid !== sid) {
      console.warn(
        "SIDs don't match - pool may have stale context. Using trackCallSid for verification."
      );
    }
  });

  it("step 3: /get_user_context confirms sid context was set by track_call", async () => {
    // Use the SID that track_call actually used
    const sidToVerify = trackCallSid || sid;
    expect(sidToVerify).toBeTruthy();
    console.log("Verifying sid context for:", sidToVerify);

    const { data } = await fetchJSON(
      `${API_URL}/get_user_context?id_type=sid&user_id=${sidToVerify}&key=${POOL_KEY}`,
      { method: "GET" }
    );
    console.log("get_user_context response:", data);

    // Verify the response structure from the actual backend
    expect(data.status).toBe("success");
    expect(data.msg).toBeDefined();
    expect(data.msg).not.toBeNull();

    // Verify the sid_ctx fields that track_call should have set
    expect(data.msg.last_called_number).toBe(trackingNumber);
    expect(data.msg.last_called_time).toBeDefined();
    expect(typeof data.msg.last_called_time).toBe("number");
    expect(data.msg.last_called_time).toBeGreaterThan(0);

    // Verify timestamp is recent (within last 60 seconds)
    const now = Math.floor(Date.now() / 1000);
    expect(now - data.msg.last_called_time).toBeLessThan(60);
  });

  it("step 4: verify sid_ctx structure matches what initCallback would receive", async () => {
    // Use the SID that track_call actually used
    const sidToVerify = trackCallSid || sid;

    // This verifies the exact structure that the frontend's initCallback will receive
    // when number_pool returns sid_ctx
    const { data } = await fetchJSON(
      `${API_URL}/get_user_context?id_type=sid&user_id=${sidToVerify}&key=${POOL_KEY}`,
      { method: "GET" }
    );

    const sidCtx = data.msg;

    // Verify the structure that initCallback expects
    expect(sidCtx).toHaveProperty("last_called_number");
    expect(sidCtx).toHaveProperty("last_called_time");

    // Test that client-side helper logic works with real data
    const hasCalledRecently = (ctx, withinSeconds = 300) => {
      if (!ctx || !ctx.last_called_time) return false;
      const now = Math.floor(Date.now() / 1000);
      return now - ctx.last_called_time < withinSeconds;
    };

    // Should be true since we just called
    expect(hasCalledRecently(sidCtx, 300)).toBe(true);

    // Should be false with a very short window
    expect(hasCalledRecently(sidCtx, 0)).toBe(false);

    // Verify we can create a Date from the timestamp
    const calledAt = new Date(sidCtx.last_called_time * 1000);
    expect(calledAt).toBeInstanceOf(Date);
    expect(calledAt.getTime()).toBeGreaterThan(0);
  });

  it("step 4b: /number_pool initial call returns sid_ctx when context exists", async () => {
    // NOTE: This tests that a NEW /number_pool call (not renewal) returns sid_ctx.
    // In practice, the frontend uses renewals which require cookies we can't send here.
    // This verifies the backend logic works - the full browser flow would need Playwright.

    const sidToVerify = trackCallSid || sid;

    // Make a fresh /number_pool call (will get a potentially different number)
    // but should still return sid_ctx for the session
    const { data } = await fetchJSON(`${API_URL}/number_pool`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pool_id: POOL_ID,
        number: null, // New lease, not renewal
        context: { url: "https://example.com/?pl=1" },
        properties: {
          zar: {
            vid: { id: vid, t: Date.now(), origReferrer: "", isNew: false },
            sid: { id: sidToVerify, t: Date.now() }
          }
        }
      })
    });
    console.log("/number_pool response with sid_ctx:", data);

    expect(data.status).toBe("success");
    expect(data.number).toBeDefined();

    // This is the key assertion - sid_ctx should be returned
    expect(data.sid_ctx).toBeDefined();
    expect(data.sid_ctx.last_called_number).toBe(trackingNumber);
    expect(data.sid_ctx.last_called_time).toBeGreaterThan(0);
  });

  it("step 4c: /page returns sid_ctx in pool_data after track_call", async () => {
    // This tests that a subsequent /page call includes sid_ctx in pool_data
    // after track_call has set the user context.

    const { data: pageData } = await fetchJSON(`${API_URL}/page`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: "page",
        properties: {
          url: "https://example.com/another-page?pl=1",
          pool_id: POOL_ID,
          pool_context: {},
          zar: {
            vid: { id: vid, t: Date.now(), origReferrer: "", isNew: false },
            sid: { id: sid, t: Date.now() }
          }
        },
        userId: null,
        anonymousId: null
      })
    });
    console.log("/page response with sid_ctx:", pageData);

    expect(pageData.sid).toBe(sid);
    expect(pageData.pool_data).toBeDefined();
    expect(pageData.pool_data.status).toBe("success");

    // This is the key assertion - pool_data should include sid_ctx
    expect(pageData.pool_data.sid_ctx).toBeDefined();
    expect(pageData.pool_data.sid_ctx.last_called_number).toBe(trackingNumber);
    expect(pageData.pool_data.sid_ctx.last_called_time).toBeGreaterThan(0);
  });

  it("step 5: /update_user_context can modify sid context", async () => {
    // Test that we can update the user context via the API
    const { data: updateData } = await fetchJSON(
      `${API_URL}/update_user_context`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key: POOL_KEY,
          id_type: "sid",
          user_id: sid,
          context: {
            last_called_number: trackingNumber,
            last_called_time: Math.floor(Date.now() / 1000),
            custom_field: "test_value"
          }
        })
      }
    );
    console.log("update_user_context response:", updateData);

    expect(updateData.status).toBe("success");

    // Verify the update was applied
    const { data: verifyData } = await fetchJSON(
      `${API_URL}/get_user_context?id_type=sid&user_id=${sid}&key=${POOL_KEY}`,
      { method: "GET" }
    );
    console.log("Verified updated context:", verifyData);

    expect(verifyData.status).toBe("success");
    expect(verifyData.msg.custom_field).toBe("test_value");
    expect(verifyData.msg.last_called_number).toBe(trackingNumber);
  });

  it("step 6: /remove_user_context clears sid context", async () => {
    // Test cleanup endpoint
    const removeResp = await fetch(
      `${API_URL}/remove_user_context?id_type=sid&user_id=${sid}&key=${POOL_KEY}`
    );
    const removeData = await removeResp.json();
    console.log("remove_user_context response:", removeData);

    expect(removeData.status).toBe("success");

    // Verify it was removed
    const { data: verifyData } = await fetchJSON(
      `${API_URL}/get_user_context?id_type=sid&user_id=${sid}&key=${POOL_KEY}`,
      { method: "GET" }
    );
    console.log("Context after removal:", verifyData);

    expect(verifyData.status).toBe("success");
    expect(verifyData.msg).toBeNull();
  });
});
