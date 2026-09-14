# -*- coding: utf-8 -*-
"""Admin control plane and persistent Google-Sheets storage for Cozy Traffic.

MTProto access remains read-only. This module only writes to our own Google
Sheet and sends status replies to the authorized Cozy Asia admin in the bot.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os
import threading
import time

from telegram.ext import CommandHandler

import mtproto_user_client
import cozy_traffic_runtime as traffic

log = logging.getLogger("cozy-traffic-manager")
SOURCE_SHEET = "TrafficSources"
OPPORTUNITY_SHEET = "TrafficOpportunities"
SOURCE_HEADERS = ["username", "title", "kind", "telegram_id", "score", "russian_share", "active30", "status", "found_at", "updated_at"]
OPPORTUNITY_HEADERS = ["key", "created_at", "source_username", "source_title", "message_id", "message_date", "score", "band", "districts", "date_text", "duration_text", "budget", "bedrooms", "occupants", "pets", "reasons", "text", "link"]
_DAEMON_STARTED = False
_DAEMON_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _admin_username() -> str:
    return os.getenv("COZY_TRAFFIC_ADMIN_USERNAME", "Cozy_asia").strip().lstrip("@").lower()


def _admin_ok(update) -> bool:
    user = getattr(update, "effective_user", None); chat = getattr(update, "effective_chat", None)
    return bool(user and chat and getattr(chat, "type", "") == "private" and (getattr(user, "username", "") or "").lower() == _admin_username())


def _worksheet(catalog, title: str, headers: list[str], rows: int = 2500):
    sh = catalog._client().open_by_key(catalog.SHEET_ID)
    try: ws = sh.worksheet(title)
    except Exception:
        ws = sh.add_worksheet(title=title, rows=rows, cols=max(len(headers), 10)); ws.append_row(headers, value_input_option="RAW")
    values = ws.get_all_values()
    if not values: ws.append_row(headers, value_input_option="RAW")
    elif values[0][:len(headers)] != headers: raise RuntimeError(f"Unexpected schema in worksheet {title}")
    return ws


def _source_ws(catalog): return _worksheet(catalog, SOURCE_SHEET, SOURCE_HEADERS, 1200)
def _opportunity_ws(catalog): return _worksheet(catalog, OPPORTUNITY_SHEET, OPPORTUNITY_HEADERS, 6000)


def _source_rows(catalog) -> list[dict[str, str]]:
    values = _source_ws(catalog).get_all_values()
    return [dict(zip(SOURCE_HEADERS, row + [""] * (len(SOURCE_HEADERS) - len(row)))) for row in values[1:]]


def _save_sources(catalog, findings: list[traffic.SourceFinding]) -> dict[str, int]:
    ws = _source_ws(catalog); rows = ws.get_all_values(); index = {}
    for rownum, row in enumerate(rows[1:], start=2):
        username = (row[0] if row else "").strip().lower().lstrip("@")
        if username: index[username] = (rownum, row)
    created = updated = 0; now = _now()
    for item in findings:
        username = item.username.strip().lower().lstrip("@")
        if not username or item.score <= 0: continue
        current = index.get(username); status = "candidate"; found_at = now
        if current:
            old = current[1] + [""] * len(SOURCE_HEADERS)
            status = old[7] if old[7] in {"candidate", "approved", "rejected"} else "candidate"; found_at = old[8] or now
        payload = [username, item.title, item.kind, str(item.telegram_id), str(item.score), f"{item.russian_share:.3f}", str(item.recent_30d), status, found_at, now]
        if current:
            ws.update(f"A{current[0]}:J{current[0]}", [payload], value_input_option="RAW"); updated += 1
        else:
            ws.append_row(payload, value_input_option="RAW"); created += 1
    return {"created": created, "updated": updated}


def _set_source_status(catalog, username: str, status: str) -> bool:
    if status not in {"candidate", "approved", "rejected"}: raise ValueError("invalid source status")
    target = username.strip().lower().lstrip("@"); ws = _source_ws(catalog); rows = ws.get_all_values()
    for rownum, row in enumerate(rows[1:], start=2):
        if row and row[0].strip().lower().lstrip("@") == target:
            found_at = (row[8] if len(row) > 8 else "") or _now()
            ws.update(f"H{rownum}:J{rownum}", [[status, found_at, _now()]], value_input_option="RAW"); return True
    return False


def _approved_sources(catalog, limit: int = 30) -> list[dict[str, str]]:
    rows = [row for row in _source_rows(catalog) if row.get("status") == "approved" and row.get("username")]
    rows.sort(key=lambda row: int(row.get("score") or 0), reverse=True); return rows[:limit]


def _save_opportunities(catalog, leads: list[traffic.LeadFinding]) -> dict[str, int]:
    ws = _opportunity_ws(catalog); rows = ws.get_all_values(); existing = {row[0] for row in rows[1:] if row}; created = duplicate = 0
    for lead in sorted(leads, key=lambda x: (x.message_date, x.score)):
        key = f"{lead.source_username}:{lead.message_id}"
        if key in existing: duplicate += 1; continue
        budget = "" if lead.budget_amount is None else f"{lead.budget_amount} {lead.budget_currency or ''}".strip()
        payload = [key, _now(), lead.source_username, lead.source_title, str(lead.message_id), lead.message_date.isoformat(timespec="seconds"), str(lead.score), lead.band,
            ", ".join(lead.districts), lead.date_text or "", lead.duration_text or "", budget,
            "" if lead.bedrooms is None else str(lead.bedrooms), "" if lead.occupants is None else str(lead.occupants),
            "" if lead.pets is None else ("yes" if lead.pets else "no"), ",".join(lead.reasons), lead.text[:1000], lead.link]
        ws.append_row(payload, value_input_option="RAW"); existing.add(key); created += 1
    return {"created": created, "duplicate": duplicate}


def _recent_opportunities(catalog, limit: int = 15) -> list[dict[str, str]]:
    rows = _opportunity_ws(catalog).get_all_values()[1:]
    data = [dict(zip(OPPORTUNITY_HEADERS, row + [""] * (len(OPPORTUNITY_HEADERS) - len(row)))) for row in rows]
    data.sort(key=lambda row: (int(row.get("score") or 0), row.get("message_date") or ""), reverse=True); return data[:limit]


def _source_line(row: dict[str, str]) -> str:
    return f"{row.get('score','-'):>3} · {row.get('status','candidate'):<9} · {row.get('kind','?')} · @{row.get('username','')} · {row.get('title','')[:55]}"


def _opportunity_line(row: dict[str, str]) -> str:
    extras = []
    if row.get("districts"): extras.append(row["districts"])
    if row.get("budget"): extras.append(row["budget"])
    if row.get("bedrooms"): extras.append(row["bedrooms"] + "BR")
    detail = " · ".join(extras)
    return f"{row.get('band')} {row.get('score')} · @{row.get('source_username')}" + (f" · {detail}" if detail else "") + f"\n{row.get('link')}"


async def _new_client(catalog):
    client = await mtproto_user_client._new_client(catalog)
    if not client: raise RuntimeError("MTProto session is not authorized")
    return client


async def _discover(catalog) -> list[traffic.SourceFinding]:
    client = await _new_client(catalog)
    try:
        return await traffic.discover_public_sources(client,
            search_limit=max(5, min(int(os.getenv("COZY_TRAFFIC_SEARCH_LIMIT", "15")), 40)),
            recent_limit=max(10, min(int(os.getenv("COZY_TRAFFIC_RECENT_LIMIT", "30")), 80)),
            max_candidates=max(20, min(int(os.getenv("COZY_TRAFFIC_MAX_CANDIDATES", "60")), 100)))
    finally: await client.disconnect()


async def _scan(catalog) -> list[traffic.LeadFinding]:
    sources = await asyncio.to_thread(_approved_sources, catalog)
    if not sources: return []
    client = await _new_client(catalog); all_leads = []
    try:
        per_source = max(10, min(int(os.getenv("COZY_TRAFFIC_SCAN_LIMIT", "40")), 100))
        for source in sources:
            try: all_leads.extend(await traffic.scan_public_source(client, username=source["username"], title=source.get("title", ""), limit=per_source))
            except Exception as exc: log.warning("Traffic scan failed source=@%s: %s", source.get("username"), exc.__class__.__name__)
        return all_leads
    finally: await client.disconnect()


async def cmd_traffic_discover(update, context, catalog):
    if not _admin_ok(update): return
    msg = update.effective_message; await msg.reply_text("🔎 Cozy Traffic: ищу русскоязычные публичные источники Самуи…")
    try:
        findings = await _discover(catalog); stats = await asyncio.to_thread(_save_sources, catalog, findings); useful = [x for x in findings if x.score >= 60][:15]
        lines = [f"✅ Найдено {len(findings)}; новых {stats['created']}; обновлено {stats['updated']}.", ""]
        lines += [f"{x.score:>3} · {x.kind} · @{x.username} · {x.title[:60]}" for x in useful]; lines.append("\nОдобрение: /traffic_approve username")
        await msg.reply_text("\n".join(lines)[:3900], disable_web_page_preview=True)
    except Exception as exc:
        log.exception("traffic discover command failed"); await msg.reply_text(f"❌ Discovery failed: {exc.__class__.__name__}")


async def cmd_traffic_sources(update, context, catalog):
    if not _admin_ok(update): return
    rows = await asyncio.to_thread(_source_rows, catalog); rows.sort(key=lambda row: int(row.get("score") or 0), reverse=True)
    if not rows: await update.effective_message.reply_text("TrafficSources пока пуст. Запусти /traffic_discover"); return
    await update.effective_message.reply_text("\n".join(["📡 Cozy Traffic sources:", ""] + [_source_line(row) for row in rows[:30]])[:3900])


async def _status_command(update, context, catalog, status: str):
    if not _admin_ok(update): return
    if not context.args: await update.effective_message.reply_text(f"Использование: /traffic_{status} username"); return
    username = context.args[0]; ok = await asyncio.to_thread(_set_source_status, catalog, username, status)
    if ok: await update.effective_message.reply_text(f"✅ @{username.lstrip('@')} → {status}")
    else: await update.effective_message.reply_text(f"❌ Источник @{username.lstrip('@')} не найден")


async def cmd_traffic_approve(update, context, catalog): return await _status_command(update, context, catalog, "approved")
async def cmd_traffic_reject(update, context, catalog): return await _status_command(update, context, catalog, "rejected")


async def cmd_traffic_scan(update, context, catalog):
    if not _admin_ok(update): return
    msg = update.effective_message; await msg.reply_text("🛰 Сканирую последние сообщения только в approved-источниках…")
    try:
        leads = await _scan(catalog); stats = await asyncio.to_thread(_save_opportunities, catalog, leads); top = sorted(leads, key=lambda x: (x.score, x.message_date), reverse=True)[:10]
        lines = [f"✅ Кандидатов {len(leads)}; новых {stats['created']}; дублей {stats['duplicate']}.", ""]
        lines += [f"{x.band} {x.score} · @{x.source_username}" + (f" · {', '.join(x.districts)}" if x.districts else "") + f"\n{x.link}" for x in top]
        await msg.reply_text("\n".join(lines)[:3900], disable_web_page_preview=True)
    except Exception as exc:
        log.exception("traffic scan command failed"); await msg.reply_text(f"❌ Scan failed: {exc.__class__.__name__}")


async def cmd_traffic_opportunities(update, context, catalog):
    if not _admin_ok(update): return
    rows = await asyncio.to_thread(_recent_opportunities, catalog, 15)
    if not rows: await update.effective_message.reply_text("Пока нет opportunities. Одобри источники и запусти /traffic_scan"); return
    await update.effective_message.reply_text(("🎯 Cozy Traffic opportunities:\n\n" + "\n\n".join(_opportunity_line(row) for row in rows))[:3900], disable_web_page_preview=True)


def _daemon_worker(catalog):
    interval = max(300, min(int(os.getenv("COZY_TRAFFIC_MONITOR_INTERVAL", "900")), 21600)); initial = max(30, min(int(os.getenv("COZY_TRAFFIC_MONITOR_INITIAL_DELAY", "90")), 600)); time.sleep(initial)
    while True:
        try:
            leads = asyncio.run(_scan(catalog)); stats = _save_opportunities(catalog, leads)
            log.info("Traffic monitor cycle leads=%d new=%d duplicates=%d", len(leads), stats["created"], stats["duplicate"])
        except Exception: log.exception("Traffic monitor cycle failed")
        time.sleep(interval)


def ensure_monitor_started(catalog) -> bool:
    global _DAEMON_STARTED
    if os.getenv("COZY_TRAFFIC_MONITOR", "0").strip().lower() not in {"1", "true", "yes", "on"}: return False
    with _DAEMON_LOCK:
        if _DAEMON_STARTED: return False
        _DAEMON_STARTED = True
    threading.Thread(target=_daemon_worker, args=(catalog,), name="cozy-traffic-monitor", daemon=True).start(); log.info("Cozy Traffic monitor enabled"); return True


def install(app, catalog) -> None:
    app.add_handler(CommandHandler("traffic_discover", lambda u, c: cmd_traffic_discover(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_sources", lambda u, c: cmd_traffic_sources(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_approve", lambda u, c: cmd_traffic_approve(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_reject", lambda u, c: cmd_traffic_reject(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_scan", lambda u, c: cmd_traffic_scan(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_opportunities", lambda u, c: cmd_traffic_opportunities(u, c, catalog)), group=-20)
    ensure_monitor_started(catalog); log.info("Cozy Traffic admin commands installed; monitor=%s", os.getenv("COZY_TRAFFIC_MONITOR", "0"))
