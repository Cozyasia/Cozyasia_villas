# -*- coding: utf-8 -*-
"""One-shot maintenance: backfill WebsiteMedia refs from verified Telegram albums."""
from __future__ import annotations
import hashlib, json, os, time
import gspread
from google.oauth2.service_account import Credentials
from telethon import TelegramClient
from telethon.sessions import StringSession

SPREADSHEET_ID="1D-A0u8UUksT3GHiqnpyfmoCKX2gGs5REwZxX_xLXeWg"
ROWS=[176,246,249,252,279,280,281,284,294,316,321,328,329,335,348,362,363,386,388,396,398,399,400,411,415,416,420,424,429,439,442,445,450,451,459,460,462,464,465,466,469,471,474,475,476,502]

def _creds():
    raw=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON","").strip()
    if raw.startswith("{"):
        return Credentials.from_service_account_info(json.loads(raw),scopes=["https://www.googleapis.com/auth/spreadsheets"])
    path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS","").strip()
    return Credentials.from_service_account_file(path,scopes=["https://www.googleapis.com/auth/spreadsheets"])

def main():
    gc=gspread.authorize(_creds()); sh=gc.open_by_key(SPREADSHEET_ID); lots=sh.worksheet("Lots"); media=sh.worksheet("WebsiteMedia")
    vals=lots.get_all_values(); existing=media.get_all_values()
    existing_manifest={r[1] for r in existing[1:] if len(r)>1 and r[1]}
    api_id=int(os.environ["MT_API_ID"]); api_hash=os.environ["MT_API_HASH"]; session=os.environ["MT_SESSION_KEY"]
    client=TelegramClient(StringSession(session),api_id,api_hash)
    client.start()
    added=0; ready=0; failed=[]
    for rn in ROWS:
        r=vals[rn-1]; lot=(r[0] if len(r)>0 else "").strip(); mid=int((r[1] if len(r)>1 else "0") or 0)
        wid=(r[27] if len(r)>27 else "").strip()
        msg=client.get_messages("samuirental",ids=mid)
        if not msg:
            failed.append([lot,"message_not_found"]); continue
        gid=getattr(msg,"grouped_id",None); candidates=[]
        if gid:
            nearby=client.get_messages("samuirental",ids=list(range(max(1,mid-12),mid+13)))
            candidates=[m for m in nearby if m and getattr(m,"grouped_id",None)==gid and (getattr(m,"photo",None) or str(getattr(getattr(m,"document",None),"mime_type","")).startswith("image/"))]
            candidates.sort(key=lambda m:m.id)
        elif getattr(msg,"photo",None) or str(getattr(getattr(msg,"document",None),"mime_type","")).startswith("image/"):
            candidates=[msg]
        if not candidates:
            failed.append([lot,"no_images"]); continue
        manifest="manifest:"+hashlib.sha256((wid+"|samuirental|"+str(mid)+"|"+",".join(str(m.id) for m in candidates)).encode()).hexdigest()[:20]
        rows=[]
        for idx,m in enumerate(candidates[:20]):
            asset="cwm_"+hashlib.sha256((manifest+"|"+str(idx)).encode()).hexdigest()[:24]
            rows.append([wid,manifest,asset,"telegram",f"telegram:samuirental:{mid}:{idx}","image/jpeg","","",idx+1,"",True])
        if manifest not in existing_manifest:
            media.append_rows(rows,value_input_option="RAW"); existing_manifest.add(manifest); added+=len(rows)
        lots.update_cell(rn,34,manifest); lots.update_cell(rn,35,""); lots.update_cell(rn,36,"")
        ready+=1
        print("READY",lot,mid,len(rows),manifest,flush=True)
    client.disconnect()
    print(json.dumps({"ready":ready,"media_rows_added":added,"failed":failed},ensure_ascii=False),flush=True)

if __name__=="__main__": main()
