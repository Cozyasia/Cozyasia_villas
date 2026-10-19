# Facebook Villa Batch Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add and safely run a data-driven Telethon publisher for the verified Facebook four-bedroom villa candidates in the Cozy Asia small channel.

**Architecture:** A one-shot batch module will validate a manifest, render the established premium caption format, publish each listing as one Telegram album of up to 10 photos, and read back each result. A gated environment flag keeps ordinary Render startup side-effect free.

**Tech Stack:** Python 3.12, Telethon, existing Cozy Asia MTProto/premium helpers, pytest, Render environment flag.

**Spec:** `docs/superpowers/specs/2026-10-20-facebook-villa-batch-design.md`

## Global Constraints

- Target channel is `@arenda_vill_samui`.
- Use `@Cozyasia_villa_bot` for the small-channel CTA.
- Exactly four bedrooms are required in every manifest entry.
- Maximum 10 Telegram photos per listing.
- No owner contact details in public captions.
- No deletion, edits, bookings, or payments.
- Normal service startup must not publish.

## Review Focus

- Duplicate Facebook URLs must be rejected before any Telegram call.
- A three-bedroom or missing-photo entry must fail validation.
- A caption over Telegram's 1024-character album limit must fail before send.
- A retry after a successful send must return the existing Telegram message instead of duplicating it.
- A failing listing must not prevent later independent listings from being attempted.

### Task 1: Batch manifest and validation

**Files:**
- Create: `fb_villa_batch_20261020.py`
- Test: `tests/test_fb_villa_batch_20261020.py`

**Interfaces:**
- Produce `ListingSpec`, `validate_manifest(entries)`, and `render_caption(entry, lot_id)`.

- [ ] Write failing tests for duplicate source URLs, bedroom count, required fields, photo limit, and caption-length validation.
- [ ] Run `pytest tests/test_fb_villa_batch_20261020.py -q`; expect failure because the module is absent.
- [ ] Implement the manifest dataclass and pure validation/caption helpers without importing or connecting to Telethon during module import.
- [ ] Run the focused tests and verify they pass.

### Task 2: Telethon publication runner

**Files:**
- Modify: `fb_villa_batch_20261020.py`
- Test: `tests/test_fb_villa_batch_20261020.py`

**Interfaces:**
- Consume `ListingSpec` and existing `mtproto_user_client`, `publication_safety`, and `channel_publication_policy`.
- Produce `async run_batch(entries, dry_run: bool) -> list[dict]` and `run_service_mode()`.

- [ ] Write failing tests for dry-run isolation, duplicate read-back handling, and per-listing failure isolation using injected client/publisher boundaries.
- [ ] Run the focused tests and verify the new tests fail for the missing runner.
- [ ] Implement gated album publishing to `@arenda_vill_samui`, small-channel CTA generation, existing premium/custom-emoji upgrade, read-back verification, and per-entry result records.
- [ ] Run the focused tests and verify they pass.

### Task 3: Production entrypoint and manifest wiring

**Files:**
- Modify: `main.py`
- Modify: `fb_villa_batch_20261020.py`
- Test: `tests/test_fb_villa_batch_20261020.py`

**Interfaces:**
- Environment flag: `PUBLISH_FB_VILLA_BATCH_20261020=1`.
- Manifest source: checked-in data within the batch module, with photo package paths supplied by the Render environment.

- [ ] Add a failing test proving ordinary import/startup does not execute the publisher and the flag is required.
- [ ] Run the focused test and verify failure.
- [ ] Add the explicit gated branch to `main.py`; do not alter existing gates.
- [ ] Run the full available pytest suite.

### Task 4: Dry-run and deployment verification

**Files:**
- Modify: `docs/superpowers/plans/2026-10-20-facebook-villa-batch.md` only if operational notes are needed.

- [ ] Run the batch dry-run and verify every entry has exactly four bedrooms, valid source URL, valid caption, and at most 10 photos.
- [ ] Confirm Render service health and deployment status on the feature branch/staging path.
- [ ] Only after dry-run passes, enable the one-shot flag for the intended Render service and verify each Telegram read-back URL.
- [ ] Disable the one-shot flag after completion and report published, skipped, and failed entries.
