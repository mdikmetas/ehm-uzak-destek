#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EHM Uzak Destek - TEK UYGULAMA (hem paylasan hem baglanan)
- Port acmaya / IP ayarina gerek yok. Iki taraf da relay'e DISARI dogru baglanir.
- Paylasan: "Ekranimi Paylas" -> rastgele KOD alir, karsiya verir.
- Baglanan: KODU girer -> "Baglan" -> paylasana ONAY penceresi cikar.
- Kabul edilince uzaktan fare/klavye kontrolu baslar (VNC mantigi).
- DEGISEN BOLGE AKISI: ekran bir izgaraya bolunur, her karede sadece
  degisen kareler gonderilir. Ekran dururken trafik ~sifir.
Gereken: pip install websocket-client mss pillow pynput
Relay adresi: relay.txt (ws://SUNUCU:8765 ya da wss://ad.ts.net) / EHM_RELAY.
"""
import os, sys, io, json, time, threading, queue, secrets

PRESETS = {"Akıcı": (1024, 15, 30), "Dengeli": (1280, 8, 50), "Keskin": (1920, 5, 85)}  # (maxw,fps,q)

def _cfg_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, "EHM-Uzak-Destek")
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
    return d

def _load_settings():
    try:
        fp = os.path.join(_cfg_dir(), "settings.json")
        if os.path.exists(fp):
            return json.load(open(fp, encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save_settings(d):
    try:
        json.dump(d, open(os.path.join(_cfg_dir(), "settings.json"), "w", encoding="utf-8"))
        return True
    except Exception:
        return False

SETTINGS = _load_settings()

def _find_relay():
    v = os.environ.get("EHM_RELAY")
    if v: return v
    v = SETTINGS.get("relay")
    if v: return v
    cands = [_cfg_dir()]
    try: cands.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception: pass
    try: cands.append(os.path.dirname(os.path.abspath(sys.executable)))
    except Exception: pass
    cands.append(os.getcwd())
    for base in cands:
        try:
            fp = os.path.join(base, "relay.txt")
            if os.path.exists(fp):
                t = open(fp, encoding="utf-8").read().strip()
                if t: return t
        except Exception:
            pass
    return "ws://CHANGE_ME:8765"

RELAY_URL = _find_relay()

def _mode_to_cfg(name):
    if name in PRESETS:
        maxw, fps, q = PRESETS[name]
        return {"fps": fps, "q": q, "maxw": maxw}
    return {"fps": FPS, "q": QUALITY, "maxw": MAXW}

# ---- Windows: yonetici / otomatik baslat ----
def _is_admin_win():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def _win_elevate():
    try:
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            return
        if getattr(sys, "frozen", False):
            exe = sys.executable; params = ""
        else:
            exe = sys.executable; params = '"%s"' % os.path.abspath(__file__)
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        if r is not None and int(r) > 32:
            sys.exit(0)  # yetkili kopya acildi, bunu kapat
        # reddedildi/basarisiz -> yetkisiz devam
    except Exception:
        pass

def _win_autostart(enable):
    import winreg
    name = "EHM-Uzak-Destek"
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Run",
                         0, winreg.KEY_SET_VALUE)
    try:
        if enable:
            if getattr(sys, "frozen", False):
                cmd = '"%s"' % sys.executable
            else:
                cmd = '"%s" "%s"' % (sys.executable, os.path.abspath(__file__))
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, cmd)
        else:
            try: winreg.DeleteValue(key, name)
            except FileNotFoundError: pass
    finally:
        winreg.CloseKey(key)

def _win_autostart_state():
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run")
        v, _ = winreg.QueryValueEx(key, "EHM-Uzak-Destek")
        winreg.CloseKey(key)
        return bool(v)
    except Exception:
        return False

# --- ayarlanabilir kalite ---
MAXW = int(os.environ.get("EHM_MAXW", "1280"))   # calisma genisligi (px)
FPS = int(os.environ.get("EHM_FPS", "10"))       # saniyedeki tarama
TILE = int(os.environ.get("EHM_TILE", "128"))    # kare (tile) boyutu
QUALITY = int(os.environ.get("EHM_Q", "50"))     # JPEG kalite
KEYFRAME_EVERY = 15.0                            # sn'de bir tam yenileme (sigorta)

import tkinter as tk
from tkinter import messagebox

try:
    import websocket  # websocket-client
except Exception:
    _r = tk.Tk(); _r.withdraw()
    messagebox.showerror("Eksik paket", "Once kur:\n\npip install websocket-client mss pillow pynput")
    raise

try:
    import certifi
except Exception:
    certifi = None

try:
    import mss as _mss
except Exception:
    _mss = None
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None; ImageTk = None
try:
    from pynput.mouse import Controller as MouseCtl, Button as MouseBtn
    from pynput.keyboard import Controller as KeyCtl, Key as KKey
except Exception:
    MouseCtl = KeyCtl = MouseBtn = KKey = None

def build_special():
    m = {}
    if KeyCtl is None:
        return m
    names = {
        "Return": "enter", "BackSpace": "backspace", "Tab": "tab",
        "Escape": "esc", "space": "space", "Delete": "delete",
        "Home": "home", "End": "end", "Prior": "page_up", "Next": "page_down",
        "Up": "up", "Down": "down", "Left": "left", "Right": "right",
        "Shift_L": "shift", "Shift_R": "shift_r",
        "Control_L": "ctrl", "Control_R": "ctrl_r",
        "Alt_L": "alt", "Alt_R": "alt_r",
        "Caps_Lock": "caps_lock", "Insert": "insert",
        "Super_L": "cmd", "Super_R": "cmd_r", "Win_L": "cmd", "Win_R": "cmd_r",
    }
    for i in range(1, 13):
        names["F%d" % i] = "f%d" % i
    for sym, attr in names.items():
        k = getattr(KKey, attr, None)   # platformda yoksa atla (ör. macOS'ta insert yok)
        if k is not None:
            m[sym] = k
    return m
SPECIAL = build_special()

# ---- degisen-bolge yardimcilari (test edilebilir, modul seviyesinde) ----
def encode_tiles(img, prev, tile, quality, force_key):
    """img icinden prev'e gore degismis kareleri uretir.
    Doner: (mesaj_listesi, yeni_prev). Her mesaj: 8 bayt baslik
    (x,y,w,h big-endian uint16) + JPEG."""
    W, H = img.size
    msgs = []
    newprev = dict(prev)
    cols = (W + tile - 1) // tile
    rows = (H + tile - 1) // tile
    for ry in range(rows):
        for cx in range(cols):
            x = cx * tile; y = ry * tile
            w = min(tile, W - x); h = min(tile, H - y)
            t = img.crop((x, y, x + w, y + h))
            hsh = hash(t.tobytes())
            if (not force_key) and prev.get((cx, ry)) == hsh:
                continue
            newprev[(cx, ry)] = hsh
            buf = io.BytesIO(); t.save(buf, "JPEG", quality=quality)
            header = (x.to_bytes(2, "big") + y.to_bytes(2, "big") +
                      w.to_bytes(2, "big") + h.to_bytes(2, "big"))
            msgs.append(header + buf.getvalue())
    return msgs, newprev

def apply_tile(buf_img, b):
    """Gelen tile mesajini buffer imajina yapistirir."""
    x = int.from_bytes(b[0:2], "big"); y = int.from_bytes(b[2:4], "big")
    tile = Image.open(io.BytesIO(b[8:])); tile.load()
    buf_img.paste(tile, (x, y))

class Conn:
    def __init__(self, url, on_text, on_bin, on_open, on_close):
        self.url = url; self.on_text = on_text; self.on_bin = on_bin
        self.on_open = on_open; self.on_close = on_close
        self.ws = None; self.lock = threading.Lock()
    def start(self):
        kw = {}
        if self.url.startswith("wss"):
            if os.environ.get("EHM_INSECURE") == "1":
                import ssl; kw["sslopt"] = {"cert_reqs": ssl.CERT_NONE}
            elif certifi is not None:
                kw["sslopt"] = {"ca_certs": certifi.where()}
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=lambda w: self.on_open(),
            on_close=lambda w, a, b: self.on_close(),
            on_error=lambda w, e: None,
            on_message=lambda w, m: (self.on_bin(m) if isinstance(m, (bytes, bytearray)) else self.on_text(m)),
        )
        threading.Thread(
            target=lambda: self.ws.run_forever(ping_interval=20, ping_timeout=10, **kw),
            daemon=True).start()
    def text(self, obj):
        with self.lock:
            try: self.ws.send(json.dumps(obj), opcode=websocket.ABNF.OPCODE_TEXT)
            except Exception: pass
    def binary(self, b):
        with self.lock:
            try: self.ws.send(b, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception: pass
    def close(self):
        try: self.ws.close()
        except Exception: pass

class App:
    def __init__(self, root):
        self.root = root
        root.title("EHM Uzak Destek")
        root.geometry("460x420")
        self.q = queue.Queue()
        self.conn = None
        self.mode = None
        self.streaming = False
        self.peer_active = False
        self.viewer_win = None
        self.view_box = (0, 0, 1, 1)
        self.host_w = 1; self.host_h = 1
        self._tkimg = None
        self._pending_code = None
        # viewer buffer
        self.buf = None
        self.buf_dirty = False
        self._render_job = None
        self.cfg = _mode_to_cfg(SETTINGS.get("mode"))
        self._rx_bytes = 0
        self._bw_job = None
        self._build()
        self.root.after(30, self._pump)

    def _build(self):
        f = tk.Frame(self.root, padx=16, pady=14); f.pack(fill="both", expand=True)
        tk.Label(f, text="EHM Uzak Destek", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        self.status = tk.Label(f, text="Hazir", fg="#555"); self.status.pack(anchor="w", pady=(0, 10))

        s = tk.LabelFrame(f, text="Ekranimi Paylas (destek al)", padx=10, pady=8); s.pack(fill="x")
        self.share_btn = tk.Button(s, text="Ekranimi Paylas", command=self.start_host)
        self.share_btn.pack(side="left")
        self.code_lbl = tk.Label(s, text="", font=("Consolas", 17, "bold"), fg="#0a7")
        self.code_lbl.pack(side="left", padx=12)

        c = tk.LabelFrame(f, text="Baglan (destek ver)", padx=10, pady=8); c.pack(fill="x", pady=(12, 0))
        tk.Label(c, text="Kod:").pack(side="left")
        self.code_entry = tk.Entry(c, width=12, font=("Consolas", 13)); self.code_entry.pack(side="left", padx=6)
        self.conn_btn = tk.Button(c, text="Baglan", command=self.start_viewer); self.conn_btn.pack(side="left")

        row = tk.Frame(f); row.pack(fill="x", pady=(12, 0))
        tk.Button(row, text="Ayarlar", command=self._open_settings).pack(side="left")
        self.admin_lbl = tk.Label(row, text="", fg="#888", font=("Segoe UI", 8)); self.admin_lbl.pack(side="right")
        self.relay_lbl = tk.Label(f, text="Relay: " + RELAY_URL, fg="#999", font=("Segoe UI", 8))
        self.relay_lbl.pack(anchor="w", side="bottom")
        self._update_admin_lbl()

    def set_status(self, t):
        self.status.config(text=t)

    def ensure_conn(self):
        if self.conn is None:
            self.conn = Conn(RELAY_URL,
                             on_text=lambda m: self.q.put(("text", m)),
                             on_bin=lambda b: self.q.put(("bin", b)),
                             on_open=lambda: self.q.put(("open", None)),
                             on_close=lambda: self.q.put(("close", None)))
            self.conn.start()

    def start_host(self):
        if _mss is None or MouseCtl is None:
            messagebox.showerror("Eksik paket", "pip install mss pillow pynput"); return
        self.mode = "host"; self.set_status("Relay'e baglaniliyor...")
        self.share_btn.config(state="disabled"); self.conn_btn.config(state="disabled")
        self.ensure_conn()

    def start_viewer(self):
        code = self.code_entry.get().strip()
        if not code:
            messagebox.showwarning("Kod", "Kod girin."); return
        if Image is None:
            messagebox.showerror("Eksik paket", "pip install pillow"); return
        self.mode = "viewer"; self._pending_code = code; self.set_status("Relay'e baglaniliyor...")
        self.share_btn.config(state="disabled"); self.conn_btn.config(state="disabled")
        self.ensure_conn()

    def _pump(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "open": self._on_open()
                elif kind == "close": self._on_close()
                elif kind == "text": self._on_text(data)
                elif kind == "bin": self._on_bin(data)
        except queue.Empty:
            pass
        self.root.after(25, self._pump)

    def _on_open(self):
        if self.mode == "host":
            self.conn.text({"type": "host"}); self.set_status("Kod aliniyor...")
        elif self.mode == "viewer":
            self.conn.text({"type": "connect", "code": self._pending_code}); self.set_status("Onay bekleniyor...")

    def _on_close(self):
        self.set_status("Baglanti kapandi")
        self.streaming = False; self.peer_active = False
        self.share_btn.config(state="normal"); self.conn_btn.config(state="normal")

    def _reset(self):
        self.set_status("Hazir")
        self.share_btn.config(state="normal"); self.conn_btn.config(state="normal")

    def _on_text(self, m):
        try: d = json.loads(m)
        except Exception: return
        t = d.get("type")
        if t == "hosting":
            self.code_lbl.config(text=d["code"])
            self.set_status("KODU karsiya verin. Baglanti bekleniyor...")
        elif t == "request":
            self._approve_dialog()
        elif t == "approved":
            self.set_status("Onaylandi. Uzak ekran aciliyor...")
            self._open_viewer()
        elif t == "rejected":
            messagebox.showinfo("Reddedildi", "Karsi taraf reddetti."); self._reset()
        elif t == "error":
            msg = {"invalid_code": "Gecersiz kod", "busy": "Bu oturum dolu"}.get(d.get("msg"), d.get("msg", ""))
            messagebox.showerror("Hata", msg); self._reset()
        elif t == "meta":
            W = int(d.get("w", 0)); H = int(d.get("h", 0))
            if W > 0 and H > 0 and Image is not None:
                self.buf = Image.new("RGB", (W, H), (16, 16, 16))
                self.buf_dirty = True
        elif t in ("ended", "peer_left"):
            self.set_status("Karsi taraf ayrildi")
            self.streaming = False; self.peer_active = False
            if self.viewer_win:
                try: self.viewer_win.destroy()
                except Exception: pass
                self.viewer_win = None
        elif t == "in":
            if self.mode == "host" and self.peer_active:
                self._inject(d)
        elif t == "cfg":
            if self.mode == "host":
                c = self.cfg
                if "fps" in d: c["fps"] = max(1, min(30, int(d["fps"])))
                if "q" in d: c["q"] = max(10, min(95, int(d["q"])))
                if "maxw" in d: c["maxw"] = max(320, min(3840, int(d["maxw"])))

    def _on_bin(self, b):
        if self.mode != "viewer":
            return
        self._rx_bytes += len(b)
        if self.buf is None:
            return
        try:
            if len(b) < 8:
                return
            apply_tile(self.buf, b)
            self.buf_dirty = True
        except Exception:
            pass

    def _approve_dialog(self):
        win = tk.Toplevel(self.root); win.title("Baglanti Istegi"); win.attributes("-topmost", True)
        tk.Label(win, text="Birisi ekraniniza baglanmak istiyor.\nKABUL ederseniz fare ve klavyenizi kontrol edebilir.",
                 padx=20, pady=16, justify="left").pack()
        bf = tk.Frame(win, pady=8); bf.pack()
        def ok():
            win.destroy(); self.conn.text({"type": "approve"})
            self.peer_active = True; self._start_stream()
            self.set_status("Baglandi - ekran paylasiliyor")
        def no():
            win.destroy(); self.conn.text({"type": "reject"}); self.set_status("Reddedildi - kod bekleniyor")
        tk.Button(bf, text="KABUL ET", width=12, bg="#0a7", fg="white", command=ok).pack(side="left", padx=6)
        tk.Button(bf, text="Reddet", width=12, command=no).pack(side="left", padx=6)
        win.protocol("WM_DELETE_WINDOW", no)

    def _start_stream(self):
        if self.streaming: return
        self.streaming = True
        self.mouse = MouseCtl(); self.kb = KeyCtl()
        try:
            with _mss.mss() as s:
                mon = s.monitors[1]; self.host_w = mon["width"]; self.host_h = mon["height"]
        except Exception:
            self.host_w = 1920; self.host_h = 1080
        threading.Thread(target=self._stream_loop, daemon=True).start()

    def _stream_loop(self):
        prev = {}
        last_wh = None
        last_key = 0.0
        try:
            with _mss.mss() as sct:
                mon = sct.monitors[1]
                self.host_w = mon["width"]; self.host_h = mon["height"]
                while self.streaming and self.peer_active:
                    t0 = time.time()
                    fps = max(1, int(self.cfg.get("fps", FPS)))
                    maxw = max(320, int(self.cfg.get("maxw", MAXW)))
                    q = max(10, min(95, int(self.cfg.get("q", QUALITY))))
                    interval = 1.0 / fps
                    try:
                        shot = sct.grab(mon)
                        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                        if img.width > maxw:
                            h = int(img.height * maxw / img.width)
                            img = img.resize((maxw, h))
                        W, H = img.size
                        force_key = False
                        if (W, H) != last_wh:
                            self.conn.text({"type": "meta", "w": W, "h": H, "tile": TILE})
                            last_wh = (W, H); prev = {}; force_key = True
                        if t0 - last_key >= KEYFRAME_EVERY:
                            force_key = True; last_key = t0
                        msgs, prev = encode_tiles(img, prev, TILE, q, force_key)
                        for mb in msgs:
                            self.conn.binary(mb)
                    except Exception:
                        pass
                    dt = time.time() - t0
                    if dt < interval:
                        time.sleep(interval - dt)
        except Exception:
            pass

    def _inject(self, d):
        try:
            a = d.get("a")
            if a == "move":
                self.mouse.position = (int(d["x"] * self.host_w), int(d["y"] * self.host_h))
            elif a in ("ldown", "lup", "rdown", "rup"):
                self.mouse.position = (int(d["x"] * self.host_w), int(d["y"] * self.host_h))
                btn = MouseBtn.left if a[0] == "l" else MouseBtn.right
                (self.mouse.press if a.endswith("down") else self.mouse.release)(btn)
            elif a == "scroll":
                self.mouse.scroll(0, d.get("dy", 0))
            elif a == "key":
                k = self._mapkey(d.get("sym"), d.get("ch"))
                if k is None: return
                if d.get("down"): self.kb.press(k)
                else: self.kb.release(k)
        except Exception:
            pass

    def _mapkey(self, sym, ch):
        if sym in SPECIAL: return SPECIAL[sym]
        if ch and len(ch) == 1 and ch.isprintable(): return ch
        if sym and len(sym) == 1 and sym.isprintable(): return sym
        return None

    def _open_viewer(self):
        if self.viewer_win: return
        self.buf = None; self.buf_dirty = False
        w = tk.Toplevel(self.root); self.viewer_win = w
        w.title("Uzak Ekran - EHM"); w.geometry("1100x700")
        bar = tk.Frame(w, bg="#20202b"); bar.pack(fill="x")
        self.var_preset = tk.StringVar(value="Dengeli")
        self.var_res = tk.StringVar(value="1280")
        self.var_fps = tk.StringVar(value="8")
        self.var_q = tk.StringVar(value="Orta")
        def _mk(lbl, var, opts, cb):
            tk.Label(bar, text=lbl, fg="#ccc", bg="#20202b").pack(side="left", padx=(8, 2))
            om = tk.OptionMenu(bar, var, *opts, command=lambda e: cb())
            om.config(highlightthickness=0, takefocus=0, bg="#2d2d3a", fg="#fff")
            om.pack(side="left", padx=2, pady=4)
        _mk("Mod", self.var_preset, ["Akıcı", "Dengeli", "Keskin", "Özel"], self._apply_preset)
        _mk("Çözünürlük", self.var_res, ["800", "1024", "1280", "1600", "1920"], self._cfg_from_ui)
        _mk("FPS", self.var_fps, ["3", "5", "8", "12", "15"], self._cfg_from_ui)
        _mk("Kalite", self.var_q, ["Düşük", "Orta", "Yüksek", "Çok Yüksek"], self._cfg_from_ui)
        self.bw_lbl = tk.Label(bar, text="0 KB/s", fg="#0ad", bg="#20202b", font=("Consolas", 10, "bold"))
        self.bw_lbl.pack(side="right", padx=10)
        self.canvas = tk.Canvas(w, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.focus_set()
        c = self.canvas
        c.bind("<Motion>", lambda e: self._vsend("move", e))
        c.bind("<ButtonPress-1>", lambda e: self._vsend("ldown", e))
        c.bind("<ButtonRelease-1>", lambda e: self._vsend("lup", e))
        c.bind("<ButtonPress-3>", lambda e: self._vsend("rdown", e))
        c.bind("<ButtonRelease-3>", lambda e: self._vsend("rup", e))
        c.bind("<MouseWheel>", lambda e: self.conn.text({"type": "in", "a": "scroll", "dy": (1 if e.delta > 0 else -1)}))
        c.bind("<KeyPress>", lambda e: self._ksend(e, True))
        c.bind("<KeyRelease>", lambda e: self._ksend(e, False))
        c.bind("<Enter>", lambda e: c.focus_set())
        w.protocol("WM_DELETE_WINDOW", self._close_viewer)
        self._render_tick()
        self._bw_tick()
        self._send_cfg()

    def _close_viewer(self):
        self.streaming = False; self.peer_active = False
        if self._render_job:
            try: self.root.after_cancel(self._render_job)
            except Exception: pass
            self._render_job = None
        if self._bw_job:
            try: self.root.after_cancel(self._bw_job)
            except Exception: pass
            self._bw_job = None
        try: self.conn.close()
        except Exception: pass
        if self.viewer_win:
            try: self.viewer_win.destroy()
            except Exception: pass
            self.viewer_win = None
        self.conn = None
        self._reset()

    def _render_tick(self):
        if not self.viewer_win:
            self._render_job = None; return
        if self.buf_dirty and self.buf is not None:
            self.buf_dirty = False
            self._blit()
        self._render_job = self.root.after(40, self._render_tick)

    def _blit(self):
        try:
            cw = self.canvas.winfo_width(); ch = self.canvas.winfo_height()
            if cw < 10 or ch < 10: cw, ch = 1100, 680
            iw, ih = self.buf.size
            scale = min(cw / iw, ch / ih)
            nw = max(1, int(iw * scale)); nh = max(1, int(ih * scale))
            disp = self.buf.resize((nw, nh))
            x0 = (cw - nw) // 2; y0 = (ch - nh) // 2
            self.view_box = (x0, y0, nw, nh)
            self._tkimg = ImageTk.PhotoImage(disp)
            self.canvas.delete("all")
            self.canvas.create_image(x0, y0, anchor="nw", image=self._tkimg)
        except Exception:
            pass

    def _update_admin_lbl(self):
        try:
            if sys.platform == "win32":
                self.admin_lbl.config(text=("Yönetici: Evet" if _is_admin_win() else "Yönetici: Hayır"))
            else:
                self.admin_lbl.config(text="")
        except Exception:
            pass

    def _save_relay(self, url):
        global RELAY_URL
        url = (url or "").strip()
        if not url:
            return
        RELAY_URL = url
        SETTINGS["relay"] = url
        _save_settings(SETTINGS)

    def _open_settings(self):
        win = tk.Toplevel(self.root); win.title("Ayarlar"); win.transient(self.root)
        win.geometry("470x330"); win.attributes("-topmost", True)
        tk.Label(win, text="Relay adresi (ws:// veya wss://):").pack(anchor="w", padx=12, pady=(12, 2))
        rv = tk.StringVar(value=RELAY_URL)
        tk.Entry(win, textvariable=rv, width=50).pack(anchor="w", padx=12)
        def save_relay():
            self._save_relay(rv.get())
            try: self.relay_lbl.config(text="Relay: " + RELAY_URL)
            except Exception: pass
            messagebox.showinfo("Ayarlar", "Relay adresi kaydedildi.\nYeni baglantilarda kullanilacak.")
        tk.Button(win, text="Relay'i Kaydet", command=save_relay).pack(anchor="w", padx=12, pady=(4, 10))

        tk.Label(win, text="Varsayilan yayin modu (ekran paylasirken):").pack(anchor="w", padx=12)
        mv = tk.StringVar(value=SETTINGS.get("mode", "Dengeli"))
        tk.OptionMenu(win, mv, "Akıcı", "Dengeli", "Keskin").pack(anchor="w", padx=12)
        def save_mode(*a):
            SETTINGS["mode"] = mv.get(); _save_settings(SETTINGS)
            self.cfg = _mode_to_cfg(mv.get())
        mv.trace_add("write", save_mode)

        if sys.platform == "win32":
            av = tk.BooleanVar(value=_win_autostart_state())
            def toggle_auto():
                try: _win_autostart(av.get())
                except Exception as e: messagebox.showerror("Hata", str(e))
            tk.Checkbutton(win, text="Windows acilisinda otomatik baslat",
                           variable=av, command=toggle_auto).pack(anchor="w", padx=12, pady=(10, 4))
            adm = _is_admin_win()
            tk.Label(win, text="Yonetici olarak calisiyor: " + ("Evet" if adm else "Hayir"),
                     fg=("#0a7" if adm else "#c33")).pack(anchor="w", padx=12)
            if not adm:
                tk.Label(win, text="(Yonetici degilsen bazi pencereleri kontrol edemezsin)",
                         fg="#888", font=("Segoe UI", 8)).pack(anchor="w", padx=12)
        tk.Button(win, text="Kapat", command=win.destroy).pack(side="bottom", pady=10)

    def _q_val(self, name):
        return {"Düşük": 30, "Orta": 50, "Yüksek": 70, "Çok Yüksek": 85}.get(name, 50)

    def _apply_preset(self):
        presets = {"Akıcı": ("1024", "15", "Düşük"),
                   "Dengeli": ("1280", "8", "Orta"),
                   "Keskin": ("1920", "5", "Çok Yüksek")}
        p = self.var_preset.get()
        if p in presets:
            r, f, q = presets[p]
            self.var_res.set(r); self.var_fps.set(f); self.var_q.set(q)
        self._send_cfg()

    def _cfg_from_ui(self):
        self.var_preset.set("Özel")
        self._send_cfg()

    def _send_cfg(self):
        if not self.conn:
            return
        try:
            self.conn.text({"type": "cfg",
                            "maxw": int(self.var_res.get()),
                            "fps": int(self.var_fps.get()),
                            "q": self._q_val(self.var_q.get())})
        except Exception:
            pass

    def _bw_tick(self):
        if not self.viewer_win:
            self._bw_job = None; return
        kb = self._rx_bytes / 1024.0
        self._rx_bytes = 0
        try: self.bw_lbl.config(text="%.0f KB/s" % kb)
        except Exception: pass
        self._bw_job = self.root.after(1000, self._bw_tick)

    def _norm(self, e):
        x0, y0, w, h = self.view_box
        if w <= 0 or h <= 0: return None
        nx = (e.x - x0) / w; ny = (e.y - y0) / h
        if nx < 0 or nx > 1 or ny < 0 or ny > 1: return None
        return nx, ny

    def _vsend(self, a, e):
        p = self._norm(e)
        if p is None: return
        self.conn.text({"type": "in", "a": a, "x": p[0], "y": p[1]})

    def _ksend(self, e, down):
        self.conn.text({"type": "in", "a": "key", "sym": e.keysym, "ch": e.char, "down": down})

def main():
    if sys.platform == "win32" and os.environ.get("EHM_NOADMIN") != "1":
        _win_elevate()
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
