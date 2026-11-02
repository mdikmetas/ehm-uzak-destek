#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EHM Uzak Destek - RELAY (bulusma noktasi)
Bir kez, internetten erisilebilen bir makinede (VPS / ucretsiz PaaS) calisir.
Istemciler buraya DISARI dogru baglanir; son kullanicilar port acmaz.
Calistir:  python relay.py        (varsayilan 8765 portu)
Gereken:   pip install websockets
"""
import asyncio, json, secrets, os
import websockets

HOSTS = {}  # kod -> {"ws": host_ws, "viewer": viewer_ws}

def newcode():
    c = "%09d" % secrets.randbelow(1000000000)
    while c in HOSTS:
        c = "%09d" % secrets.randbelow(1000000000)
    return c

async def handler(ws, path=None):
    ws._role = None; ws._code = None; ws._peer = None
    try:
        async for msg in ws:
            if isinstance(msg, (bytes, bytearray)):
                p = ws._peer
                if p is not None:
                    try: await p.send(msg)
                    except Exception: pass
                continue
            try: d = json.loads(msg)
            except Exception: continue
            t = d.get("type")
            if t == "host":
                code = newcode()
                HOSTS[code] = {"ws": ws, "viewer": None}
                ws._role = "host"; ws._code = code
                await ws.send(json.dumps({"type": "hosting", "code": code}))
            elif t == "connect":
                c = str(d.get("code", "")).strip()
                h = HOSTS.get(c)
                if not h:
                    await ws.send(json.dumps({"type": "error", "msg": "invalid_code"}))
                elif h["viewer"] is not None:
                    await ws.send(json.dumps({"type": "error", "msg": "busy"}))
                else:
                    h["viewer"] = ws; ws._role = "viewer"; ws._code = c
                    await h["ws"].send(json.dumps({"type": "request"}))
            elif t == "approve":
                h = HOSTS.get(ws._code)
                if h and h["viewer"]:
                    ws._peer = h["viewer"]; h["viewer"]._peer = ws
                    await h["viewer"].send(json.dumps({"type": "approved"}))
            elif t == "reject":
                h = HOSTS.get(ws._code)
                if h and h["viewer"]:
                    try: await h["viewer"].send(json.dumps({"type": "rejected"}))
                    except Exception: pass
                    h["viewer"]._peer = None; h["viewer"] = None
            else:
                p = ws._peer
                if p is not None:
                    try: await p.send(msg)
                    except Exception: pass
    except Exception:
        pass
    finally:
        c = ws._code; r = ws._role
        if r == "host" and c in HOSTS:
            v = HOSTS[c]["viewer"]
            if v:
                try: await v.send(json.dumps({"type": "ended"}))
                except Exception: pass
            del HOSTS[c]
        elif r == "viewer" and c in HOSTS and HOSTS[c]["viewer"] is ws:
            HOSTS[c]["viewer"] = None
            try: await HOSTS[c]["ws"].send(json.dumps({"type": "peer_left"}))
            except Exception: pass

async def main():
    port = int(os.environ.get("PORT", "8765"))
    async with websockets.serve(handler, "0.0.0.0", port, max_size=None,
                                ping_interval=20, ping_timeout=20):
        print("RELAY calisiyor, port:", port)
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
