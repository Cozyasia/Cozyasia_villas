# -*- coding: utf-8 -*-
"""One-shot Telegram media scanner for remaining website lots."""
import json, asyncio
ITEMS=[["samuirental",1169,4795,"cw_6e38256a3934"],["samuirental",1186,4955,"cw_3c2bd58d67e5"],["samuirental",1187,4965,"cw_ede376535b03"],["samuirental",1188,4974,"cw_66d88a1abeb4"],["samuirental",1189,4979,"cw_84160b00225b"],["samuirental",1191,5008,"cw_4fabc250f0a8"],["samuirental",1192,5017,"cw_4e20b12a2c36"],["samuirental",1194,5035,"cw_f694a6f01ea7"],["samuirental",1195,5045,"cw_386073752580"],["samuirental",1197,5065,"cw_e2a192cbf3ca"],["samuirental",1198,5075,"cw_cd7ed7225f0c"],["samuirental",1201,5104,"cw_d04aeaa8b610"],["samuirental",1204,5134,"cw_4c9f70e05128"],["arenda_vill_samui",1170,794,"cw_e4488ab617e1"],["arenda_vill_samui",1173,824,"cw_1fa68e5720c2"],["arenda_vill_samui","-313011",89,"cw_727d82dd2209"],["arenda_vill_samui","01-005",170,"cw_6a6332ca9dd0"],["arenda_vill_samui","01-008",198,"cw_0882d00e2f5b"],["arenda_vill_samui","01-014",274,"cw_5c1573acf65a"],["arenda_vill_samui",1181,881,"cw_4395f2c890c5"],["arenda_vill_samui",1182,891,"cw_5fc4482051e0"],["arenda_vill_samui",1208,1013,"cw_62c0fc1f88ab"]]
async def _amain():
 import cozy_catalog, mtproto_user_client
 c=await asyncio.wait_for(mtproto_user_client._new_client(cozy_catalog),timeout=30)
 if not c: raise RuntimeError("Stored MTProto session unavailable")
 out=[]
 for channel,lot,mid,wid in ITEMS:
  try:
   msg=await asyncio.wait_for(c.get_messages(channel,ids=mid),timeout=20)
   imgs=[mid] if msg and (getattr(msg,"photo",None) or str(getattr(getattr(msg,"document",None),"mime_type","")).startswith("image/")) else []
   out.append({"channel":channel,"lot":lot,"mid":mid,"wid":wid,"image_message_ids":imgs})
  except Exception as e: out.append({"channel":channel,"lot":lot,"mid":mid,"wid":wid,"error":type(e).__name__})
 print("WM_SCAN="+json.dumps(out,separators=(",",":")),flush=True)
 await c.disconnect()
def main(): asyncio.run(_amain())
if __name__=="__main__": main()
