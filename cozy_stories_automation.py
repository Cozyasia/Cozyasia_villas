# -*- coding: utf-8 -*-
"""Daily Cozy Asia Telegram Stories for @samuirental and @arenda_vill_samui."""
from __future__ import annotations

import asyncio, hashlib, html, io, logging, os, random, re, threading, time
from datetime import datetime, timedelta, timezone
import requests
import mtproto_user_client

log = logging.getLogger("cozy-stories")
TZ = timezone(timedelta(hours=7))
CHANNELS = tuple(x.strip().lstrip("@") for x in os.getenv(
    "COZY_STORIES_CHANNELS", "samuirental,arenda_vill_samui"
).split(",") if x.strip())
STATE_SHEET = "CozyStoriesAutomation"
RECENT = max(5, min(int(os.getenv("COZY_STORIES_RECENT_POSTS", "20")), 50))
PROPERTY_HOUR = int(os.getenv("COZY_STORIES_PROPERTY_HOUR", "9"))
SERVICE_HOUR = int(os.getenv("COZY_STORIES_SERVICE_HOUR", "18"))
SERVICE_DAYS = {1, 3, 6}  # Tue/Thu/Sun
RUN_ON_START = os.getenv("COZY_STORIES_RUN_ON_START", "0").lower() in {"1","true","yes","on"}
_STARTED = False
_LOCK = threading.Lock()


def _ws(catalog):
    sh = catalog._client().open_by_key(catalog.SHEET_ID)
    try: return sh.worksheet(STATE_SHEET)
    except Exception:
        ws = sh.add_worksheet(title=STATE_SHEET, rows=1200, cols=7)
        ws.append_row(["day","channel","kind","source_message_id","story_id","created_at","note"], value_input_option="RAW")
        return ws


def _state(catalog):
    try: return _ws(catalog).get_all_values()[1:]
    except Exception:
        log.exception("Cozy Stories state read failed"); return []


def _done(catalog, day, channel, kind):
    return any(len(r)>=3 and r[0]==day and r[1]==channel and r[2]==kind for r in _state(catalog))


def _used(catalog, channel, now):
    cutoff=(now-timedelta(days=7)).date(); out=set()
    for r in _state(catalog):
        if len(r)<4 or r[1]!=channel or r[2]!="property" or not str(r[3]).isdigit(): continue
        try:
            if datetime.strptime(r[0],"%Y-%m-%d").date()>=cutoff: out.add(int(r[3]))
        except Exception: pass
    return out


def _mark(catalog, day, channel, kind, mid, sid, note=""):
    _ws(catalog).append_row([day,channel,kind,str(mid or ""),str(sid or ""),datetime.now(timezone.utc).isoformat(timespec="seconds"),(note or "")[:500]], value_input_option="RAW")


def _clean(s):
    return re.sub(r"[ \t]+"," ",html.unescape(s or "").replace("\ufe0f","").replace("\u20e3","")).strip()


def _font(size,bold=False):
    from PIL import ImageFont
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try: return ImageFont.truetype(p,size)
    except Exception: return ImageFont.load_default()


def _wrap(draw,text,font,width,n):
    out=[]; line=""
    for w in _clean(text).split():
        t=(line+" "+w).strip()
        if not line or draw.textlength(t,font=font)<=width: line=t; continue
        out.append(line); line=w
        if len(out)>=n: break
    if line and len(out)<n: out.append(line)
    return out[:n]


def _weather():
    try:
        r=requests.get("https://api.open-meteo.com/v1/forecast",params={
            "latitude":9.512,"longitude":100.013,"current":"temperature_2m,weather_code",
            "daily":"precipitation_probability_max","timezone":"Asia/Bangkok","forecast_days":1,
        },timeout=12); r.raise_for_status(); d=r.json(); c=d.get("current",{}); day=d.get("daily",{})
        code=int(c.get("weather_code",-1)); label=("ясно" if code==0 else "облачно" if code in {1,2,3} else "дождь" if code in {51,53,55,61,63,65,80,81,82} else "гроза" if code in {95,96,99} else "переменная погода")
        rain=(day.get("precipitation_probability_max") or [None])[0]
        return f"🌤 Самуи {round(float(c['temperature_2m']))}°C • {label}" + (f" • дождь до {round(float(rain))}%" if rain is not None else "")
    except Exception:
        log.exception("Weather lookup failed"); return "🌤 Погода на Самуи сегодня"


def _lot(msg):
    try:
        import publication_safety
        v=publication_safety.lot_from_message(msg)
        if v: return str(v)
    except Exception: pass
    m=re.search(r"(?i)(?:лот|lot)\s*(?:№|#)?\s*([0-9]{3,7}(?:-[0-9]+)?)",_clean(getattr(msg,"message","") or ""))
    return m.group(1) if m else ""


def _meta(msg):
    text=getattr(msg,"message","") or ""; lines=[_clean(x) for x in text.splitlines() if _clean(x)]; lot=_lot(msg)
    title=""
    for x in lines[:10]:
        low=x.lower()
        if ("лот" in low and re.search(r"\d{3,7}",x)) or x.startswith("#") or "оставить" in low: continue
        if len(x)>=7: title=re.sub(r"^[^\wА-Яа-я0-9]+","",x).strip(); break
    def find(p): return next((x for x in lines if p(x)),"")
    district=re.sub(r"^📍\s*","",find(lambda x:x.startswith("📍") or "район" in x.lower())).strip()
    price=re.sub(r"^[^\w\d]+","",find(lambda x:bool(re.search(r"\d[\d\s'’.]*\s*(?:бат|thb|฿)",x,re.I)) and len(x)<120)).strip()
    avail=re.sub(r"^[^\wА-Яа-я0-9]+","",find(lambda x:"доступ" in x.lower() or "available" in x.lower())).strip()
    return {"lot":lot,"title":title or (f"Лот №{lot}" if lot else "Предложение Cozy Asia"),"district":district,"price":price,"avail":avail,"promo":bool(re.search(r"(?i)акци|promo|promotion|скидк|special offer",text)),"text":text}


async def _pick(client, channel, catalog, channel_name, now):
    used=await asyncio.to_thread(_used,catalog,channel_name,now); msgs=await client.get_messages(channel,limit=max(RECENT*4,50)); pool=[]; groups=set()
    for m in msgs:
        if len(pool)>=RECENT: break
        if not m or not getattr(m,"photo",None): continue
        g=int(getattr(m,"grouped_id",0) or 0)
        if g and g in groups: continue
        if g: groups.add(g)
        meta=_meta(m)
        if not meta["lot"] and not re.search(r"(?i)вилл|дом|апартамент|студи|villa|house|condo",meta["text"]): continue
        pool.append((m,meta))
    fresh=[x for x in pool if int(x[0].id) not in used] or pool
    promos=[x for x in fresh if x[1]["promo"]]
    if promos and random.random()<0.45: return random.choice(promos)
    return random.choice(fresh[:max(1,min(12,len(fresh)))]) if fresh else (None,None)


async def _photo(client,msg):
    from PIL import Image, ImageOps
    try:
        raw=await client.download_media(msg,file=bytes); im=Image.open(io.BytesIO(raw)); return ImageOps.exif_transpose(im).convert("RGB")
    except Exception: log.exception("Listing photo download failed mid=%s",getattr(msg,"id","")); return None


def _property_image(photo,meta,weather,channel):
    from PIL import Image, ImageDraw, ImageEnhance, ImageOps
    R=getattr(Image,"Resampling",Image).LANCZOS; base=ImageOps.fit(photo,(1080,1920),method=R).convert("RGB"); base=ImageEnhance.Contrast(base).enhance(.92).convert("RGBA")
    ov=Image.new("RGBA",base.size,(0,0,0,0)); d=ImageDraw.Draw(ov); d.rectangle((0,0,1080,610),fill=(3,18,31,178)); d.rectangle((0,1310,1080,1920),fill=(3,18,31,210)); im=Image.alpha_composite(base,ov); d=ImageDraw.Draw(im)
    tag="АКЦИЯ" if meta["promo"] else "ПРЕДЛОЖЕНИЕ ДНЯ"; d.rounded_rectangle((65,65,650,180),38,fill=(221,174,73,238)); d.text((357,123),f"COZY ASIA • {tag}",font=_font(35,True),anchor="mm",fill=(12,31,44,255))
    y=250
    for ln in _wrap(d,meta["title"],_font(68,True),940,4): d.text((70,y),ln,font=_font(68,True),fill="white"); y+=86
    details=[]
    if meta["district"]: details.append("📍 "+meta["district"])
    if meta["price"]: details.append("💰 "+meta["price"])
    if meta["avail"]: details.append("📅 "+meta["avail"])
    if meta["lot"]: details.append("🏡 Лот №"+meta["lot"])
    y=1380
    for s in details[:4]:
        for ln in _wrap(d,s,_font(44,True),920,2): d.text((78,y),ln,font=_font(44,True),fill="white"); y+=57
        y+=8
    d.rounded_rectangle((65,1695,1015,1790),34,fill=(255,255,255,230)); d.text((540,1743),weather,font=_font(34,True),anchor="mm",fill=(8,39,61,255)); d.text((540,1850),f"СМОТРЕТЬ ЛОТ → @{channel}",font=_font(33,True),anchor="mm",fill="white")
    b=io.BytesIO(); im.convert("RGB").save(b,"JPEG",quality=91,optimize=True); b.seek(0); b.name="cozy-property-story.jpg"; return b


TOPICS=(
("ЗАГРАНПАСПОРТ И КОНСУЛЬСКИЕ ВОПРОСЫ","Поможем сориентироваться по документам, записи и подготовке пакета. Без обещаний результата — аккуратно по вашей ситуации."),
("КОНСУЛЬСКАЯ ПОМОЩЬ НА САМУИ","Подскажем порядок действий, проверим список документов и поможем организовать процесс до визита в консульство."),
("COZY ASIA — НЕ ТОЛЬКО АРЕНДА","Подбор жилья, онлайн-показы, трансфер и помощь с бытовыми и документальными вопросами на острове."),
)


def _service_image(topic,weather,channel):
    from PIL import Image, ImageDraw
    im=Image.new("RGB",(1080,1920),(5,28,48)); d=ImageDraw.Draw(im)
    for y in range(1920):
        t=y/1919; d.line((0,y,1080,y),fill=(int(5+6*t),int(28+52*t),int(48+60*t)))
    d.rounded_rectangle((70,80,1010,220),46,fill=(221,174,73)); d.text((540,150),"COZY ASIA • ПОМОЩЬ НА САМУИ",font=_font(38,True),anchor="mm",fill=(8,34,52)); d.ellipse((390,315,690,615),fill=(18,121,158),outline=(221,174,73),width=12); d.text((540,465),"CA",font=_font(92,True),anchor="mm",fill="white")
    y=745
    for ln in _wrap(d,topic[0],_font(68,True),900,5): d.text((540,y),ln,font=_font(68,True),anchor="mm",fill="white"); y+=86
    y+=45
    for ln in _wrap(d,topic[1],_font(44),860,7): d.text((540,y),ln,font=_font(44),anchor="mm",fill=(218,238,246)); y+=62
    d.rounded_rectangle((65,1665,1015,1760),34,fill="white"); d.text((540,1713),weather,font=_font(34,True),anchor="mm",fill=(8,39,61)); d.text((540,1845),f"НАПИСАТЬ → @Cozy_asia • @{channel}",font=_font(31,True),anchor="mm",fill="white")
    b=io.BytesIO(); im.save(b,"JPEG",quality=92,optimize=True); b.seek(0); b.name="cozy-service-story.jpg"; return b


def _sid(result):
    for u in getattr(result,"updates",[]) or []:
        v=getattr(u,"id",None) or getattr(getattr(u,"story",None),"id",None)
        if isinstance(v,int) and v>0: return v
    return getattr(result,"id","") or ""


async def _send(client,channel,image,caption):
    from telethon.tl import functions, types
    await client(functions.stories.CanSendStoryRequest(peer=channel)); up=await client.upload_file(image,file_name=image.name)
    return await client(functions.stories.SendStoryRequest(peer=channel,media=types.InputMediaUploadedPhoto(file=up),privacy_rules=[types.InputPrivacyValueAllowAll()],random_id=random.randint(1,2**63-1),caption=caption[:1800]))


async def _properties(catalog,day,now):
    weather=await asyncio.to_thread(_weather); client=await mtproto_user_client._new_client(catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    try:
        for name in CHANNELS:
            if await asyncio.to_thread(_done,catalog,day,name,"property"): continue
            ch=await client.get_entity(name); msg,meta=await _pick(client,ch,catalog,name,now)
            if not msg: log.warning("No property candidate for @%s",name); continue
            photo=await _photo(client,msg)
            if photo is None: continue
            image=await asyncio.to_thread(_property_image,photo,meta,weather,name); cap=f"🏡 {meta['title']}"+(f" • лот №{meta['lot']}" if meta['lot'] else "")+f"\n👉 https://t.me/{name}/{msg.id}\n💬 @Cozy_asia"
            sid=_sid(await _send(client,ch,image,cap)); await asyncio.to_thread(_mark,catalog,day,name,"property",msg.id,sid,meta["lot"]); log.info("COZY_STORY_PROPERTY_SENT @%s mid=%s lot=%s sid=%s",name,msg.id,meta["lot"],sid); await asyncio.sleep(2)
    finally: await client.disconnect()


async def _services(catalog,day,now):
    weather=await asyncio.to_thread(_weather); topic=TOPICS[(now.timetuple().tm_yday//2)%len(TOPICS)]; client=await mtproto_user_client._new_client(catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    try:
        for name in CHANNELS:
            if await asyncio.to_thread(_done,catalog,day,name,"service"): continue
            ch=await client.get_entity(name); image=await asyncio.to_thread(_service_image,topic,weather,name); sid=_sid(await _send(client,ch,image,f"🛂 {topic[0]}\n💬 По вопросам: @Cozy_asia")); await asyncio.to_thread(_mark,catalog,day,name,"service","",sid,topic[0]); log.info("COZY_STORY_SERVICE_SENT @%s sid=%s",name,sid); await asyncio.sleep(2)
    finally: await client.disconnect()


def ensure_started(catalog):
    global _STARTED
    with _LOCK:
        if _STARTED: return
        _STARTED=True
    def run():
        pkey=skey=None; boot=False
        while True:
            try:
                now=datetime.now(TZ); day=now.strftime("%Y-%m-%d")
                if RUN_ON_START and not boot: boot=True; asyncio.run(_properties(catalog,day,now)); pkey=day
                if PROPERTY_HOUR<=now.hour<=PROPERTY_HOUR+2 and pkey!=day: pkey=day; asyncio.run(_properties(catalog,day,now))
                if now.weekday() in SERVICE_DAYS and SERVICE_HOUR<=now.hour<=SERVICE_HOUR+2 and skey!=day: skey=day; asyncio.run(_services(catalog,day,now))
            except Exception: log.exception("Cozy Stories scheduled publication failed")
            time.sleep(60)
    threading.Thread(target=run,name="cozy-stories-scheduler",daemon=True).start(); log.info("Cozy Stories active: daily %02d:00 + services Tue/Thu/Sun %02d:00 Asia/Bangkok; channels=%s; recent=%d",PROPERTY_HOUR,SERVICE_HOUR,",".join("@"+x for x in CHANNELS),RECENT)
