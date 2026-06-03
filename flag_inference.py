"""
flag_inference.py — Flag Pattern Live Inference Tray App
With Telegram notification support.

Install:
    pip install pystray mss pillow keyboard ultralytics plyer python-dotenv requests

Setup:
    Create .env file with:
        BOT_TOKEN=your_token_here
        CHAT_ID=your_chat_id_here

Usage:
    python flag_inference.py
    1. Right-click tray → Set Capture Area
    2. Right-click tray → Set Model Path
    3. Press Ctrl+Shift+D to run inference
"""

import io
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import keyboard
import mss
import mss.tools
import pystray
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageTk
from plyer import notification

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    print("tkinter not found")
    sys.exit(1)

# ── Load env ──────────────────────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("CHAT_ID", "")

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE = "config.json"
HOTKEY      = "ctrl+shift+d"
ICON_SIZE   = 64
CONF_THRESH = 0.25
TIMEZONE    = ZoneInfo("Asia/Singapore")
BOX_COLOR   = (240, 180, 41)

# ── Config helpers ─────────────────────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def notify(title, msg):
    threading.Thread(
        target=lambda: notification.notify(title=title, message=msg, timeout=2),
        daemon=True
    ).start()

# ── Telegram ───────────────────────────────────────────────────────────────────

def tele_send_photo(image: Image.Image, detections: list):
    """Send annotated screenshot to Telegram with caption."""
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram not configured — check .env file")
        return

    now      = datetime.now(tz=TIMEZONE)
    count    = len(detections)
    conf_max = max([d["conf"] for d in detections]) if detections else 0

    caption = (
        f"🚩 *FLAG PATTERN DETECTED*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Symbol  : `XAUUSD M1`\n"
        f"Time    : `{now.strftime('%H:%M:%S')} SGT`\n"
        f"Date    : `{now.strftime('%Y-%m-%d')}`\n"
        f"Count   : `{count} pattern{'s' if count > 1 else ''}`\n"
        f"Conf    : `{conf_max:.2f}`\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"_Review chart before entry_"
    )

    # Convert PIL image to bytes
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        resp = requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
            files={"photo": ("chart.png", buf, "image/png")},
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"Telegram sent ✓")
        else:
            print(f"Telegram error: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Telegram send failed: {e}")


def tele_test():
    """Send a test message to verify bot is working."""
    if not BOT_TOKEN or not CHAT_ID:
        notify("Telegram", "BOT_TOKEN or CHAT_ID missing in .env")
        return
    try:
        url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            data={"chat_id": CHAT_ID, "text": "✅ Flag Inference bot connected successfully!"},
            timeout=10,
        )
        if resp.status_code == 200:
            notify("Telegram", "Test message sent ✓ Check your Telegram")
        else:
            notify("Telegram", f"Failed: {resp.status_code}")
    except Exception as e:
        notify("Telegram", f"Error: {e}")

# ── Tray icon ──────────────────────────────────────────────────────────────────

def make_icon():
    img  = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(18, 18, 26))
    draw.rounded_rectangle([14, 22, 50, 46], radius=4, fill=(240, 180, 41))
    draw.ellipse([24, 26, 40, 42], fill=(18, 18, 26))
    draw.ellipse([27, 29, 37, 39], fill=(80, 80, 120))
    draw.rounded_rectangle([20, 18, 30, 24], radius=2, fill=(240, 180, 41))
    return img

# ── Area selector ──────────────────────────────────────────────────────────────

class AreaSelector:
    def __init__(self, callback):
        self.callback = callback
        self.start_x  = 0
        self.start_y  = 0
        self.rect_id  = None

        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.35)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black", cursor="crosshair")
        self.root.overrideredirect(True)

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2, 40,
            text="Drag to select chart area  ·  ESC to cancel",
            fill="white", font=("Courier New", 16),
        )

        self.canvas.bind("<ButtonPress-1>",   self.on_press)
        self.canvas.bind("<B1-Motion>",        self.on_drag)
        self.canvas.bind("<ButtonRelease-1>",  self.on_release)
        self.root.bind("<Escape>",             lambda e: self.root.destroy())
        self.root.mainloop()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def on_drag(self, event):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline="#f0b429", width=2, fill="#f0b42920"
        )

    def on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.root.destroy()
        if (x2 - x1) > 20 and (y2 - y1) > 20:
            self.callback({"x1": x1, "y1": y1, "x2": x2, "y2": y2})

# ── Inference overlay window ───────────────────────────────────────────────────

class InferenceWindow:
    def __init__(self, image: Image.Image, detections: list, area: dict):
        self.root = tk.Tk()
        self.root.title("Flag Inference")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0a0a0f")
        self.root.resizable(True, True)

        win_x = area["x1"]
        win_y = max(0, area["y1"] - 60)
        self.root.geometry(f"+{win_x}+{win_y}")

        # Header
        header = tk.Frame(self.root, bg="#12121a", pady=8)
        header.pack(fill="x")

        count        = len(detections)
        status_color = "#f0b429" if count > 0 else "#555570"
        status_text  = f"  ⬡  {count} FLAG PATTERN{'S' if count != 1 else ''} DETECTED" if count > 0 else "  ○  NO PATTERNS DETECTED"

        tk.Label(
            header, text=status_text,
            bg="#12121a", fg=status_color,
            font=("Courier New", 11, "bold")
        ).pack(side="left", padx=12)

        tk.Label(
            header,
            text=f"conf≥{CONF_THRESH}  ·  {datetime.now(tz=TIMEZONE).strftime('%H:%M:%S')} SGT",
            bg="#12121a", fg="#555570",
            font=("Courier New", 9)
        ).pack(side="right", padx=12)

        # Annotated image
        annotated     = self._draw_boxes(image.copy(), detections)
        self.photo    = ImageTk.PhotoImage(annotated)
        tk.Label(self.root, image=self.photo, bg="#0a0a0f").pack(padx=2, pady=2)

        # Detection list
        if detections:
            det_frame = tk.Frame(self.root, bg="#12121a", pady=6)
            det_frame.pack(fill="x")
            for i, d in enumerate(detections):
                tk.Label(
                    det_frame,
                    text=f"  [{i+1}]  {d['class']}  ·  conf: {d['conf']:.2f}",
                    bg="#12121a", fg="#888899",
                    font=("Courier New", 9)
                ).pack(anchor="w", padx=12)

        # Close button
        btn_frame = tk.Frame(self.root, bg="#0a0a0f", pady=6)
        btn_frame.pack(fill="x")
        tk.Button(
            btn_frame, text="Close  [ESC]",
            bg="#1e1e2e", fg="#888899",
            font=("Courier New", 9),
            relief="flat", bd=0,
            command=self.root.destroy,
            cursor="hand2"
        ).pack(pady=4)

        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.mainloop()

    def _draw_boxes(self, img: Image.Image, detections: list) -> Image.Image:
        draw = ImageDraw.Draw(img, "RGBA")
        try:
            font = ImageFont.truetype("consola.ttf", 13)
        except Exception:
            font = ImageFont.load_default()

        for det in detections:
            x1, y1, x2, y2 = det["box"]
            conf  = det["conf"]
            label = f"{det['class']} {conf:.2f}"

            draw.rectangle([x1, y1, x2, y2], outline=BOX_COLOR, width=2)

            corner = 12
            for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                draw.line([(cx, cy), (cx + dx*corner, cy)], fill=BOX_COLOR, width=3)
                draw.line([(cx, cy), (cx, cy + dy*corner)], fill=BOX_COLOR, width=3)

            bbox = draw.textbbox((x1, y1 - 20), label, font=font)
            draw.rectangle([bbox[0]-4, bbox[1]-2, bbox[2]+4, bbox[3]+2], fill=(18, 18, 26, 200))
            draw.text((x1, y1 - 20), label, fill=BOX_COLOR, font=font)

        return img

# ── Model ──────────────────────────────────────────────────────────────────────

_model      = None
_model_path = None

def load_model(path: str):
    global _model, _model_path
    try:
        from ultralytics import YOLO
        _model      = YOLO(path)
        _model_path = path
        print(f"Model loaded: {path}")
        return True
    except Exception as e:
        print(f"Model load error: {e}")
        return False

# ── Core inference ─────────────────────────────────────────────────────────────

def run_inference(icon=None, item=None):
    cfg        = load_config()
    area       = cfg.get("area")
    model_path = cfg.get("model_path")

    if not area:
        notify("Flag Inference", "No area set — right-click → Set Capture Area")
        return
    if not model_path:
        notify("Flag Inference", "No model set — right-click → Set Model Path")
        return
    if _model is None:
        if not load_model(model_path):
            notify("Flag Inference", "Failed to load model")
            return

    # Capture
    monitor = {
        "top":    area["y1"],
        "left":   area["x1"],
        "width":  area["x2"] - area["x1"],
        "height": area["y2"] - area["y1"],
    }
    with mss.mss() as sct:
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.rgb)

    # Inference
    results    = _model(img, conf=CONF_THRESH, verbose=False)
    detections = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            detections.append({
                "class": _model.names[int(box.cls[0])],
                "conf":  float(box.conf[0]),
                "box":   (x1, y1, x2, y2)
            })

    count = len(detections)
    print(f"[{datetime.now(tz=TIMEZONE).strftime('%H:%M:%S')}] {count} pattern(s) detected")

    # Draw boxes for Telegram photo
    annotated = _draw_boxes_static(img.copy(), detections)

    # Send Telegram only if pattern found
    if count > 0:
        threading.Thread(
            target=lambda: tele_send_photo(annotated, detections),
            daemon=True
        ).start()

    # Show overlay window
    threading.Thread(
        target=lambda: InferenceWindow(img, detections, area),
        daemon=True
    ).start()


def _draw_boxes_static(img: Image.Image, detections: list) -> Image.Image:
    """Standalone box drawing for Telegram photo (no tkinter dependency)."""
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("consola.ttf", 13)
    except Exception:
        font = ImageFont.load_default()

    for det in detections:
        x1, y1, x2, y2 = det["box"]
        label = f"{det['class']} {det['conf']:.2f}"
        draw.rectangle([x1, y1, x2, y2], outline=BOX_COLOR, width=2)
        corner = 12
        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
            draw.line([(cx, cy), (cx + dx*corner, cy)], fill=BOX_COLOR, width=3)
            draw.line([(cx, cy), (cx, cy + dy*corner)], fill=BOX_COLOR, width=3)
        bbox = draw.textbbox((x1, y1 - 20), label, font=font)
        draw.rectangle([bbox[0]-4, bbox[1]-2, bbox[2]+4, bbox[3]+2], fill=(18, 18, 26, 200))
        draw.text((x1, y1 - 20), label, fill=BOX_COLOR, font=font)
    return img

# ── Auto scan ──────────────────────────────────────────────────────────────────

_auto_scan_running = False
_auto_scan_thread  = None
AUTO_SCAN_INTERVAL = 60   # seconds


def auto_scan_loop():
    global _auto_scan_running
    print(f"Auto scan started — every {AUTO_SCAN_INTERVAL}s")
    notify("Flag Inference", f"Auto scan started — every {AUTO_SCAN_INTERVAL}s")
    while _auto_scan_running:
        run_inference()
        # Sleep in small chunks so we can stop quickly
        for _ in range(AUTO_SCAN_INTERVAL * 10):
            if not _auto_scan_running:
                break
            time.sleep(0.1)
    print("Auto scan stopped")
    notify("Flag Inference", "Auto scan stopped")


def start_auto_scan(icon=None, item=None):
    global _auto_scan_running, _auto_scan_thread
    if _auto_scan_running:
        return
    _auto_scan_running = True
    _auto_scan_thread  = threading.Thread(target=auto_scan_loop, daemon=True)
    _auto_scan_thread.start()


def stop_auto_scan(icon=None, item=None):
    global _auto_scan_running
    _auto_scan_running = False


# ── Tray actions ───────────────────────────────────────────────────────────────

def set_capture_area(icon=None, item=None):
    def on_selected(coords):
        cfg = load_config()
        cfg["area"] = coords
        save_config(cfg)
        notify("Flag Inference", f"Area set! Press {HOTKEY.upper()} to run.")
    threading.Thread(target=lambda: AreaSelector(on_selected), daemon=True).start()


def set_model_path(icon=None, item=None):
    def pick():
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Select best.pt",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")]
        )
        root.destroy()
        if path:
            cfg = load_config()
            cfg["model_path"] = path
            save_config(cfg)
            load_model(path)
            notify("Flag Inference", f"Model loaded: {Path(path).name}")
    threading.Thread(target=pick, daemon=True).start()


def test_telegram(icon=None, item=None):
    threading.Thread(target=tele_test, daemon=True).start()


def quit_app(icon, item):
    global _auto_scan_running
    _auto_scan_running = False
    keyboard.unhook_all()
    icon.stop()

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    cfg        = load_config()
    area       = cfg.get("area")
    model_path = cfg.get("model_path")

    print("=" * 55)
    print("  Flag Pattern Inference — System Tray")
    print(f"  Hotkey    : {HOTKEY.upper()}")
    print(f"  Auto scan : every {AUTO_SCAN_INTERVAL}s")
    print(f"  Telegram  : {'✓ configured' if BOT_TOKEN and CHAT_ID else '✗ missing .env'}")
    print("=" * 55)

    if model_path and os.path.exists(model_path):
        load_model(model_path)
    if not area:
        print("  No area set — right-click tray → Set Capture Area")

    keyboard.add_hotkey(HOTKEY, run_inference)

    icon = pystray.Icon(
        name  = "flag_inference",
        icon  = make_icon(),
        title = "Flag Inference",
        menu  = pystray.Menu(
            pystray.MenuItem("Run Inference",        run_inference,   default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start Auto Scan",      start_auto_scan),
            pystray.MenuItem("Stop Auto Scan",       stop_auto_scan),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Set Capture Area",     set_capture_area),
            pystray.MenuItem("Set Model Path",       set_model_path),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Test Telegram",        test_telegram),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",                 quit_app),
        ),
    )

    icon.run()


if __name__ == "__main__":
    main()