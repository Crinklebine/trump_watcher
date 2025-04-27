# main2.py - Trump Watcher
# Monitors TruthSocial for @realDonaldTrump posts and shows desktop notifications

# ----------------------------
# System imports
# ----------------------------
import os
import sys
import platform
import time
import threading
import ctypes
import re
import hashlib
from datetime import datetime
from pathlib import Path

# ----------------------------
# Third-party imports
# ----------------------------
from playwright.sync_api import sync_playwright
import pystray
from PIL import Image, ImageDraw
from winotify import Notification, audio
import tkinter as tk
import webbrowser

# ----------------------------
# App identity & shortcut config
# ----------------------------
APP_ID        = "TrumpWatcher"        # AppUserModelID for toasts
SHORTCUT_NAME = f"{APP_ID}.lnk"       # name of the Start-Menu shortcut
ICON_REL_PATH = "icon/trump_watch_icon.ico"  # relative path to your .ico

# ----------------------------
# Constants
# ----------------------------
TRUTH_URL = "https://truthsocial.com/@realDonaldTrump"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
POLL_INTERVAL = 30  # seconds between page reloads
seen_hashes = set()  # store hashes of posts already notified

# ----------------------------
# Global Variables
# ----------------------------
exit_flag = False               # Signals the background monitor loop (and tray icon) to stop and exit cleanly
#about_icon_initialized = False  # Guard so we only load & set the About-box icon once per session

# ----------------------------
# Debug flag setting
# ----------------------------

DEBUG_MODE = "--debug" in sys.argv

# ----------------------------
# Utility functions
# ----------------------------
def resource_path(relative_path: str) -> str:
    # Resolve a resource path that works both in development and when bundled
    try:
        base_path = sys._MEIPASS  # type: ignore (PyInstaller bundle)
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

HEADLESS_PATH = resource_path("ms-playwright/chromium_headless_shell/chrome-win/headless_shell.exe")

# Frozen detection and info
def get_frozen_info():
    print("=== FROZEN MODE INFO ===")
    print(f"  frozen flag.........: {getattr(sys, 'frozen', False)}")
    print(f"  executable path.....: {sys.executable!r}")
    # PyInstaller unpacks into a temp dir and points you at it
    print(f"  _MEIPASS dir........: {getattr(sys, '_MEIPASS', None)!r}")
    # original script path (won’t exist in exe)
    print(f"  __file__............: {__file__!r}")
    # argv[0] is the exe name
    print(f"  argv[0].............: {sys.argv[0]!r}")
    # host python platform
    print(f"  platform............: {platform.system()} {platform.release()}")
    print(f"  machine arch........: {platform.machine()}")
    # if you embed a VERSION file you can read it here
    ver_file = Path(getattr(sys, '_MEIPASS', os.getcwd())) / "VERSION"
    print(f"  bundle VERSION file.: {ver_file if ver_file.exists() else '<not found>'}")
    if ver_file.exists():
        print("    ->", ver_file.read_text().strip())
    print("========================")

# Determine if running as EXE (PyInstaller "frozen" mode)
FROZEN = getattr(sys, 'frozen', False)
if FROZEN:
    try:
        get_frozen_info()
    except Exception as e:
        print(f"[DEBUG] Failed to get frozen info: {e}")

def get_version():
    """Read the VERSION file and return the app version."""
    try:
        version_file = Path(resource_path("VERSION"))
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
        else:
            return "Unknown"
    except Exception as e:
        print(f"[DEBUG] Failed to load version: {e}")
        return "Unknown"

def ensure_aumid_shortcut() -> None:
    # Create or recreate the Start-Menu shortcut so Windows uses our AUMID and icon
    try:
        # Import pywin32 COM APIs for shortcut creation
        import pythoncom  # type: ignore[import]
        from win32com.shell import shell  # type: ignore[import]
        from win32com.propsys import propsys, pscon  # type: ignore[import]
    except ImportError as e:
        # Problems importing pywin32 COM APIs; skip shortcut creation
        print(f"[DEBUG] ensure_aumid_shortcut skipped: {e!r}")
        return

    # Determine the Programs folder under the current user's Start Menu
    programs_folder = os.path.join(
        os.environ["APPDATA"],
        "Microsoft", "Windows", "Start Menu", "Programs"
    )
    link_path = os.path.join(programs_folder, SHORTCUT_NAME)

    # Always remove any existing shortcut so we rebuild it fresh
    if os.path.exists(link_path):
        os.remove(link_path)

    # Instantiate the IShellLink COM object
    sl = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink, None,
        pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
    )

    # Detect whether we're running as a bundled EXE (frozen) or in development
    frozen = getattr(sys, "frozen", False)

    if frozen:
        # When running as EXE, point to the executable itself
        target = sys.executable
        args   = ""
        icon   = target  # use the EXE’s embedded icon
        workdir = os.path.dirname(target)
    else:
        # In development mode, point to python.exe and pass the script path
        target  = sys.executable
        script  = os.path.abspath(__file__)
        args    = f'"{script}"'
        icon    = resource_path(ICON_REL_PATH)  # use raw .ico for dev testing
        workdir = os.path.dirname(script)

    # Debug output to verify correct paths and settings
    print(f"[DEBUG] ensure_aumid_shortcut: frozen={frozen}")
    print(f"[DEBUG]   shortcut target = {target}")
    print(f"[DEBUG]   arguments       = {args}")
    print(f"[DEBUG]   icon location   = {icon}")
    print(f"[DEBUG]   shortcut path   = {link_path}")

    # Configure the shortcut
    sl.SetPath(target)
    sl.SetArguments(args)
    sl.SetWorkingDirectory(workdir)
    sl.SetIconLocation(icon, 0)

    # Assign our AppUserModelID to the shortcut for toast grouping
    prop_store = sl.QueryInterface(propsys.IID_IPropertyStore)
    propvar     = propsys.PROPVARIANTType(APP_ID)
    prop_store.SetValue(pscon.PKEY_AppUserModel_ID, propvar)
    prop_store.Commit()

    # Save the .lnk file to disk
    persist_file = sl.QueryInterface(pythoncom.IID_IPersistFile)
    persist_file.Save(link_path, 0)

def set_app_id(app_id: str) -> None:
    # Register a Windows AppUserModelID so notifications are grouped under our app
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        print(f"[DEBUG] AppUserModelID set to: {app_id}")
    except Exception as e:
        print(f"[DEBUG] Failed to set AppUserModelID: {e}")

def normalize(text: str) -> str:
    # Lowercase, strip punctuation, remove duplicate lines for hashing
    lines = [line.strip() for line in text.splitlines()]
    seen = set()
    filtered = []
    for line in lines:
        if not line:
            continue
        # skip standalone URLs or domains
        if re.match(r'^(https?://|www\.|[\w\-]+\.\w{2,})', line) and len(line.split()) <= 1:
            continue
        norm = re.sub(r'[^\w\s]', '', line.lower())
        if norm in seen:
            continue
        seen.add(norm)
        filtered.append(line)
    return "\n".join(filtered).strip()

def hash_post(text: str) -> str:
    # Compute SHA-256 hash of normalized text
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# ----------------------------
# Core functionality
# ----------------------------
def extract_posts_from_page(page) -> list:
    # Scrape the current page for new posts and return list of (raw_text, normalized_text, hash)
    new_posts = []
    # All post containers share these CSS classes
    post_blocks = page.query_selector_all('div.flex.flex-col.space-y-4')

    for block in post_blocks:
        # 1) Try to collect textual content
        text_parts = []
        for tag in ["p", "span", "a", "h1", "h2", "h3", "blockquote"]:
            for el in block.query_selector_all(tag):
                txt = el.inner_text().strip()
                if txt and len(txt) > 10:
                    text_parts.append(txt)

        if text_parts:
            # Join all collected text lines
            raw_text = "\n".join(text_parts)

        else:
            # 2) Fallback: look for a <video> element
            video_el = block.query_selector("video")
            if video_el:
                source_el = video_el.query_selector("source")
                if not source_el:
                    # No <source> inside <video> → skip this block
                    continue
                src = source_el.get_attribute("src") or ""
                src = src.split("?")[0]
                raw_text = f"[Video post] {src}"

            else:
                # 3) Fallback again: look for an <img> element
                img_el = block.query_selector("img")
                if not img_el:
                    # No image either → nothing to notify
                    continue
                src = img_el.get_attribute("src") or ""
                src = src.split("?")[0]
                raw_text = f"[Image post] {src}"

        # 4) Skip boilerplate or irrelevant posts
        blacklist = [
            "New to Truth?", "Join Truth Social", "Create Account",
            "Truth Social uses cookies", "session cookies",
            "automated attacks", "Learn more"
        ]
        if any(bad in raw_text for bad in blacklist):
            continue

        # 5) Skip very short text posts (unless multimedia)
        if len(raw_text.split()) < 3 and not raw_text.startswith(("[Video post]", "[Image post]")):
            continue

        # 6) Normalize and hash to dedupe
        normalized = normalize(raw_text)
        h = hash_post(normalized)
        if h not in seen_hashes:
            new_posts.append((raw_text, normalized, h))

    return new_posts

def notify(post_text: str, normalized_text: str, label: str = "New Trump post") -> None:
    # Log to console
    print(f"[{datetime.now()}] Notify: {label}")

    try:
        # Resolve paths to the small ICO and your 256×256 PNG
        ico_path = resource_path("icon/trump_watch_icon.ico")
        hero_path = resource_path("icon/trump_watch_icon.png")

        # Build the toast using the ICO
        toast = Notification(
            app_id=APP_ID,           # “TrumpWatcher”
            title=label,
            msg=normalized_text[:200],
            icon=ico_path,
            duration="long"          # banner stays up ~25s
        )

        # Only add a hero image if that method exists
        if hasattr(toast, "add_image"):
            toast.add_image(src=hero_path)

        # Add a button to view on TruthSocial
        toast.add_actions(label="View on TruthSocial", launch=TRUTH_URL)

        # Play the default notification sound
        toast.set_audio(audio.Default, loop=False)

        # Show it
        toast.show()

    except Exception as e:
        # Catch-all so we never crash on notification errors
        print(f"[{datetime.now()}] Notification error: {e}")

    # Always append full details to posts log in DEBUG mode
    if DEBUG_MODE:
        with open("posts_log.txt", "a", encoding="utf-8") as log:
            log.write(f"\n[{datetime.now()}] [{label}]\n")
            log.write("Raw Extracted:\n" + post_text + "\n\n")
            log.write("Normalized for Hashing:\n" + normalized_text + "\n")
            log.write("-" * 40 + "\n")

def monitor_loop() -> None:
    # Main loop: do a cold start once, then poll every POLL_INTERVAL seconds
    global exit_flag
    cold_start = True

    # For now, always use the hardcoded headless path
    browser_path = HEADLESS_PATH
    print(f"[DEBUG] Using browser at: {browser_path}")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=browser_path
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        while not exit_flag:
            if cold_start:
                # initial wait for full page render
                print(f"[{datetime.now()}] Cold start: waiting 5s for render...")
                time.sleep(5)
                print(f"[{datetime.now()}] Initial page load")

                # on cold start, notify only the very latest post
                page.goto(TRUTH_URL, timeout=60000)
                page.wait_for_selector('div.flex.flex-col.space-y-4', timeout=30000)
                page.wait_for_timeout(2000)
                new_posts = extract_posts_from_page(page)

                if new_posts:
                    # notify just the newest item
                    raw, norm, h = new_posts[0]
                    seen_hashes.add(h)
                    label = "New Trump post"
                    if "[Video post]" in norm:
                        label = "New Trump Video Post"
                    elif "[Image post]" in norm:
                        label = "New Trump Image Post"
                    notify(raw, norm, label=label)

                    # mark the rest as seen so they never re-notify
                    for _, _, h2 in new_posts[1:]:
                        seen_hashes.add(h2)
                else:
                    print(f"[{datetime.now()}] No new posts found.")

                cold_start = False

            else:
                # regular polling: notify on *any* new post
                print(f"[{datetime.now()}] Polling: reloading page")
                try:
                    page.goto(TRUTH_URL, timeout=60000)
                    page.wait_for_selector('div.flex.flex-col.space-y-4', timeout=30000)
                    page.wait_for_timeout(2000)
                    new_posts = extract_posts_from_page(page)

                    if not new_posts:
                        print(f"[{datetime.now()}] No new posts found.")

                    for raw, norm, h in new_posts:
                        if h not in seen_hashes:
                            seen_hashes.add(h)
                            label = "New Trump post"
                            if "[Video post]" in norm:
                                label = "New Trump Video Post"
                            elif "[Image post]" in norm:
                                label = "New Trump Image Post"
                            notify(raw, norm, label=label)

                except Exception as e:
                    print(f"[{datetime.now()}] Error during monitor loop: {e}")

            time.sleep(POLL_INTERVAL)

        browser.close()

# ----------------------------
# System tray icon setup
# ----------------------------
def create_icon() -> None:
    # Create a system tray icon with menu: Open, About, Exit; start monitor in background
  
    def on_exit(icon, item):
        # Stop the loop and exit the tray icon
        global exit_flag
        exit_flag = True
        icon.stop()

    def on_about(icon, item):
        # Triggered when the About menu item is clicked
        print("[DEBUG] About menu item clicked.")

        #Show an About dialog in its own thread with a fresh Tk root.
        def show_about():
            # Running inside a new thread to open About dialog
            print("[DEBUG] About dialog thread started.")

            # Create a brand-new root for this dialog
            root = tk.Tk()
            root.title("About TrumpWatcher")
            root.resizable(False, False)

            # Try setting our custom icon
            try:
                path = resource_path("icon/trump_watch_icon.png")
                img  = tk.PhotoImage(file=path)
                root.iconphoto(True, img)
                root._icon_ref = img  # keep a reference alive
                print("[DEBUG] About dialog icon loaded successfully.")
            except Exception as e:
                print(f"[DEBUG] Failed to set window icon: {e}")

            # Center the window
            w, h = 360, 180
            x = (root.winfo_screenwidth()  - w) // 2
            y = (root.winfo_screenheight() - h) // 2
            root.geometry(f"{w}x{h}+{x}+{y}")

            # About text
            about_text = (
                f"TrumpWatcher v{get_version()}\n"
                "Monitors TruthSocial for @realDonaldTrump posts.\n"
                "Displays desktop notifications on new posts.\n\n"
                "Built with:\n"
                "Python, Playwright, Pystray, Tkinter 🙏\n"
                "© 2025 Crinklebine"
            )
            tk.Label(root, text=about_text, justify="center", padx=20, pady=10).pack()

           # Close button
            tk.Button(root, text="Close", command=root.destroy).pack(pady=10)

            # Enter Tk event loop for this About dialog only
            print("[DEBUG] About dialog ready, entering mainloop.")
            root.mainloop()
            print("[DEBUG] About dialog closed.")

        # Launch About in a daemon thread so it never blocks the tray
        threading.Thread(target=show_about, daemon=True).start()

    def on_open_trump(icon, item):
        # Triggered when the Open Trump Page menu item is clicked
        print("[DEBUG] Open Trump Page menu item clicked.")
        try:
            # Open the TruthSocial page in the default browser
            webbrowser.open(TRUTH_URL)
            print("[DEBUG] Browser launched successfully.")
        except Exception as e:
            print(f"[DEBUG] Failed to open browser: {e}")    

    # Load or draw tray icon
    try:
        icon_path = resource_path("icon/trump_watch_icon.png")
        image = Image.open(icon_path).resize((64, 64))
        print("[DEBUG] Tray icon loaded.")
    except Exception as e:
        print(f"[DEBUG] Tray icon load failed: {e}")
        image = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill='red')

    menu = pystray.Menu(
        pystray.MenuItem("Open Trump Page", on_open_trump),
        pystray.Menu.SEPARATOR, 
        pystray.MenuItem("About", on_about),
        pystray.MenuItem("Exit", on_exit)
    )
    icon = pystray.Icon("TrumpWatcher", image, "Trump Watcher", menu)

    # Start monitoring in background
    threading.Thread(target=monitor_loop, daemon=True).start()
    icon.run()

# ----------------------------
# Entry point
# ----------------------------
if __name__ == "__main__":
    # 1) Create the Start-Menu shortcut (uses the global APP_ID)
    ensure_aumid_shortcut()

    # 2) Register the AppUserModelID for this process
    set_app_id(APP_ID)

    # 3) Start the tray icon & monitoring loop
    create_icon()



