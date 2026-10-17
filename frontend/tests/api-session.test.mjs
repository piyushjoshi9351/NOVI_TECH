import assert from "node:assert/strict";
import test from "node:test";

let sequence = 0;
async function setup(t, pathname = "/passport") {
  const storage = new Map([["novi_token", "old-token"], ["novi_user", JSON.stringify({ id: 1 })]]);
  const redirects = [];
  const events = [];
  t.mock.method(globalThis, "fetch", async () => Response.json({ detail: "Expired" }, { status: 401 }));
  Object.defineProperty(globalThis, "window", { value: {
    localStorage: { getItem: (key) => storage.get(key) ?? null, removeItem: (key) => storage.delete(key) },
    location: { pathname, search: "", replace: (url) => redirects.push(url) },
    dispatchEvent: (event) => events.push(event.type),
  }, configurable: true });
  t.after(() => { delete globalThis.window; });
  const client = await import(`../src/api.js?test=${sequence++}`);
  client.setApiToken("old-token");
  t.after(() => client.resetWarmAll());
  return { client, storage, redirects, events };
}

test("parallel protected 401s clear credentials and redirect exactly once", async (t) => {
  const { client, storage, redirects, events } = await setup(t);
  const results = await Promise.allSettled([client.api("/dna"), client.api("/auth/me")]);
  assert.ok(results.every((result) => result.status === "rejected" && result.reason.status === 401));
  assert.equal(client.getApiToken(), null);
  assert.equal(storage.has("novi_token"), false);
  assert.equal(storage.has("novi_user"), false);
  assert.deepEqual(redirects, ["/login?next=%2Fpassport"]);
  assert.deepEqual(events, [client.SESSION_EXPIRED]);
});

for (const path of ["/login", "/signup"]) test(`expired session on ${path} does not reload the auth page`, async (t) => {
  const { client, storage, redirects } = await setup(t, path);
  await assert.rejects(client.api("/auth/me"), { status: 401 });
  assert.equal(storage.has("novi_token"), false);
  assert.deepEqual(redirects, []);
});

test("incorrect login credentials do not expire an existing session", async (t) => {
  const { client, storage, redirects, events } = await setup(t, "/login");
  await assert.rejects(client.api("/auth/login", { method: "POST", body: "{}" }), { status: 401 });
  assert.equal(storage.get("novi_token"), "old-token");
  assert.deepEqual(redirects, []);
  assert.deepEqual(events, []);
});

test("a delayed 401 from an earlier JWT cannot sign out its replacement", async (t) => {
  const { client, storage, redirects } = await setup(t);
  let rejectOld;
  t.mock.method(globalThis, "fetch", () => new Promise((resolve) => { rejectOld = resolve; }));
  const pending = client.api("/auth/me");
  client.setApiToken("replacement-token");
  storage.set("novi_token", "replacement-token");
  rejectOld(Response.json({ detail: "Expired" }, { status: 401 }));
  await assert.rejects(pending, { status: 401 });
  assert.equal(client.getApiToken(), "replacement-token");
  assert.equal(storage.get("novi_token"), "replacement-token");
  assert.deepEqual(redirects, []);
});

test("401 invalidates cached data before another login", async (t) => {
  const { client, storage } = await setup(t);
  let dnaReads = 0;
  t.mock.method(globalThis, "fetch", async (url) => url.endsWith("/dna")
    ? Response.json({ owner: ++dnaReads }) : Response.json({}, { status: 401 }));
  assert.deepEqual(await client.api("/dna"), { owner: 1 });
  await assert.rejects(client.api("/auth/me"), { status: 401 });
  client.setApiToken("new-token");
  storage.set("novi_token", "new-token");
  assert.deepEqual(await client.api("/dna"), { owner: 2 });
});

test("image and streaming requests use the same 401 handling", async (t) => {
  const { client, redirects } = await setup(t);
  assert.equal(await client.apiImage("/parent/students/1/photo"), null);
  assert.equal(redirects.length, 1);
  client.setApiToken("another-token");
  await assert.rejects(client.streamChat({ message: "hello" }), { status: 401 });
  assert.equal(redirects.length, 2);
});

function fakeTimers(t) {
  const queue = [];
  const cancelled = new Set();
  let id = 0;
  t.mock.method(globalThis, "setTimeout", (callback) => { queue.push({ id: ++id, callback }); return id; });
  t.mock.method(globalThis, "clearTimeout", (timer) => { cancelled.add(timer); });
  return () => {
    while (queue.length) {
      const entry = queue.shift();
      if (!cancelled.has(entry.id)) entry.callback();
    }
  };
}

test("temporary-password and incomplete students never prefetch data", async (t) => {
  const { client } = await setup(t);
  const drain = fakeTimers(t);
  const reads = [];
  t.mock.method(globalThis, "fetch", async (url) => { reads.push(url); return Response.json({}); });
  for (const identity of [null, { role: "student", must_change_password: true, onboarding_completed: true }, { role: "student", onboarding_completed: false }]) {
    client.setApiIdentity(identity);
    client.warmRoute("profile");
    client.warmAllRoutes();
    drain();
  }
  assert.deepEqual(reads, []);
});

test("a newly restricted identity cancels queued student data reads", async (t) => {
  const { client } = await setup(t);
  const drain = fakeTimers(t);
  const reads = [];
  t.mock.method(globalThis, "fetch", async (url) => { reads.push(url); return Response.json({}); });
  client.setApiIdentity({ role: "student", onboarding_completed: true });
  client.warmAllRoutes();
  client.setApiIdentity({ role: "student", onboarding_completed: true, must_change_password: true });
  drain();
  assert.deepEqual(reads, []);
});

test("parent prefetch is limited to current parent routes", async (t) => {
  const { client } = await setup(t);
  const drain = fakeTimers(t);
  const reads = [];
  t.mock.method(globalThis, "fetch", async (url) => { reads.push(url); return Response.json({}); });
  client.setApiIdentity({ role: "parent", needs_child_setup: false });
  client.warmAllRoutes();
  client.warmRoute("profile");
  drain();
  assert.deepEqual(new Set(reads), new Set(["/api/v1/parent/students", "/api/v1/auth/me"]));
});

test("student profile warms sharing controls without retired or parent endpoints", async (t) => {
  const { client } = await setup(t);
  const reads = [];
  t.mock.method(globalThis, "fetch", async (url) => { reads.push(url); return Response.json({}); });
  client.setApiIdentity({ role: "student", onboarding_completed: true });
  client.warmRoute("profile");
  client.warmRoute("parent");
  assert.deepEqual(new Set(reads), new Set(["/api/v1/auth/me", "/api/v1/dna", "/api/v1/student/parent-links"]));
});
