# Cozy Lead Engine v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Cozy Traffic into an independent Render service and dedicated Telegram control bot with persistent admin notifications.

**Architecture:** Reuse the existing traffic runtime/scoring/storage modules, add a dedicated process entrypoint, extend the manager with admin registration/new-lead notification, and remove Traffic installation from Villa bot. Deploy the same repository twice with different start commands.

**Tech Stack:** Python 3, python-telegram-bot 21.x, Telethon, gspread, Render, Google Sheets.

**Spec:** `docs/superpowers/specs/2026-09-16-cozy-lead-engine-v1-design.md`

## Global Constraints

- Third-party Telegram access remains read-only in V1.
- No secrets in GitHub or Google Sheets.
- Authorized admin username defaults to `Cozy_asia`.
- Monitor interval is 900 seconds in production.
- QZR Manager outbound messaging is out of V1 scope.

---

### Task 1: Dedicated Lead Engine entrypoint

**Files:**
- Create: `lead_engine_main.py`
- Test: `test_lead_engine_main.py`

**Interfaces:**
- Consumes: `cozy_catalog`, `cozy_traffic_runtime`, scoring/discovery patches, `cozy_traffic_manager.install(app, catalog)`.
- Produces: a process started with `python lead_engine_main.py` using `COZY_LEAD_BOT_TOKEN`.

- [ ] Write tests verifying the entrypoint requires `COZY_LEAD_BOT_TOKEN`, applies both traffic patches, installs the manager, starts an HTTP health server, and uses Telegram polling.
- [ ] Run the tests and confirm they fail before implementation.
- [ ] Implement the minimal entrypoint with a daemon `ThreadingHTTPServer` bound to `$PORT` and `Application.run_polling()`.
- [ ] Run the tests and confirm they pass.
- [ ] Commit.

### Task 2: Persistent admin registration and lead notifications

**Files:**
- Modify: `cozy_traffic_manager.py`
- Create: `test_cozy_traffic_notifications.py`

**Interfaces:**
- Produces: `LeadEngineConfig` worksheet with `key,value,updated_at`; `/start` records `admin_chat_id`; `_save_opportunities` returns newly-created lead objects/rows in addition to counts; daemon notifies only newly-created leads.

- [ ] Write regression tests for authorized `/start`, persisted chat ID, notification formatting, and no notification on duplicates.
- [ ] Verify tests fail on current code.
- [ ] Add config worksheet helpers and `/start` handler.
- [ ] Return newly-created opportunities from persistence without changing deduplication semantics.
- [ ] Send compact lead cards to the saved admin chat from the monitor; catch/log notification errors without stopping scanning.
- [ ] Verify tests pass.
- [ ] Commit.

### Task 3: Remove Traffic Engine from Villa bot

**Files:**
- Modify: `main.py`
- Create: `test_villa_bot_traffic_separation.py`

**Interfaces:**
- Villa bot continues to delegate to `main_legacy` only.

- [ ] Add a regression test asserting `main.py` does not import/install traffic modules or start traffic smoke/monitor.
- [ ] Verify it fails.
- [ ] Replace `main.py` with the historical wrapper that imports `main_legacy` and calls `_entry.main()` only.
- [ ] Verify the separation test passes.
- [ ] Commit.

### Task 4: Repository verification and merge

**Files:**
- No new production files.

- [ ] Inspect branch diff against `main` and confirm only Lead Engine separation/notification changes plus docs/tests are present.
- [ ] Verify no token-like credentials were committed.
- [ ] Fast-forward `main` to the verified branch.
- [ ] Wait for existing `Cozyasia_villas` auto-deploy and verify its logs no longer show `cozy-traffic-manager` installation or monitor startup.

### Task 5: Create Render Lead Engine service

**Files:**
- Render configuration only.

- [ ] Create `Cozy-Lead-Engine` in Singapore from `Cozyasia/Cozyasia_villas`, branch `main`, build `pip install -r requirements.txt`, start `python lead_engine_main.py`.
- [ ] Set non-secret traffic settings at creation where possible.
- [ ] Have the user add required secret environment variables in Render, especially the new `COZY_LEAD_BOT_TOKEN`.
- [ ] Set `COZY_TRAFFIC_MONITOR=0` on `Cozyasia_villas` and `COZY_TRAFFIC_MONITOR=1` on `Cozy-Lead-Engine`.
- [ ] Verify Lead Engine logs, `/start`, monitor startup, and health endpoint.
- [ ] Run one `/traffic_scan` from the new bot and verify TrafficOpportunities continues using the existing shared sheet.
