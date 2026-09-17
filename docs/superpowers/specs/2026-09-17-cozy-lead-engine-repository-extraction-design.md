# Cozy Lead Engine Repository Extraction Design

## Goal

Move the already-working Cozy Lead Engine out of `Cozyasia/Cozyasia_villas` into a new **private** repository `Cozyasia/cozy-lead-engine`, then repoint the existing Render service `Cozy-Lead-Engine` to the new repository without enabling LIVE SEND and without interrupting the Villa bot.

## Baseline

The migration source baseline is `Cozyasia/Cozyasia_villas` `main` at commit `b9eb4f90149b198a36c63b1ae983c226b36b2df8` (Merge PR #3: placeholder guard and real recipient probe).

At this baseline:
- `@CozyLeadEngine_bot` is the dedicated control bot.
- `@CozyAsiaAI` is connected through the AI Manager MTProto session.
- `/manager_status` passes.
- `/traffic_recipient_test @samui5 131661` resolves the real recipient without sending a message.
- contact mode remains `dry_run`.
- LIVE SEND is not part of this migration.

## Target ownership

### `Cozyasia/cozy-lead-engine` (private)

Owns all lead-discovery and outreach-preparation code:
- Lead Engine process entrypoint and health endpoint.
- Telegram control commands for the authorized admin.
- source discovery, monitoring, scoring and opportunity persistence.
- AI draft generation, placeholder guard, draft persistence and approval/edit flow.
- AI Manager (`@CozyAsiaAI`) authorization and recipient resolution.
- Lead Engine tests and deployment documentation.

### `Cozyasia/Cozyasia_villas`

Remains the Villa/rental bot repository:
- villa catalogue and rental inquiry flows.
- lot/deep-link processing.
- channel/post/premium-emoji publishing automation.
- villa-specific scripts and maintenance utilities.

After cutover, Lead Engine modules may be removed from this repository only after the new private repository has passed parity tests and the Render service has been verified in production.

### `Cozyasia/gpt5pro-bot`

Unchanged. It remains the separate Neyro-Bot GPT 5 Studio product and is not a dependency of Cozy Lead Engine.

## Extraction strategy

Use a staged extraction rather than copying the entire Villa repository.

### Stage 1 — create a private repository from the verified Lead Engine slice

Create `Cozyasia/cozy-lead-engine` as a private repository with `main` as the default branch.

Move/copy the Lead Engine modules from the source baseline, including the current production entrypoint/control/draft/traffic/AI-manager modules and their relevant tests.

The extracted repository must keep current behavior first. No feature work is mixed into the repository split.

### Stage 2 — remove Villa-only dependencies inside the new repository

The current Lead Engine still depends on two Villa-oriented modules:

1. `cozy_catalog` is used as a Google Sheets access object.
2. `cozy_traffic_runtime` calls `mtproto_user_client._new_client(...)`, while `mtproto_user_client.py` also contains Villa channel publishing and Premium Custom Emoji code.

The new repository must not copy those unrelated Villa features.

Replace them with focused compatibility modules:

- `lead_sheets.py` — owns Google Sheets connection and exposes the minimal interface the Lead Engine currently consumes (`SHEET_ID` and `_client()` plus any additional interface proven necessary by tests).
- `traffic_mtproto.py` — owns only the encrypted read-only MTProto session loading/client creation required by source discovery/scanning. It must contain no channel publishing, joining, forwarding, editing, emoji, or post-formatting operations.

`lead_engine_main.py` and the traffic modules are updated to use these focused modules.

The AI Manager session in `ai_manager_auth.py` remains separate and continues to represent `@CozyAsiaAI`.

## Repository structure

The private repository should initially keep the current flat module layout to minimize migration risk. A package refactor is explicitly out of scope for this migration.

Expected core files include:
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
- new `lead_sheets.py`
- new `traffic_mtproto.py`
- `requirements.txt` reduced to dependencies actually required by Lead Engine
- Lead Engine/traffic/AI-manager tests copied from the source repository
- `README.md` documenting the dedicated service and safe operating modes

## Shared state

Migration does **not** create a new Google Sheet or change worksheet names. The existing Sheet remains authoritative so that no opportunities, source approvals, draft records, configuration, or encrypted sessions are lost.

Existing worksheets used by the Lead Engine continue unchanged, including the traffic/opportunity, Lead Engine config/action/draft, MTProto auth, and AI Manager auth worksheets.

No secret values are copied into GitHub.

## Secrets and configuration

Secrets stay in Render Environment and are never committed to the private repository.

The new repository reads the same production values already used by the Render service, including as applicable:
- `COZY_LEAD_BOT_TOKEN`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDS_JSON`
- `MT_API_ID`
- `MT_API_HASH`
- `MT_SESSION_KEY`
- `AI_MANAGER_USERNAME=CozyAsiaAI`
- `COZY_TRAFFIC_ADMIN_USERNAME=Cozy_asia`
- `COZY_TRAFFIC_ADMIN_USER_ID`
- traffic monitor/scan configuration
- OpenAI API/model configuration
- `COZY_LEAD_CONTACT_MODE=dry_run`

The migration must not print, copy, commit, or rotate secrets unless a secret is independently found to be compromised.

## Safety invariants

The repository extraction must preserve these invariants:

1. `COZY_LEAD_CONTACT_MODE` stays `dry_run` throughout migration.
2. No LIVE SEND implementation is enabled as part of the split.
3. `/traffic_recipient_test` must remain non-sending.
4. `@CozyAsiaAI` must not send a third-party Telegram message during migration acceptance tests.
5. source discovery/scanning remains read-only toward third-party Telegram chats.
6. the existing Villa bot remains independently deployable and is not repointed to the new repository.
7. the current Render `Cozy-Lead-Engine` service is not changed until the private repository passes local/CI parity checks.

## Verification before Render cutover

The new repository must pass:

- import/compile checks for all production modules;
- the copied Lead Engine/traffic/AI-manager unit tests;
- explicit tests that `traffic_mtproto.py` contains no Telegram write path;
- placeholder retry/block tests;
- admin authorization tests;
- recipient-resolution tests;
- dry-run approval tests proving outbound send methods are not invoked;
- entrypoint/health-server tests.

The acceptance baseline after deployment is:

1. `/manager_status` reports `@CozyAsiaAI` connected.
2. `/traffic_recipient_test @samui5 131661` resolves the same recipient and sends nothing.
3. `/traffic_sources`, `/traffic_scan`, and the monitor use the existing shared Sheet.
4. health endpoint reports the Lead Engine service healthy.
5. logs contain no unexpected outbound Telegram send to third-party recipients.

## Render cutover

Do not create a second active monitor against the same production state unless intentionally used as a short controlled test with monitoring disabled.

Preferred cutover:

1. Build and verify `Cozyasia/cozy-lead-engine` independently with monitor disabled.
2. Repoint the existing Render service `Cozy-Lead-Engine` from `Cozyasia/Cozyasia_villas` to `Cozyasia/cozy-lead-engine`, branch `main`.
3. Keep the existing service environment/secrets unchanged.
4. Deploy with `python lead_engine_main.py`.
5. Verify health, bot commands, AI Manager status, recipient probe, and shared Sheet access while still in `dry_run`.
6. Re-enable the production monitor only after those checks pass.

## Rollback

Before cutover, record the current source repository and commit SHA (`Cozyasia/Cozyasia_villas@b9eb4f90149b198a36c63b1ae983c226b36b2df8`).

If the new deployment fails verification:
- repoint/rollback Render to the recorded Villa repository baseline;
- keep `COZY_LEAD_CONTACT_MODE=dry_run`;
- do not delete extracted files from `Cozyasia_villas`;
- diagnose the new private repository offline before another cutover attempt.

## Cleanup after successful cutover

Only after stable production verification:

- remove Lead Engine-specific production modules/tests from `Cozyasia_villas` through a separate PR;
- leave Villa functionality untouched;
- update the Villa README so it no longer documents Lead Engine deployment;
- keep the old baseline reachable through Git history for rollback/audit.

## Success criteria

The migration is complete when:

1. `Cozyasia/cozy-lead-engine` exists as a private repository and contains only Lead Engine responsibilities plus minimal supporting adapters.
2. its test suite passes independently of `Cozyasia_villas`.
3. Render `Cozy-Lead-Engine` deploys from the private repository.
4. `/manager_status` and the real recipient probe still pass.
5. monitoring and persistence use the existing shared state.
6. no third-party Telegram message is sent during migration.
7. `Cozyasia_villas` and `gpt5pro-bot` remain independently functional and logically separate.
