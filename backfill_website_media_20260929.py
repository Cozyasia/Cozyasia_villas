# -*- coding: utf-8 -*-
"""One-shot Telegram media locator for remaining website lots."""
import json, asyncio
ITEMS=[["samuirental","933",2295,"cw_9770c90c776c"],["samuirental","989",2871,"cw_9ef4e84822a1"],["samuirental","1042",3481,"cw_ff65662a9594"],["samuirental","1063",3705,"cw_b89729f80f7b"],["samuirental","1118",4268,"cw_25569fd624a9"],["samuirental","1184",4925,"cw_c3cc5e2115c6"],["samuirental","1185",4945,"cw_adbddd88164e"],["samuirental","1193",5025,"cw_1a4684ea1ccb"],["samuirental","1196",5055,"cw_d398a0c54ce4"],["samuirental","1199",5081,"cw_d8b906e97a85"],["arenda_vill_samui","1063A",716,"cw_5f05a8db272c"],["arenda_vill_samui","1063B",139,"cw_fbe56f47699e"],["arenda_vill_samui","01-003B",149,"cw_ead108a5ec3c"],["arenda_vill_samui","1186",930,"cw_0abc5aa77d5e"],["arenda_vill_samui","1209",1103,"cw_bc45e9c83e54"],["arenda_vill_samui","1210",1113,"cw_8336e093107d"],["arenda_vill_samui","1211",1123,"cw_1db3f64ebc2a"]]
def _img(m): return bool(m and (getattr(m,"photo",None) or str(getattr(getattr(m,"document",None),"mime_type","")).startswith("image/")))
async def _amain():
 import cozy_catalog, mtproto_user_client
 c=await asyncio.wait_for(mtproto_user_client._new_client(cozy_catalog),timeout=30)
 if not c: raise RuntimeError("Stored MTProto session unavailable")
 out=[]
 for channel,lot,mid,wid in ITEMS:
  found=[]
  for candidate in range(mid, max(0,mid-15), -1):
   try:
    m=await asyncio.wait_for(c.get_messages(channel,ids=candidate),timeout=10)
    if _img(m): found.append(candidate)
   except Exception: pass
  out.append({"channel":channel,"lot":lot,"mid":mid,"wid":wid,"nearby_image_message_ids":found})
 print("WM_SCAN="+json.dumps(out,separators=(",",":")),flush=True); await c.disconnect()
def main(): asyncio.run(_amain())
if __name__=="__main__": main()
