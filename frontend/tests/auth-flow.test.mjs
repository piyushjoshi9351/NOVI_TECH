import assert from "node:assert/strict";
import test from "node:test";
import { ADD_CHILD, FIRST_LOGIN, destinationFor, googleDestination, passwordError, passwordSettingsMessage, redirectFor, safeNext } from "../src/authFlow.js";

const parent = { role: "parent", needs_child_setup: false };
const student = { role: "student", onboarding_completed: true, must_change_password: false };
const route = (user, pathname, extra = {}) => redirectFor({ token: "test-token", user, pathname, ...extra });

test("new passwords enforce character count and UTF-8 bytes", () => {
  assert.ok(passwordError("short"));
  assert.equal(passwordError("password"), "");
  assert.equal(passwordError("\u00e9".repeat(36)), "");
  assert.ok(passwordError("\u00e9".repeat(37)));
  assert.ok(passwordError("x".repeat(73)));
  assert.ok(passwordError("\u{1f600}".repeat(7)));
  assert.equal(passwordError("\u{1f600}".repeat(8)), "");
  // Existing credentials remain usable; every replacement uses the new rules.
  assert.equal(passwordError("oldpass", true), "");
  assert.ok(passwordError("" , true));
});

for (const next of ["https://evil.example/", "//evil.example", "/\\evil.example", "/%2f%2fevil.example", "/api/v1/auth/me", "/signup", "/login?next=/parent", "/dashboard?google_token=secret", "/dashboard%0a", "javascript:alert(1)"]) {
  test(`unsafe return destination is rejected: ${next}`, () => {
    assert.equal(safeNext(next), "");
    assert.equal(destinationFor(parent, next), "/parent");
    assert.equal(destinationFor(student, next), "/dashboard");
  });
}

test("role boundaries also apply to return destinations", () => {
  assert.equal(safeNext("/parent/12", "parent"), "/parent/12");
  assert.equal(safeNext("/parent/12", "student"), "");
  assert.equal(safeNext("/chat", "parent"), "");
  assert.equal(destinationFor(parent, "/parent/add-child"), ADD_CHILD);
  assert.equal(destinationFor(student, "/careers?category=STEM"), "/careers?category=STEM");
});

test("unauthenticated users go to login with a safe return path", () => {
  assert.equal(redirectFor({ token: null, user: null, pathname: "/passport" }), "/login?next=%2Fpassport");
  assert.equal(redirectFor({ token: "stale", user: null, pathname: "/parent" }), "/login?next=%2Fparent");
});

test("password change precedes onboarding and wrong-role redirects", () => {
  const temporary = { ...student, must_change_password: true, onboarding_completed: false };
  assert.equal(destinationFor(temporary), FIRST_LOGIN);
  assert.equal(destinationFor(temporary, "/chat"), "/first-login?next=%2Fchat");
  assert.equal(route(temporary, "/onboarding"), FIRST_LOGIN);
  assert.equal(route(temporary, "/parent", { requiredRole: "parent" }), FIRST_LOGIN);
  assert.equal(route(temporary, FIRST_LOGIN), "");
});

test("password replacement continues through onboarding before the requested route", () => {
  const incomplete = { ...student, onboarding_completed: false };
  assert.equal(destinationFor(incomplete, "/passport"), "/onboarding?next=%2Fpassport");
  assert.equal(route(incomplete, FIRST_LOGIN, { search: "next=%2Fpassport" }), "/onboarding?next=%2Fpassport");
  assert.equal(route(incomplete, "/onboarding", { search: "next=%2Fpassport" }), "");
  assert.equal(route(student, "/onboarding", { search: "next=%2Fpassport" }), "/passport");
  assert.equal(route(student, FIRST_LOGIN), "/dashboard");
});

test("parents without a child resume Add child before requested destinations", () => {
  const setup = { ...parent, needs_child_setup: true };
  assert.equal(destinationFor(setup), ADD_CHILD);
  assert.equal(destinationFor(setup, "/parent/42"), "/parent/add-child?next=%2Fparent%2F42");
  assert.equal(route(setup, "/parent"), "/parent/add-child?next=%2Fparent");
  assert.equal(route(setup, ADD_CHILD), "");
  assert.equal(route(parent, ADD_CHILD), ""); // Multiple children remain possible.
  assert.equal(destinationFor(parent, "/parent/42"), "/parent/42");
});

test("completed accounts use role home when entering the other area", () => {
  assert.equal(route(student, "/parent", { requiredRole: "parent" }), "/dashboard");
  assert.equal(route(parent, "/chat", { requiredRole: "student" }), "/parent");
  assert.equal(route(parent, "/parent/settings"), "");
});

test("logging back in during setup preserves the original safe destination", () => {
  const temporary = { ...student, must_change_password: true, onboarding_completed: false };
  assert.equal(destinationFor(temporary, "/first-login?next=%2Fpassport"), "/first-login?next=%2Fpassport");
  assert.equal(destinationFor(student, "/onboarding?next=%2Fpassport"), "/passport");
  assert.equal(destinationFor({ ...parent, needs_child_setup: true }, "/parent/add-child?next=%2Fparent%2F42"), "/parent/add-child?next=%2Fparent%2F42");
  assert.equal(destinationFor(student, "/first-login?next=https%3A%2F%2Fevil.example"), "/dashboard");
});

test("password settings are only shown for a confirmed local password", () => {
  assert.equal(passwordSettingsMessage({ has_local_password: true }), "");
  assert.match(passwordSettingsMessage({ has_local_password: false }), /Google/);
  assert.match(passwordSettingsMessage({ has_local_password: null }), /not been confirmed/);
  assert.match(passwordSettingsMessage({}), /not been confirmed/);
});

test("Google callback waits for current identity and skips cleared first-login restriction", async () => {
  let complete;
  const identity = new Promise((resolve) => { complete = resolve; });
  let usedToken;
  let finished = false;
  const destination = googleDestination("google-jwt", (token) => { usedToken = token; return identity; }, "/passport");
  destination.then(() => { finished = true; });
  await Promise.resolve();
  assert.equal(usedToken, "google-jwt");
  assert.equal(finished, false);
  complete({ ...student, onboarding_completed: false, must_change_password: false, has_local_password: false });
  assert.equal(await destination, "/onboarding?next=%2Fpassport");
  assert.equal(await googleDestination("parent-jwt", async () => ({ ...parent, needs_child_setup: true })), ADD_CHILD);
});
