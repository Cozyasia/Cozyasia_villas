# Cozy Lead Engine Repository Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the working Cozy Lead Engine from `Cozyasia/Cozyasia_villas` into the new private repository `Cozyasia/cozy-lead-engine`, preserve all shared production state, and repoint the existing Render `Cozy-Lead-Engine` service only after independent verification.

**Architecture:** Start from the verified Villa-repo baseline `b9eb4f90149b198a36c63b1ae983c226b36b2df8`, copy only Lead Engine responsibilities into the private repository, then replace the two Villa-specific dependencies (`cozy_catalog` and publishing-heavy `mtproto_user_client`) with focused adapters. Keep the flat module layout during migration, keep `COZY_LEAD_CONTACT_MODE=dry_run`, and do not remove source files from `Cozyasia_villas` until the new deployment passes acceptance tests.

**Tech Stack:** Python 3, python-telegram-bot 21.6, Telethon 1.x, gspread 6.x, Google Auth, OpenAI Python 1.x, cryptography/Fernet, Render, Google Sheets.

**Spec:** `docs/superpowers/specs/2026-09-17-cozy-lead-engine-repository-extraction-design.md`

## Global Constraints

- Target repository is private: `Cozyasia/cozy-lead-engine`.
- Source baseline is `Cozyasia/Cozyasia_villas@b9eb4f90149b198a36c63b1ae983c226b36b2df8`.
- `COZY_LEAD_CONTACT_MODE=dry_run` for the entire migration.
- No LIVE SEND enablement or third-party Telegram message is part of this plan.
- Existing Google Sheet and worksheet names stay authoritative; no state migration to a new spreadsheet.
- No tokens, Telegram session plaintext, Google credentials, OpenAI keys, or Render secrets may be committed.
- Existing `Cozyasia_villas` Render service and `gpt5pro-bot` remain unchanged during extraction.
- Existing `Cozy-Lead-Engine` Render service is not repointed until the private repository passes independent tests.
- Source discovery/scanning remains read-only toward third-party Telegram chats.

---

### Task 1: Create and isolate the private repository

**Files:**
- Create in target: `README.md`
- Create in target: `.gitignore`
- Create in target: `docs/source-baseline.md`

**Interfaces:**
- Consumes: verified source commit `b9eb4f90149b198a36c63b1ae983c226b36b2df8`.
- Produces: private repository `Cozyasia/cozy-lead-engine`, default branch `main`, implementation branch `migration/lead-engine-extraction`.

- [ ] Create `Cozyasia/cozy-lead-engine` with visibility **Private** and initialize it with a README only.
- [ ] Create branch `migration/lead-engine-extraction` from `main`; all extraction work must go to this branch until verification passes.
- [ ] Write `docs/source-baseline.md` with the exact source repository, source commit SHA, migration date, and rollback baseline.
- [ ] Add `.gitignore` entries for `.env`, `.env.*`, `*.session`, `*.session-journal`, `__pycache__/`, `.pytest_cache/`, `.venv/`, `venv/`, and local credential JSON files.
- [ ] Verify repository visibility is private and no secrets exist in the initial tree.

### Task 2: Seed the current Lead Engine slice without behavior changes

**Files:**
- Copy unchanged from source baseline:
  - `lead_engine_main.py`
  - `lead_engine_control.py`
  - `lead_engine_selftest.py`
  - `lead_contact_dry_run.py`
  - `lead_contact_flow.py`
  - `lead_draft_store.py`
  - `ai_manager_auth.py`
  - `cozy_traffic_runtime.py`
  - `cozy_traffic_manager.py`
  - `cozy_traffic_discovery_patch.py`
  - `cozy_traffic_scoring_patch.py`
- Copy tests unchanged:
  - `test_ai_manager_auth.py`
  - `test_cozy_traffic_discovery_patch.py`
  - `test_cozy_traffic_runtime.py`
  - `test_cozy_traffic_scoring_patch_v2.py`
  - `test_lead_contact_dry_run.py`
  - `test_lead_contact_flow.py`
  - `test_lead_draft_store.py`
  - `test_lead_engine_ai_manager_auth.py`
  - `test_lead_engine_control.py`
  - `test_lead_engine_dry_run_wiring.py`
  - `test_lead_engine_logging.py`
  - `test_lead_engine_main.py`
  - `test_lead_engine_selftest.py`
  - `tests/test_lead_safety_guards.py`

**Interfaces:**
- Produces: an auditable byte-for-byte starting point for current Lead Engine production modules/tests before dependency extraction.

- [ ] Fetch every listed file from source commit `b9eb4f9...`, not from a moving branch tip.
- [ ] Create the same paths in target branch `migration/lead-engine-extraction` with unchanged content.
- [ ] Compare SHA/content for copied files and record mismatches as failures.
- [ ] Do not copy Villa publishing scripts, publication assets, post layout modules, Facebook automation, premium emoji modules, `main_legacy.py`, or `gpt5pro-bot` code.
- [ ] Commit the exact baseline slice before adapter changes.

### Task 3: Add a focused Google Sheets adapter

**Files:**
- Create: `lead_sheets.py`
- Modify: `lead_engine_main.py`
- Modify callers only where required by the proven interface.
- Test: `test_lead_sheets.py`
- Update: `test_lead_engine_main.py` if import expectations change.

**Interfaces:**
- `lead_sheets.SHEET_ID: str` reads `GOOGLE_SHEET_ID`.
- `lead_sheets._client()` returns an authorized `gspread.Client` built from `GOOGLE_CREDS_JSON`.
- Existing manager/control/auth modules continue to receive one catalog-like object exposing `SHEET_ID` and `_client()`.

- [ ] Write failing tests proving missing/invalid `GOOGLE_CREDS_JSON` fails clearly and valid service-account JSON is passed to Google credentials/gspread without logging the JSON.
- [ ] Run only `test_lead_sheets.py` and verify failure before implementation.
- [ ] Implement `lead_sheets.py` with no Villa catalogue, lot, publication, channel, or content-formatting behavior.
- [ ] Change `lead_engine_main.py` from `import cozy_catalog` to `import lead_sheets` and pass `lead_sheets` to Lead Engine control/self-test/auth installation paths.
- [ ] Run `test_lead_sheets.py`, `test_lead_engine_main.py`, `test_lead_engine_control.py`, and `test_ai_manager_auth.py` and verify they pass.
- [ ] Commit this adapter as one isolated change.

### Task 4: Add a read-only traffic MTProto adapter

**Files:**
- Create: `traffic_mtproto.py`
- Modify: `cozy_traffic_runtime.py`
- Test: `test_traffic_mtproto.py`
- Update: `test_cozy_traffic_runtime.py` for the focused import.

**Interfaces:**
- `traffic_mtproto.new_client(catalog)` loads the existing encrypted source-scanner session from the same worksheet/key and returns an authorized Telethon client.
- It reads `MT_API_ID`, `MT_API_HASH`, `MT_SESSION_KEY` and uses the existing Sheet-backed encrypted session contract.
- It exposes no Telegram write, publishing, joining, forwarding, editing, emoji, or channel-posting API.

- [ ] Write failing tests for session decrypt/load, unauthorized session rejection, expected client construction, and absence of write-oriented exported functions.
- [ ] Add an explicit static safety test that the module does not reference `send_message`, `send_file`, `forward_messages`, `edit_message`, `delete_messages`, `JoinChannelRequest`, or Villa publishing modules.
- [ ] Run tests and verify failure before implementation.
- [ ] Implement only the minimal encrypted StringSession load/client creation needed by discovery/scanning.
- [ ] Replace `mtproto_user_client._new_client(catalog)` in `cozy_traffic_runtime.py` with `traffic_mtproto.new_client(catalog)`.
- [ ] Run `test_traffic_mtproto.py`, `test_cozy_traffic_runtime.py`, discovery/scoring tests, and verify pass.
- [ ] Commit this adapter as one isolated change.

### Task 5: Reduce dependencies and document standalone operation

**Files:**
- Create/replace: `requirements.txt`
- Replace: `README.md`
- Create: `.env.example`
- Optional create: `render.yaml` only if it contains no secrets and matches the existing service start command.

**Interfaces:**
- Start command remains `python lead_engine_main.py`.
- Health endpoint remains on Render `$PORT`.
- Runtime environment remains compatible with the existing `Cozy-Lead-Engine` service variables.

- [ ] Build `requirements.txt` from imports actually used by target modules; retain pinned/compatible versions for `python-telegram-bot`, `gspread`, `google-auth`, `openai`, `telethon`, `qrcode[pil]`, and `cryptography` as required.
- [ ] Ensure Villa-only dependencies are omitted unless a retained Lead Engine import proves they are needed.
- [ ] Write `.env.example` containing variable names and safe example/blank values only; never real secrets.
- [ ] Document `dry_run` as the mandatory migration/default contact mode and document the rollback baseline.
- [ ] Document the separate roles of `@CozyLeadEngine_bot` and `@CozyAsiaAI`.
- [ ] Run a secret-pattern scan over the target tree for bot-token patterns, API keys, private keys, service-account private keys, and StringSession-like committed values.
- [ ] Commit dependency/docs changes.

### Task 6: Add migration-specific safety regression tests

**Files:**
- Create: `test_repository_separation.py`
- Create: `test_outbound_firewall.py`
- Keep: `tests/test_lead_safety_guards.py`

**Interfaces:**
- Produces a test-enforced separation contract between Lead Engine and Villa publishing code.

- [ ] Write a repository-separation test that fails if target production modules import `cozy_catalog`, `mtproto_user_client`, `post_layout_*`, channel publication modules, `main_legacy`, or Facebook/publication automation.
- [ ] Write an outbound-firewall test that monkeypatches/mock-blocks Telethon outbound methods (`send_message`, `send_file`, `forward_messages`) and proves `/traffic_recipient_test` and dry-run approval paths do not invoke them.
- [ ] Include the existing placeholder retry/block regression suite unchanged.
- [ ] Run all migration-specific tests and verify pass.
- [ ] Commit safety tests.

### Task 7: Full independent verification on the migration branch

**Files:**
- No new production files unless a failing test reveals a migration defect.

**Interfaces:**
- Produces: branch eligible for review/merge, but does not change Render.

- [ ] Run `python -m compileall` over production modules.
- [ ] Run the complete copied/extraction test suite with `python -m unittest discover -v` (and any pytest invocation required by the existing test layout).
- [ ] Verify every retained source-scanning code path is read-only toward third-party chats.
- [ ] Verify `COZY_LEAD_CONTACT_MODE` defaults/falls back to `dry_run` and no migration code flips it to live.
- [ ] Run the repository secret scan again.
- [ ] Review branch diff: only Lead Engine code, focused adapters, tests, docs, and dependency metadata are allowed.
- [ ] Open a pull request from `migration/lead-engine-extraction` to target `main` with source baseline and verification results in the body.
- [ ] Do not merge until all checks pass.

### Task 8: Merge target repository and verify a non-production build

**Files:**
- Target repository only; no Villa-repo cleanup yet.

**Interfaces:**
- Produces: verified `main` in `Cozyasia/cozy-lead-engine` ready to become Render source.

- [ ] Merge the verified extraction PR.
- [ ] Confirm target `main` contains the expected files and remains private.
- [ ] If CI is configured, verify latest target-main checks pass.
- [ ] Perform an import/startup smoke test in an environment with monitor disabled and without sending third-party messages.
- [ ] Record target main commit SHA for Render cutover and rollback.

### Task 9: Controlled Render cutover

**Files:**
- Render service configuration only.

**Interfaces:**
- Existing service: `Cozy-Lead-Engine`.
- New source: `Cozyasia/cozy-lead-engine`, branch `main`.
- Start command: `python lead_engine_main.py`.

- [ ] Before changing source, record current Render service source and source commit/baseline.
- [ ] Keep `COZY_LEAD_CONTACT_MODE=dry_run` and temporarily keep the production monitor disabled during first boot after source change.
- [ ] Repoint the existing `Cozy-Lead-Engine` service to the private repository and deploy target main.
- [ ] Verify health endpoint and clean startup logs.
- [ ] In Telegram run `/manager_status`; require `@CozyAsiaAI` to report connected.
- [ ] Run `/traffic_recipient_test @samui5 131661`; require the same real recipient resolution and zero third-party send.
- [ ] Run `/traffic_sources` and one controlled `/traffic_scan`; verify existing shared Google Sheet state is used.
- [ ] Only after these checks, restore the normal monitor setting.
- [ ] If any check fails, rollback Render to `Cozyasia/Cozyasia_villas@b9eb4f90149b198a36c63b1ae983c226b36b2df8` and keep dry-run.

### Task 10: Deferred cleanup of `Cozyasia_villas`

**Files:**
- Separate future PR in `Cozyasia/Cozyasia_villas`.

**Interfaces:**
- Must happen only after stable Lead Engine production verification.

- [ ] Identify Lead Engine-only files now owned by the private repository.
- [ ] Confirm no Villa runtime/import path depends on them.
- [ ] Remove only confirmed Lead Engine-only modules/tests from Villa repo.
- [ ] Keep Villa-specific `mtproto_user_client.py`, premium emoji/channel publishing, catalogue, lot and post automation intact.
- [ ] Update Villa README to describe Villa responsibilities only.
- [ ] Run Villa bot regression tests and deploy separately.
