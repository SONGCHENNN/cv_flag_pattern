"""
flag_capture.py — Flag Pattern Screen Capture Tool
Runs as a Windows system tray app.

Install:
    pip install pystray mss pillow keyboard plyer

Usage:
    python flag_capture.py
    - Right-click tray icon to access menu
    - First time: click "Set Capture Area" and drag over your chart
    - After that: click "Capture" or press Ctrl+Shift+S
"""

import json
import os
import sys
import threading
from datetime import datetime

import keyboard
import mss
import mss.tools
import pystray
from PIL import Image, ImageDraw
from plyer import notification

try:
    import tkinter as tk
except ImportError:
    print("tkinter not found — install Python with tkinter support")
    sys.exit(1)

# ── Config ───────────────────────────────────────────────────────────────────
CONFIG_FILE = "config.json"
SAVE_DIR    = "flag_screenshots"
HOTKEY      = "ctrl+shift+s"
ICON_SIZE   = 64

os.makedirs(SAVE_DIR, exist_ok=True)

# ── Config helpers ────────────────────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Notification helper ───────────────────────────────────────────────────────

def notify(title, msg):
    threading.Thread(
        target=lambda: notification.notify(title=title, message=msg, timeout=2),
        daemon=True
    ).start()


# ── Tray icon image (generated, no file needed) ───────────────────────────────

def make_icon():
    img  = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60],          fill=(18, 18, 26))
    draw.rounded_rectangle([14, 22, 50, 46], radius=4, fill=(240, 180, 41))
    draw.ellipse([24, 26, 40, 42],        fill=(18, 18, 26))
    draw.ellipse([27, 29, 37, 39],        fill=(80, 80, 120))
    draw.rounded_rectangle([20, 18, 30, 24], radius=2, fill=(240, 180, 41))
    return img


# ── Area selector overlay ─────────────────────────────────────────────────────

class AreaSelector:
    """Full-screen transparent overlay for drag-to-select capture region."""

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

        self.canvas = tk.Canvas(
            self.root, bg="black", highlightthickness=0, cursor="crosshair"
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2, 40,
            text="Drag to select chart area  ·  ESC to cancel",
            fill="white",
            font=("Courier New", 16),
        )

        self.canvas.bind("<ButtonPress-1>",  self.on_press)
        self.canvas.bind("<B1-Motion>",      self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>",           lambda e: self.root.destroy())

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
        else:
            print("Selection too small, cancelled.")


# ── Screenshot logic ──────────────────────────────────────────────────────────

_capture_count = 0


def do_capture(area: dict) -> str:
    global _capture_count

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename  = f"flag_{timestamp}.png"
    filepath  = os.path.join(SAVE_DIR, filename)

    monitor = {
        "top":    area["y1"],
        "left":   area["x1"],
        "width":  area["x2"] - area["x1"],
        "height": area["y2"] - area["y1"],
    }

    with mss.mss() as sct:
        img = sct.grab(monitor)
        mss.tools.to_png(img.rgb, img.size, output=filepath)

    _capture_count += 1
    return filepath


def capture_now(icon=None, item=None):
    cfg  = load_config()
    area = cfg.get("area")

    if not area:
        notify("Flag Capture", "No area set! Right-click -> Set Capture Area first.")
        return

    try:
        filepath = do_capture(area)
        fname    = os.path.basename(filepath)
        notify("Flag Capture ✓", f"Saved #{_capture_count}: {fname}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Saved → {filepath}")
    except Exception as e:
        notify("Flag Capture ✗", str(e))
        print(f"Capture error: {e}")


def set_capture_area(icon=None, item=None):
    def on_selected(coords):
        cfg = load_config()
        cfg["area"] = coords
        save_config(cfg)
        print(f"Area saved: {coords}")
        notify("Flag Capture", f"Area set! Press {HOTKEY.upper()} or click Capture.")

    threading.Thread(target=lambda: AreaSelector(on_selected), daemon=True).start()


def open_folder(icon=None, item=None):
    os.startfile(os.path.abspath(SAVE_DIR))


def quit_app(icon, item):
    keyboard.unhook_all()
    icon.stop()


# ── Tray setup ────────────────────────────────────────────────────────────────

def main():
    cfg  = load_config()
    area = cfg.get("area")

    print("=" * 50)
    print("  Flag Pattern Capture — System Tray")
    print(f"  Hotkey : {HOTKEY.upper()}")
    print(f"  Saving : ./{SAVE_DIR}/")
    print("=" * 50)

    if not area:
        print("  No area set — right-click tray icon → Set Capture Area")
    else:
        print(f"  Area loaded: {area}")

    keyboard.add_hotkey(HOTKEY, capture_now)
    print(f"  Hotkey registered: {HOTKEY}\n")

    icon = pystray.Icon(
        name  = "flag_capture",
        icon  = make_icon(),
        title = "Flag Capture",
        menu  = pystray.Menu(
            pystray.MenuItem("Capture Now",          capture_now, default=True),
            pystray.MenuItem("Set Capture Area",     set_capture_area),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Screenshots Folder", open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",                 quit_app),
        ),
    )

    icon.run()


if __name__ == "__main__":
    main()