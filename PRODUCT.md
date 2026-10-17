# NOVI — Product Map & Flow of Work

**NOVI · The Operating System for Student Success.** Your AI mentor. Your journey. Your future.

This document is the single source of truth for what NOVI does, how every spec section maps
to real endpoints and screens, and how data flows through the system. When this doc says a
feature is implemented, it is implemented — wired end-to-end and verified live.

---

## 1. System at a glance

| Layer | Technology | Notes |
|---|---|---|
| API + product logic | FastAPI (Python 3.12) | `backend/app/` |
| Data | MySQL (`novi_db`) via SQLAlchemy | `backend/app/models/` |
| AI orchestration | `NoviEngine` | Gemini primary → local Ollama (`llama3.2:3b`) fallback with 600s quota cooldown |
| Long-term student memory | Letta (`localhost:8283`) | 4-year memory, grade 9 → 12, tagged per school year |
| Frontend | Single-page app (vanilla JS) | `frontend/` — served by FastAPI at `/` |

Core message every screen reinforces: **KNOW YOURSELF · BUILD YOUR FUTURE · GET THERE**.

---

## 2. The 4-year journey (the "flow of work")

Every student follows this loop. Each stage is a working screen + endpoint; completing a stage is
persisted and drives the next stage.

```
Signup → Complete profile → Build Career DNA → Discover careers → Set a goal
   → Generate roadmap → Start passport → Check university readiness → Weekly check-ins
        → Dashboard "Today's focus" + Novi Says → Letta memory keeps learning
```

| # | Step | Endpoint | Screen | What makes it "done" |
|---|---|---|---|---|
| 1a | Parent signs up | `POST /auth/parent/register` | Parent signup | Parent JWT + `needs_child_setup`; name/email/password only (or Google) |
| 1b | Parent adds child | `POST /parent/students` | Add child | Student + active basic link in one transaction; temporary password; parent session unchanged |
| 1c | Child signs in | `POST /auth/login` | Student login | Existing student JWT; temporary accounts restricted server-side |
| 1d | Child chooses personal password | `POST /auth/change-password` | First login | Different password, replacement JWT, old token/version invalidated |
| 1e | Student onboarding | `GET /onboarding/flow`, `POST /onboarding/flow/answer` | Onboarding | Parent-entered name prefilled; complete the existing 15-step engine |
| 2 | Complete profile | `PATCH /auth/me` | Profile | first_name + school + grade set |
| 3 | Build Career DNA | `GET/PATCH /dna`, `POST /dna/refresh`, `POST /dna/reflect` | My DNA | `dna_filled = true`; reflection confirmed with "Yes, that's me" |
| 4 | Discover careers | `POST /careers/match` | Careers | ≥1 stored `CareerMatch`; top match archived to memory |
| 5 | Set a goal | `POST /roadmap/goals` | Roadmap | ≥1 live goal |
| 6 | Generate roadmap | `POST /roadmap/generate` | Roadmap | `RoadmapItem`s exist across grades 9–12 |
| 7 | Start passport | `POST /passport/items` | Passport | ≥1 passport item; completion % computed |
| 8 | University readiness | `POST /universities/readiness` | University detail | ≥1 stored readiness assessment |
| 9 | Weekly check-in | `POST /checkins`, `/checkins/summarize` | Check-in | ≥1 answered week |

The **Onboarding endpoint** (`GET /onboarding`) computes all 8 flags above and powers the
"Your journey" progress card on the dashboard. `GET /dashboard` bundles today's focus,
progress %, career matches, goals, roadmap, priorities, passport and check-in status.

---

## 3. Feature map — spec section → implementation

### 1 · Homepage / brand promise
- **Auth screen hero** renders the brand promise: *"Your AI mentor. Your journey. Your future."*
- **Endpoints**: `POST /auth/parent/register`, `POST /auth/login`, `GET /auth/me`
- Signup is for parents. Students log into accounts their parents created; existing student logins continue working.
- **Trust indicators** ("Personalized AI Mentor · 4-Year Journey · Career + University Guidance") = the product itself: memory (§5), roadmap stages (§9), DNA/readiness (§§8,7).

### 2 · How Novi works — the 4-year journey
- **Endpoints**: `GET /roadmap` (grade-by-grade stages), `GET /memory` (per-school-year timeline).
- Stages map 1:1 to `GRADE_STAGE` in `backend/app/services/roadmap.py`:
  Grade 9 *Discover Yourself →* 10 *Explore & Experiment →* 11 *Build Your Profile →* 12 *Apply With Confidence*.

### 3 · For students
- **Endpoints**: every student endpoint below (§§4–12); all surfaced in one SPA.
- "Not sure what career you want?" → §4 · "Which subjects/universities?" → §6 · "How to build a profile?" → §10.

### 4 · Career discovery
- `GET /careers` (search by q/category), `GET /careers/categories`, `GET /careers/matches` (stored),
  `POST /careers/match` (AI: interests, strengths, personality, subjects, skills, goals → scored list ≥55).
- Deterministic keyword-fallback if the LLM is unavailable. Top match is archived to Letta memory.

### 5 · Career detail page
- `GET /careers/{slug}` — description, *what they actually do*, skills (What you'll need),
  subjects/degrees (*what you should study*), industries (*where this could take you*), future paths.
- `GET /careers/{slug}/advice` — **NEW**:
  - `fit_statement`: personalized *"Why Novi thinks this could fit you"* (references the student's own DNA),
  - `fit_rating` + `reasons` (from any stored match),
  - `next_steps`: 3 concrete actions, typed `project | skill | explore`, each linked to a real screen
    (`passport | roadmap | universities | careers`).

### 6 · University explorer
- `GET /universities` (with `country`/`subject` filters), `GET /universities/filters`,
  `GET /universities/recommended` (readiness-ranked picks for this student).

### 7 · University detail
- `GET /universities/{slug}` — about, entry requirements, fees, scholarships, strengths.
- `POST /universities/readiness` — readiness %, strengths ✅, improvements ⚠️, and exactly 3
  *"Next steps"* (the spec's *Next 3 Recommendations*).

### 8 · Career DNA
- `GET /dna` (living picture), `PATCH /dna` (edit), `POST /dna/refresh` (re-learn from chats),
  `POST /dna/reflect` — **NEW**: accepts `{"accepted": true}` ("Yes, that's me") or
  `{"accepted": false, "feedback": "…"}` ("Not quite"), locks/unlocks DNA and archives the
  feedback to memory. Section traits/motivations/strengths/development areas/career zones/reflection all stored.
- **Corrections, not just additions** — the DNA is *living*: when a student says "I don't like
  coding much, I love cloud engineering", the refresh engine removes coding from interests/
  subjects/skills/career-zones and adds cloud engineering, rather than keeping both. Enforcement:
  (1) the extraction prompt treats dislikes/preferences as corrections, (2) a deterministic
  `revoked_terms`+`prune` backstop drops any clearly-canelled topic even if the LLM forgets,
  (3) a "focus shift" fact is archived to Letta memory and the live profile line is synced, so
  the mentor's memory matches the student's *current* self.

### 9 · AI Roadmap
- Goals: `POST|GET /roadmap/goals`, `PATCH /roadmap/goals/{id}` (done/cancelled).
- Roadmap: `POST /roadmap/generate` (4–6 steps per grade), `GET /roadmap`, `PATCH /roadmap/items/{id}` (complete).
- This week's priorities: `GET /roadmap/priorities`, `POST /roadmap/priorities/generate` (build/explore/grow),
  `PATCH /roadmap/priorities/{id}`. Tasks: `POST|GET /roadmap/tasks`, `PATCH /roadmap/tasks/{id}`.
- Goal, plan, completions and tasks are archived to Letta memory as milestones.

### 10 · Career Passport
- `GET /passport`, `POST /passport/items`, `PATCH|DELETE /passport/items/{id}`,
  `GET /passport/completion` → overall % + per-category % + *"what would make it stronger"* +
  **DNA-aware suggestion**: the next item is framed around the student's top career zone
  ("Add your first project — a *cloud engineering* build…") plus a `novi_note` that explains
  how to tell one coherent story with their passport.
- Categories exactly per spec: projects · competitions · certifications · leadership · research · activities.
- Every add/update is archived to memory.

### 11 · Weekly check-in
- `GET /checkins/current` , `GET /checkins` (history), `POST /checkins` (answers: accomplishments,
  learnings, challenges, pride, next week, mood, energy), `POST /checkins/summarize` → wins, new skills,
  milestones, priorities-next-week **+ `dna_alignment`** — the summary now ties the student's week
  back to their stated Career DNA goals (LLM with a deterministic fallback).
- Summary + wins/learnings are archived as memory milestones.

### 11.5 · Everything speaks your DNA (sections are DNA-grounded)
- New `GET /dna/context` → compact snapshot (grade, career zones, goals, interests, subjects,
  skills, `filled`). Every student section renders a **"Based on your Career DNA"** bar (with a
  `View DNA →` deep link) on Careers, career detail, Universities, university detail, Roadmap,
  Passport and Check-in.
- Universities: `GET /universities/recommended` is now **DNA-ranked** — deterministic scoring of
  every university's course/subject/strengths/about against the student's career zones, goals,
  interests, subjects and skills (weighted), with a human-readable `reason` per recommendation,
  plus an estimated readiness, no LLM latency. Falls back to recent readiness checks if DNA is empty.

### 12 · Student dashboard
- `GET /dashboard` — greeting ("Good morning, Riya 👋"), **today's focus + why**,
  **progress** (career direction, profile strength, university readiness, roadmap %),
  **Novi Says** + action hook, career matches, roadmap/goals, passport, check-in, next task.
- `GET /onboarding` — the 8-step **Your journey** card with a "Next step →" deep link.

### 13 · Parent homepage / dashboard
- `POST /parents/link` (link a child by email), `GET /parents/dashboard` — per-child: career
  direction, profile strength, university readiness, **This month's focus**, *Parent insight*.

### 14 · Parent AI advisor
- `POST /parents/advisor` — asks Novi with full child context (progress, readiness, top career);
  calm, concrete, constructive, non-intrusive.

### 15 · Final CTA
- Parent signup and student login share form logic. Registration leads to Add child;
  student login leads to password change if required, then onboarding, then the student home.

### 16 · Novi's voice
- Encoded in `NOVI_PERSONA` (`backend/app/llm/prompts.py`): friendly, smart-but-never-complicated,
  encouraging, honest, curious, proactive, personal.

### 17 · UX rule (never a counsellor)
- Enforced in prompts (`NOVI_PERSONA` HARD RULE) and the career-advice prompt: prescribe *projects*,
  not *extracurricular activities*; celebrate progress instead of reporting weaknesses.

### 18 · Core product message
- `CORE_MESSAGE` is appended to every AI system prompt: KNOW YOURSELF · BUILD YOUR FUTURE · GET THERE.

---

## 4. Letta memory — every feature feeds the mentor

| Feature action | Archived into Letta (tagged per school year) |
|---|---|
| Any chat | Extracted durable facts + live profile update (`human` block + archival) |
| Career DNA update/refresh | Core profile sync + career-focus fact + reflection feedback |
| Goal created / roadmap generated / step or task completed | Goal, plan, milestone facts |
| Career match run | Top match + fit % |
| Passport item added/updated | Achievement record |
| Weekly check-in saved / summarized | Wins, learnings, milestones |
| University readiness checked | University + course + readiness |

`GET /api/v1/memory` returns the whole timeline grouped by school year (e.g. `sy2026-27`)
so the 4-year history is retrievable in one call. Recall is injected into every chat so the
mentor genuinely *remembers* across sessions.

**AI resilience:** `NoviEngine` tries Gemini first; on quota/latency failure it falls back to
local Ollama and stops retrying the dead key for 600s. Verified: all AI features return real
output even at 0 Gemini quota.

---

## 5. Completeness checklist

- [x] All 18 spec sections implemented and mapped (above)
- [x] 25+ live API endpoints across 12 routers (see `/docs`, OpenAPI)
- [x] 15-step student onboarding engine and dashboard journey progress card
- [x] Career detail: AI fit statement + 3 linked next steps
- [x] DNA reflection feedback ("Yes, that's me" / "Not quite")
- [x] RSS-style memory: every feature writes to the 4-year Letta memory; `/memory` timeline
- [x] Gemini outage-safe: Ollama fallback proven with quota simulated at 0
- [ ] Live browser smoke of the current parent-first flow on the deployment target
- [x] Parent-first backend chain verified in isolated tests; MySQL legacy migration rehearsed
- [ ] Provider credentials and HTTPS Google callback checked in the target environment

---

## 6. Run & verify

See [SETUP.md](SETUP.md) for local/Docker setup, test commands and the deployment
order: back up DB -> run migrations -> deploy backend -> deploy frontend.
The app runs on Next.js port 3000; API docs are on FastAPI port 8000.
Do not use published/shared demo credentials; create a disposable family for testing.

### Auth and sharing contract

- Passwords: minimum 8 characters, maximum 72 UTF-8 bytes. No plaintext password
  appears in child responses or is persisted by the frontend.
- Identity includes `must_change_password`, `needs_child_setup`, and
  `has_local_password`. Google-only/unknown local-password provenance hides the
  local change form. A verified Google login invalidates a parent-set temporary
  credential and old tokens before onboarding.
- New public student signup is disabled. Google cannot auto-create students.
  Existing student/Google accounts and legacy link choices are preserved.
- Legacy creation endpoints return 410. Legacy pending approval is allowed only
  explicitly, before invitation expiry; revoked links cannot be reactivated.
- `token_version=0` is the migration default; legacy unversioned JWTs mean 0.
  Existing users are not forced through a first-login password reset.
- `TRUSTED_PROXY_HOSTS` defaults empty; only configured proxy peers may supply
  forwarded client IPs. Login/signup/child creation are rate-limited in memory,
  per process; multiple workers require shared/ingress enforcement.
- No parent endpoint or advisor gets raw chats, check-in text or Letta memory.

## 7. Key files

| Area | Files |
|---|---|
| Memory + agents | `backend/app/llm/{letta.py,memory.py}` |
| AI engine | `backend/app/llm/engine.py` · `services/providers.py` |
| Prompts (voice/UX) | `backend/app/llm/prompts.py` |
| Onboarding engine | `backend/app/routers/onboarding.py` · `app/onboarding/steps.py` (15 steps) |
| Feature services | `backend/app/services/{career_dna,careers,universities,roadmap,passport,checkins,dashboard,parents,student_context}.py` |
| API routers | `backend/app/api/` · router map in `api/router.py` |
| Frontend | `frontend/app/` (Next.js) · `frontend/src/views/` · `frontend/src/speech.js` (TTS) |