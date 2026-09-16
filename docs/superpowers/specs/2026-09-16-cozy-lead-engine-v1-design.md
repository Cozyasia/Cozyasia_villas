# Cozy Lead Engine v1 Design

## Goal

Split Telegram lead discovery/monitoring out of Villa bot into an independent service controlled by `@CozyLeadEngine_bot`, while preserving the existing Google Sheet state and read-only MTProto scanning.

## Scope

V1 includes source discovery, source approval/rejection, 15-minute monitoring, lead scoring, persistence to `TrafficSources` / `TrafficOpportunities`, and immediate admin notifications for newly discovered leads. V1 does not yet send messages to third-party users. QZR Manager user-account automation is a separate follow-up phase.

## Architecture

`lead_engine_main.py` is a new process entrypoint. It applies the existing traffic scoring/discovery patches, creates a dedicated python-telegram-bot Application from `COZY_LEAD_BOT_TOKEN`, installs the traffic admin handlers, starts the monitor, exposes a minimal HTTP health endpoint on Render's `$PORT`, and runs Telegram long polling.

The existing Villa bot `main.py` is restored to catalogue/application duties only: it no longer imports or installs Cozy Traffic and no longer starts Traffic smoke/monitor jobs.

`cozy_traffic_manager.py` remains the shared control-plane/storage module. It is extended with admin registration and new-lead notifications. When a monitoring cycle saves new opportunities, the Lead Engine sends the authorized admin a compact card containing source, score/band, parsed request details, source link, and the original request excerpt. Notification failure must never stop scanning.

## State

Existing sheets remain authoritative:
- `TrafficSources`: discovery and approved/rejected state.
- `TrafficOpportunities`: deduplicated lead queue.

A small `LeadEngineConfig` worksheet stores `admin_chat_id` after the authorized admin starts the bot, so notifications survive Render restarts. No bot tokens or MTProto secrets are stored in Sheets or GitHub.

## Telegram safety

Monitoring remains read-only toward third-party chats. V1 does not send DMs or public replies. Only the dedicated control bot sends messages to the authorized admin. The later QZR Manager phase will require explicit approval of the first outbound public response.

## Render deployment

Create a separate Render web service named `Cozy-Lead-Engine` from the same repository, branch `main`, build command `pip install -r requirements.txt`, start command `python lead_engine_main.py`, region Singapore.

Required secrets/config on the new service:
- `COZY_LEAD_BOT_TOKEN`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDS_JSON`
- `MT_API_ID`
- `MT_API_HASH`
- `MT_SESSION_KEY`
- `COZY_TRAFFIC_ADMIN_USERNAME=Cozy_asia`
- `COZY_TRAFFIC_MONITOR=1`
- `COZY_TRAFFIC_MONITOR_INTERVAL=900`
- `COZY_TRAFFIC_MONITOR_INITIAL_DELAY=30`
- `COZY_TRAFFIC_SCAN_LIMIT=60`

The existing `Cozyasia_villas` service must have `COZY_TRAFFIC_MONITOR=0` after cutover.

## Success criteria

1. Villa bot starts without installing Traffic commands or monitor.
2. `@CozyLeadEngine_bot` responds to `/start`, `/traffic_sources`, `/traffic_scan`, `/traffic_discover`, approve/reject commands.
3. A new saved opportunity causes exactly one admin notification; duplicates do not re-notify.
4. Render health endpoint responds while Telegram polling and the monitor continue running.
5. Traffic scanning remains read-only toward third-party Telegram sources.
