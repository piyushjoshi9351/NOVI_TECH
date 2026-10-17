import assert from "node:assert/strict";
import test from "node:test";
import { ACCOUNT_STATES, accountState, isActive, isPending, isParentCreated, isRevoked, STATUS_LABEL, SCOPES } from "../src/parentAccess.js";

test("parent-created connections are immediately active, not pending", () => {
  const link = { status: "active", activation_source: "parent_created", account_state: "awaiting_first_login" };
  assert.ok(isActive(link) && isParentCreated(link));
  assert.equal(isPending(link), false);
  assert.equal(STATUS_LABEL.active, "Connected");
  assert.equal(accountState(link).label, "Awaiting first login");
});

test("legacy pending and revoked rows have distinct labels", () => {
  assert.ok(isPending({ status: "pending" }));
  assert.ok(isRevoked({ status: "revoked" }));
  assert.match(STATUS_LABEL.pending, /Legacy/);
  assert.equal(STATUS_LABEL.revoked, "Access removed");
});

test("lifecycle labels cover creation, first login, onboarding and active", () => {
  assert.deepEqual(Object.keys(ACCOUNT_STATES), ["account_created", "awaiting_first_login", "onboarding_in_progress", "active"]);
  for (const state of Object.keys(ACCOUNT_STATES)) assert.ok(accountState({ account_state: state }).detail);
  assert.equal(accountState({}).label, "Account created");
  assert.equal(SCOPES.find((scope) => scope.id === "basic").locked, true);
  assert.match(SCOPES.find((scope) => scope.id === "memory").blurb, /stay private/);
});
