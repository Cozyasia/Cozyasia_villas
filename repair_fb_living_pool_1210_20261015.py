# -*- coding: utf-8 -*-
"""Repair lot 1210 as one Telegram album with one caption.

The previous publication was split into two albums.  This one-shot job removes
only matching Living Pool/Chaweng lot-1210 messages, then publishes exactly ten
property photos as a single grouped album and verifies the read-back.
"""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from pathlib import Path

import requests

import cozy_catalog
import mtproto_user_client
import publication_safety
from publish_fb_living_pool_villas_20261015 import _final_caption

CHANNEL = "samuirental"
LOT = "1210"
# Ten Facebook CDN URLs from the source post/gallery.  The job is one-shot, so
# downloading at run time avoids adding private source files to the repository.
PHOTO_URLS = (
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/600906184_1365131708745984_7279814146317985633_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=111&ccb=1-7&_nc_sid=833d8c&_nc_ohc=rvIutj1dTxkQ7kNvwGywV29&_nc_oc=AdpfhiRGv_6q8FbGoQuHgQfJuxihq2-rNoKfq3SAB7elV41F41U27qxp28EihnPeUaK_UNGN_4xL4bcB7ECJGA42&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQPIzDsoVoN968WZWWCN_ECqMt9P5VbDKC_6dvMEvYpATQ&oe=6AD6A4F7",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/598070017_1365132022079286_6347035220067870309_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=8Ws8UONLlDEQ7kNvwF5fXuA&_nc_oc=AdputRDfpziWUjanvTS0QJpGfOqQX5vA-IN4mZ5tK5WGP2IGlwmyMzCJBz2L6O6SKSwK4yRutTfFt20PAMTgs-qu&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQMCAz0kvUBbTfaSIUF9TB9FnqDkGtHzC-UFtIPKsvJVjg&oe=6AD6A62B",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/601977393_1365134828745672_5509892367080032674_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=105&ccb=1-7&_nc_sid=833d8c&_nc_ohc=0Tl8My1zNj0Q7kNvwGIQm9b&_nc_oc=AdrS_lRFD-wheoa91pLMrLILYunu8RSLIXiyGHnZHHHMUW_qsq_bw5f2qWLaPCzO-Zrho8SlsrE6Cq897OKcLADK&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQNRDTR_QgXYAXPah43oMVONjrtjz-DMc7ROVXHWScJsMg&oe=6AD6B3C9",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/597996481_1365134668745688_7622045648775811937_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=Dym_bV-JzU8Q7kNvwEnEY-l&_nc_oc=AdptSPVApKcfpmY3Q5x_H-GfO3yXp3xVBI0KsRmYRDxsiEliTP5_6opkK3e-AihxGXxbviJSGFA0Isg3QRG7Q1Yd&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQOVAZ5XKwCVYw-iFX1CPBHccrjVhxs_SnzcLnerPWouwg&oe=6AD68C38",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/600341844_1365132452079243_3054366396884928363_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=OUQPRqr6iMUQ7kNvwGZhSl_&_nc_oc=Adqv6p3K3qA3qy2v0k-pu5X2uIUXVyiTZlE3RIoMpxL2e5wYMaCWkyIJ3PhWWLY-g7FodJEKHonqdn10T9U6wfRQ&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQNpicdixVSZz1va6MdjtVuL0qgLMIBRjc1l7CfYw3qPoA&oe=6AD6BBEA",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/600906184_1365131708745984_7279814146317985633_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=111&ccb=1-7&_nc_sid=833d8c&_nc_ohc=rvIutj1dTxkQ7kNvwGywV29&_nc_oc=AdpfhiRGv_6q8FbGoQuHgQfJuxihq2-rNoKfq3SAB7elV41F41U27qxp28EihnPeUaK_UNGN_4xL4bcB7ECJGA42&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQPIzDsoVoN968WZWWCN_ECqMt9P5VbDKC_6dvMEvYpATQ&oe=6AD6A4F7",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/598070017_1365132022079286_6347035220067870309_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=8Ws8UONLlDEQ7kNvwF5fXuA&_nc_oc=AdputRDfpziWUjanvTS0QJpGfOqQX5vA-IN4mZ5tK5WGP2IGlwmyMzCJBz2L6O6SKSwK4yRutTfFt20PAMTgs-qu&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQMCAz0kvUBbTfaSIUF9TB9FnqDkGtHzC-UFtIPKsvJVjg&oe=6AD6A62B",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/601977393_1365134828745672_5509892367080032674_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=105&ccb=1-7&_nc_sid=833d8c&_nc_ohc=0Tl8My1zNj0Q7kNvwGIQm9b&_nc_oc=AdrS_lRFD-wheoa91pLMrLILYunu8RSLIXiyGHnZHHHMUW_qsq_bw5f2qWLaPCzO-Zrho8SlsrE6Cq897OKcLADK&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQNRDTR_QgXYAXPah43oMVONjrtjz-DMc7ROVXHWScJsMg&oe=6AD6B3C9",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/597996481_1365134668745688_7622045648775811937_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=Dym_bV-JzU8Q7kNvwEnEY-l&_nc_oc=AdptSPVApKcfpmY3Q5x_H-GfO3yXp3xVBI0KsRmYRDxsiEliTP5_6opkK3e-AihxGXxbviJSGFA0Isg3QRG7Q1Yd&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQOVAZ5XKwCVYw-iFX1CPBHccrjVhxs_SnzcLnerPWouwg&oe=6AD68C38",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/600341844_1365132452079243_3054366396884928363_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=OUQPRqr6iMUQ7kNvwGZhSl_&_nc_oc=Adqv6p3K3qA3qy2v0k-pu5X2uIUXVyiTZlE3RIoMpxL2e5wYMaCWkyIJ3PhWWLY-g7FodJEKHonqdn10T9U6wfRQ&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=fhJ64gKkKFdqlGGK6k4afw&_nc_ss=7c2a8&oh=00_AQNpicdixVSZz1va6MdjtVuL0qgLMIBRjc1l7CfYw3qPoA&oe=6AD6BBEA",
)
log = logging.getLogger("repair-fb-living-pool-1210")


def _text(message) -> str:
    return str(getattr(message, "message", None) or "")


def _is_candidate(message) -> bool:
    text = _text(message)
    if not text:
        return False
    if publication_safety.lot_from_message(message) == LOT:
        return True
    lowered = text.lower()
    return "living pool" in lowered and "чавенг" in lowered and "85 000" in lowered


def _groups(messages):
    by_group: dict[int, list] = {}
    singles: list = []
    for message in messages:
        gid = int(getattr(message, "grouped_id", 0) or 0)
        if gid:
            by_group.setdefault(gid, []).append(message)
        else:
            singles.append(message)
    return by_group, singles


def _valid_album(group: list) -> bool:
    if len(group) != 10 or any(not getattr(item, "media", None) for item in group):
        return False
    captions = [item for item in group if _text(item)]
    if len(captions) != 1:
        return False
    caption = captions[0]
    return (
        publication_safety.lot_from_message(caption) == LOT
        and "Чавенг" in _text(caption)
        and "85 000" in _text(caption)
    )


async def _recent_messages(client, channel) -> list:
    return [message async for message in client.iter_messages(channel, limit=400)]


async def _delete_old_candidates(client, channel, messages: list) -> list[int]:
    by_group, singles = _groups([message for message in messages if _is_candidate(message)])
    ids: set[int] = set()
    for group in by_group.values():
        ids.update(int(item.id) for item in group)
    ids.update(int(item.id) for item in singles)
    if not ids:
        return []
    ordered = sorted(ids)
    await client.delete_messages(channel, ordered, revoke=True)
    remaining = await client.get_messages(channel, ids=ordered)
    remaining_ids = {int(item.id) for item in (remaining if isinstance(remaining, list) else [remaining]) if item}
    if remaining_ids:
        raise RuntimeError(f"Could not delete old lot-1210 messages: {sorted(remaining_ids)}")
    return ordered


async def run() -> dict:
    if len(PHOTO_URLS) != 10:
        raise RuntimeError(f"Expected exactly 10 photo URLs, found {len(PHOTO_URLS)}")

    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        recent = await _recent_messages(client, channel)
        by_group, _ = _groups([message for message in recent if _is_candidate(message)])
        valid = [group for group in by_group.values() if _valid_album(group)]
        if valid:
            keep_ids = {int(item.id) for item in valid[0]}
            old = [message for message in recent if _is_candidate(message) and int(message.id) not in keep_ids]
            deleted = await _delete_old_candidates(client, channel, old)
            caption = next(item for item in valid[0] if _text(item))
            result = {
                "channel": CHANNEL,
                "lot": LOT,
                "message_id": int(caption.id),
                "url": f"https://t.me/{CHANNEL}/{int(caption.id)}",
                "grouped_id": int(getattr(caption, "grouped_id", 0) or 0),
                "photos": 10,
                "deleted_ids": deleted,
                "result": "already",
            }
            log.info("REPAIR_FB_LIVING_POOL_1210_DONE %s", json.dumps(result, ensure_ascii=False))
            return result

        deleted = await _delete_old_candidates(client, channel, recent)
        text, entities = _final_caption(LOT)
        with tempfile.TemporaryDirectory(prefix="fb-living-pool-1210-") as directory:
            paths = []
            for index, url in enumerate(PHOTO_URLS, start=1):
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                path = Path(directory) / f"{index:02d}.jpg"
                path.write_bytes(response.content)
                if path.stat().st_size < 10_000:
                    raise RuntimeError(f"Downloaded photo {index} is unexpectedly small")
                paths.append(str(path))
            sent = await client.send_file(
                channel,
                paths,
                caption=text,
                formatting_entities=entities,
                link_preview=False,
            )
        sent_messages = sent if isinstance(sent, list) else [sent]
        caption_msg = next((item for item in sent_messages if _text(item)), sent_messages[0])
        recent_after = await _recent_messages(client, channel)
        gid = int(getattr(caption_msg, "grouped_id", 0) or 0)
        album = [item for item in recent_after if int(getattr(item, "grouped_id", 0) or 0) == gid]
        album.sort(key=lambda item: int(item.id))
        if not gid or len(album) != 10 or not _valid_album(album):
            raise RuntimeError(f"Read-back album integrity failed: grouped_id={gid}, count={len(album)}")
        verify = next(item for item in album if _text(item))
        publication_safety.validate_premium_caption(verify.message, verify.entities, LOT)
        result = {
            "channel": CHANNEL,
            "lot": LOT,
            "message_id": int(verify.id),
            "url": f"https://t.me/{CHANNEL}/{int(verify.id)}",
            "grouped_id": gid,
            "photos": len(album),
            "deleted_ids": deleted,
            "result": "published",
        }
        log.info("REPAIR_FB_LIVING_POOL_1210_DONE %s", json.dumps(result, ensure_ascii=False))
        return result
    finally:
        await client.disconnect()


def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("REPAIR_FB_LIVING_POOL_1210_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))

