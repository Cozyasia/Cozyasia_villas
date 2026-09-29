# -*- coding: utf-8 -*-
"""One-shot read-only Telegram media scanner for website backfill."""
import json, os, asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
ITEMS=[[729,1382,"cw_3989bf92a1f0"],[905,2029,"cw_faac5b429289"],[908,2055,"cw_2b5a0b393f68"],[911,2078,"cw_19cd62df1a93"],[936,2330,"cw_9c5339f28618"],[937,2335,"cw_2b7b499d634f"],[938,2350,"cw_ffd5858ec94a"],[941,2379,"cw_be37fdd7f679"],[950,2467,"cw_8258b0853daa"],[972,2691,"cw_eae661f7f575"],[977,2739,"cw_b1814991a777"],[984,2821,"cw_4755f43a4bdf"],[985,2828,"cw_902da0cb1497"],[991,2903,"cw_2572fbfcf8e3"],[1004,3056,"cw_2343f7a723f5"],[1019,3195,"cw_28d1cd1fd491"],[1018,3205,"cw_00e4925e3108"],[1039,3453,"cw_7592a45b4ad4"],[1041,3471,"cw_cb3bc8148888"],[1049,3545,"cw_9de14539c6b0"],[1051,3561,"cw_98485757b4e1"],[1052,3571,"cw_bce9ba334a40"],[1053,3581,"cw_51c599eea8d5"],[1064,3715,"cw_22ccc3099595"],[1068,3752,"cw_48cdb21efcb6"],[1069,3771,"cw_d86338e454da"],[1072,3811,"cw_8f0506140a40"],[1075,3846,"cw_b6bafe9d91a0"],[1080,3894,"cw_becc56132312"],[1089,3991,"cw_fa56b52ad5ab"],[1092,4021,"cw_dab59e4aeff5"],[1095,4051,"cw_92ee2f144bb9"],[1100,4090,"cw_a61cda3e8ab7"],[1101,4100,"cw_70f796f2c192"],[1109,4173,"cw_de3cd8c6a301"],[1110,4183,"cw_384fc2d28dd3"],[1111,4198,"cw_5403a4d447ee"],[1113,4218,"cw_77994c4af4be"],[1114,4227,"cw_c53d8a61322b"],[1115,4237,"cw_65106c79eee8"],[1117,4258,"cw_d3bc69858c99"],[1119,4287,"cw_d4209cba9f46"],[1122,4317,"cw_f335d5ac0099"],[1123,4328,"cw_4a3917b84fc8"],[1124,4337,"cw_f508613bec72"],[1147,4600,"cw_6c253450aeef"]]
async def _amain():
 import cozy_catalog, mtproto_user_client
 session=mtproto_user_client._load_session(cozy_catalog)
 if not session: raise RuntimeError("Stored MTProto session unavailable")
 c=TelegramClient(StringSession(session),int(os.environ["MT_API_ID"]),os.environ["MT_API_HASH"]); await c.connect()
 out=[]
 for lot,mid,wid in ITEMS:
  msg=await c.get_messages("samuirental",ids=mid)
  if not msg: out.append({"lot":lot,"mid":mid,"wid":wid,"error":"message_not_found"}); continue
  gid=getattr(msg,"grouped_id",None)
  if gid:
   ms=await c.get_messages("samuirental",ids=list(range(max(1,mid-12),mid+13)))
   imgs=[m.id for m in ms if m and getattr(m,"grouped_id",None)==gid and (getattr(m,"photo",None) or str(getattr(getattr(m,"document",None),"mime_type","")).startswith("image/"))]
   imgs.sort()
  else: imgs=[mid] if (getattr(msg,"photo",None) or str(getattr(getattr(msg,"document",None),"mime_type","")).startswith("image/")) else []
  out.append({"lot":lot,"mid":mid,"wid":wid,"image_message_ids":imgs})
 print("WM_SCAN="+json.dumps(out,separators=(",",":")),flush=True); await c.disconnect()
def main(): asyncio.run(_amain())
if __name__=="__main__": main()
