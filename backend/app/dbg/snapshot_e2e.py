"""End-to-end verifier for the Career DNA snapshot timeline.

Runs against the LIVE uvicorn API (auth real student -> freeze DNA -> save a
snapshot -> years pass -> save another -> asserts the *delta* (the gradual
progress) -> rename label/note -> list -> delete). Exits nonzero if any step
misbehaves.
"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"
TOKEN = None


def call(method, path, body=None, token=None, expect=200):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        resp = urllib.request.urlopen(req, data)
        raw = resp.read().decode()
        status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        status = e.code
        if status >= 500:
            print(f"!! {method} {path} -> {status}: {raw[:240]}")
            raise
    parsed = json.loads(raw) if raw.strip() else None
    ok = status == expect
    print(
        f"[{method:6}] {path:38} -> {status}"
        + ("" if ok else f"   EXPECTED {expect}  BODY: {raw[:160]}")
    )
    if not ok:
        raise SystemExit(1)
    return parsed if raw.strip() else None


def main():
    global TOKEN

    # --- register a brand-new student (fresh user, so we own the timeline) ---
    import os

    email = f"snap_{os.urandom(4).hex()}@novi.app"
    reg = call(
        "POST",
        "/auth/signup",
        {"email": email, "password": "Snapshot!42", "name": "DNA Snapshot QA", "role": "student"},
    )
    TOKEN = reg.get("token") or reg.get("access_token") or (reg.get("user") or {}).get("token")
    assert TOKEN, f"no token in register: {reg}"

    # --- step 1: tell Novi a bit (magic) so DNA gets real content ---
    magic = call(
        "POST",
        "/dna/magic",
        {
            "text": "I'm age 14. I love building robots, I'm strong at coding and "
            "chemistry, I want to design things that help people, and I'm curious "
            "about AI. I keep a lot of interests."
        },
        token=TOKEN,
    )
    assert magic.get("dna_filled") or magic.get("traits"), f"magic: {magic}"

    snap_label1 = call(
        "POST",
        "/dna/snapshots",
        {"label": "My DNA at 14", "note": "The curious kid who loves robots"},
        token=TOKEN,
    )[-1]  # the API returns the full timeline; the new one is the newest
    snap1 = snap_label1

    # --- step 3: years pass; DNA drifts (magic again -> adds new interests) ---
    magic2 = call(
        "POST",
        "/dna/magic",
        {
            "text": "Age 19 now. Programming is my thing, data science and machine "
            "learning excite me, I work on public speaking and I'm aiming toward a "
            "career in applied AI. Robotics still matters but I've moved on from "
            "chemistry."
        },
        token=TOKEN,
    )

    # --- step 4: save the second snapshot (the "gradual progress" step) ---
    snap2 = call(
        "POST",
        "/dna/snapshots",
        {"label": "My DNA at 19", "note": "The data-driven young adult"},
        token=TOKEN,
    )[-1]  # the API returns the full timeline; the new one is the newest

    # --- step 5: list -> verify delta shows exactly the gradual changes ---
    snaps = call("GET", "/dna/snapshots", token=TOKEN)
    assert len(snaps) == 2, f"expected 2 snapshots, got {len(snaps)}: {snaps}"
    newest = next((s for s in snaps if s.get("id") == snap2.get("id")), None)
    delta = newest.get("delta") or {}
    added = {k: v for k, v in delta.items() if k.endswith("_added") and v}
    removed = {k: v for k, v in delta.items() if k.endswith("_removed") and v}
    assert any(k.startswith("interests") for k in added), f"no interest delta: {delta}"
    print("  = delta (age 14 -> 19) =")
    for k in ("interests", "skills", "subjects", "subject_flags", "career_zones", "values"):
        if added.get(k + "_added"):
            print(f"    +{k}: {added[k+'_added'][:5]}")
        if removed.get(k + "_removed"):
            print(f"    -{k}: {removed[k+'_removed'][:5]}")

    # --- step 6: edit label+note years later (update) ---
    patched = call(
        "PATCH",
        f"/dna/snapshots/{snap1['id']}",
        {"label": "My DNA at 14 (retro workshop)", "note": "revisited before uni"},
        token=TOKEN,
    )
    me = next((s for s in patched if s.get("id") == snap1["id"]), None)
    assert me and me.get("label") == "My DNA at 14 (retro workshop)", f"update: {me}"

    # --- step 7: delete the stale one (timeline stays clean for years) ---
    call("DELETE", f"/dna/snapshots/{snap1['id']}", token=TOKEN, expect=200)
    after = call("GET", "/dna/snapshots", token=TOKEN)
    assert len(after) == 1, f"delete left {after}"

    print("\n[PASS] snapshot save / list / delta / update / delete all green")


if __name__ == "__main__":
    main()
