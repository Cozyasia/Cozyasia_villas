# CozyAsia Villa Bot (Telegram)

Telegram bot for Cozy Asia villa rental inquiries. Supports:
- Short rental survey (/rent) -> saves lead to Google Sheets
- Deep-link from channel posts: `https://t.me/Cozyasia_villa_bot?start=LOT_1155` (lot captured automatically)
- Manager notifications to a channel/group or specific chat

## Deploy (Render)
This repo includes `render.yaml`. In Render:
1. Create a new service from this repo.
2. Add Environment Variables:
   - `TELEGRAM_TOKEN` (required)
   - `WEBHOOK_BASE` (required) — your Render public URL (e.g. `https://your-service.onrender.com`)
   - `GOOGLE_SHEET_ID` (required for leads)
   - `GOOGLE_WORKSHEET_NAME` (default: `Leads`)
   - `GOOGLE_CREDS_JSON` (required for leads) — service account JSON (share the Sheet to the service account email as Editor)
   - `GROUP_CHAT_TARGET` (optional) — `@Cozy_asia` (channel/group) or numeric chat_id for a private chat
   - (optional) `OPENAI_API_KEY`, `OPENAI_MODEL`

## Google Sheet
Create a worksheet named `Leads` (recommended). If missing, bot falls back to the first sheet.

## Commands
- `/start` — greeting (or starts survey automatically if started via deep-link)
- `/rent` — start survey
- `/links` — show Cozy Asia links
- `/cancel` — cancel survey
- `/myid` — show chat_id/user_id (useful to configure `GROUP_CHAT_TARGET` for private chats)
