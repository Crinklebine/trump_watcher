# main.py - Trump Watcher
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
import gc
from datetime import datetime
from pathlib import Path

import win32api
import win32con
import win32gui

# ----------------------------
# pywin32 imports required - use type: ignore[import] to prevent vscode from thinking imports are unused
# ----------------------------
import pythoncom  # type: ignore[import]
from win32com.shell import shell  # type: ignore[import]
from win32com.propsys import propsys, pscon  # type: ignore[import]

# ----------------------------
# Third-party imports
# ----------------------------
import psutil
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
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
)
POLL_INTERVAL    = 30        # seconds between polls
RESTART_INTERVAL = 10 * 60    # seconds (10 minutes)
seen_hashes = set()  # store hashes of posts already notified

# ----------------------------
# Headless Browser Args and resource control
# ----------------------------
# Optional Chromium launch flags
BROWSER_ARGS = [
    "--disable-gpu",                # drop the GPU process
    "--disable-extensions",         # drop extension helper
    "--disable-dev-shm-usage",      # reduce shared-memory usage
    "--renderer-process-limit=1"    # only one renderer (instead of 3)
]

BLOCKED_RESOURCE_TYPES = ["image", "font", "media"]

# ----------------------------
# Global Variables
# ----------------------------
exit_flag = False               # Signals the background monitor loop (and tray icon) to stop and exit cleanly
browser_context = None          # global handle for the currently running browser context

# ----------------------------
# Tracking run time and peak memory usage
# ----------------------------
RUN_START = datetime.now()
MAX_HEADLESS_MEM = 0.0
MAX_TRUMPWATCHER_MEM = 0.0

# ----------------------------
# Debug flag setting
# ----------------------------

DEBUG_MODE = "--debug" in sys.argv

# ----------------------------
# Show the executable name
# ----------------------------
print(f"[DEBUG] sys.executable = {sys.executable}")
print(f"[DEBUG] My EXE name = {os.path.basename(sys.executable)}")

# ----------------------------
# Utility functions
# ----------------------------

# Resource path management
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

# Get the version from VERSION file
def get_version():
    #Read the VERSION file and return the app version
    try:
        version_file = Path(resource_path("VERSION"))
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
        else:
            return "Unknown"
    except Exception as e:
        print(f"[DEBUG] Failed to load version: {e}")
        return "Unknown"

# Create or recreate the Start-Menu shortcut so Windows uses our AUMID and icon
def ensure_aumid_shortcut() -> None:

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

# Define lockfile path (TEMP folder, safe and user-writable)
LOCKFILE = os.path.join(os.getenv('TEMP'), 'trumpwatcher.lock')        

# multiple instance checking
def check_single_instance():
    exe_name = os.path.basename(sys.executable).lower()
    my_pid = os.getpid()

    # Check if lockfile exists
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, 'r') as f:
                existing_pid = int(f.read().strip())

            if psutil.pid_exists(existing_pid):
                print(f"[DEBUG] Existing instance detected with PID {existing_pid}. Showing warning and exiting.")

                # Create an invisible window to own the MessageBox (prevent taskbar clutter)
                wndclass = win32gui.WNDCLASS()
                wndclass.lpfnWndProc = lambda hwnd, msg, wparam, lparam: 0
                wndclass.lpszClassName = "InvisibleTrumpWatcherWindow"
                atom = win32gui.RegisterClass(wndclass)
                hwnd = win32gui.CreateWindow(atom, "", 0, 0, 0, 0, 0, 0, 0, 0, None)

                win32api.MessageBox(
                    hwnd,
                    "TrumpWatcher is already running.\n\nCheck your system tray or overflow area for the icon.",
                    "TrumpWatcher Already Running",
                    win32con.MB_ICONEXCLAMATION | win32con.MB_OK
                )

                win32gui.DestroyWindow(hwnd)
                sys.exit(0)

            else:
                print(f"[DEBUG] Stale lockfile found (PID {existing_pid} not running). Removing stale lockfile.")
                os.remove(LOCKFILE)

        except Exception as e:
            print(f"[DEBUG] Error reading lockfile ({e}). Removing lockfile.")
            try:
                os.remove(LOCKFILE)
            except Exception as e2:
                print(f"[DEBUG] Failed to remove lockfile: {e2}")

    # No existing valid lockfile -> create a new one
    try:
        with open(LOCKFILE, 'w') as f:
            f.write(str(my_pid))
        print(f"[DEBUG] Lockfile created with PID {my_pid}.")
    except Exception as e:
        print(f"[DEBUG] Failed to create lockfile ({e}). Exiting.")
        sys.exit(0)

# lock file cleanup
def cleanup_single_instance():
    try:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
            print("[DEBUG] Lockfile removed successfully.")
    except Exception as e:
        print(f"[DEBUG] Failed to remove lockfile: {e}")

def perform_garbage_collection():
    # Force a full Python GC pass.
    # Call this after you tear down your browser context
    # whenever you want to free up memory.
    try:
        print("[DEBUG] Running garbage collection…")
        gc.collect()
        print("[DEBUG] Garbage collection complete.")
    except Exception as e:
        print(f"[DEBUG] Garbage collection failed: {e}")


def get_headless_memory_mb() -> float:
    # Scan for all running headless_shell.exe processes and
    # return their combined RSS memory usage in megabytes.
    # Includes debug logs for each process and any access errors.
    total_rss = 0
    for proc in psutil.process_iter(['name', 'memory_info']):
        try:
            name = proc.info.get('name') or ""
            if 'headless_shell' in name.lower():
                total_rss += proc.info['memory_info'].rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total_rss / (1024 * 1024)


def get_trumpwatcher_memory_mb() -> float:
    # Return the RSS memory usage of the running TrumpWatcher.exe process in MB,
    # with debug output.
    try:
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0

def get_run_time_minutes() -> float:
    #Returns the total run time in minutes since startup.
    return (datetime.now() - RUN_START).total_seconds() / 60

def report_summary():
    # Print summary of peak memory usage and total run time.
    print(f"[DEBUG] Peak headless_shell.exe memory: {MAX_HEADLESS_MEM:.1f} MB")
    print(f"[DEBUG] Peak TrumpWatcher.exe memory: {MAX_TRUMPWATCHER_MEM:.1f} MB")
    runtime = get_run_time_minutes()
    print(f"[DEBUG] Total run time: {runtime:.1f} minutes")

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

def seed_seen_hashes(page):
    """
    On the very first poll, mark everything already in the feed as seen,
    but notify once on the most‐recent post.
    """
    posts = extract_posts_from_page(page)
    if not posts:
        print("[DEBUG] No posts found on initial poll.")
        return

    # Notify on the very latest post only
    raw, norm, h = posts[0]
    seen_hashes.add(h)
    notify(raw, norm, "Most recent Trump post")
    print(f"[DEBUG] Most recent post notified → Hash: {h}")

    # Mark the rest as seen so we don’t re-notify them
    for _, _, later_h in posts[1:]:
        seen_hashes.add(later_h)
    print(f"[DEBUG] Seeded seen_hashes with {len(posts)} posts.")


# ----------------------------
# Core functionality
# ----------------------------

# ----------------------------
# Post extraction
# ----------------------------
def extract_posts_from_page(page) -> list:
    """
    Scrape TruthSocial for @realDonaldTrump.
    - Skips any block whose HTML contains "Pinned Truth".
    - On the very first call (seen_hashes is empty), returns exactly one post.
    - Thereafter, returns every post not yet in seen_hashes.
    """
    new_posts = []
    initial_run = len(seen_hashes) == 0

    # 1) Grab every feed item
    all_blocks = page.query_selector_all("div.status__wrapper")
    print(f"[DEBUG] Found {len(all_blocks)} status__wrapper blocks before filtering")

    # 2) Drop the pinned post
    post_blocks = []
    for idx, block in enumerate(all_blocks):
        html = block.inner_html()
        if "Pinned Truth" in html:
            print("[DEBUG] Skipping pinned post (html contains “Pinned Truth”)")
            continue
        # (optional) log which author line we see
        first_line = block.inner_text().strip().splitlines()[0]
        print(f"[DEBUG] Block {idx} first line (author): {first_line!r}")
        post_blocks.append(block)

    # 3) Extract & dedupe
    for block in post_blocks:
        raw_text = None

        # a) text
        parts = []
        for tag in ["p", "span", "a", "h1", "h2", "h3", "blockquote"]:
            for el in block.query_selector_all(tag):
                t = el.inner_text().strip()
                if t and len(t) > 10:
                    parts.append(t)
        if parts:
            raw_text = "\n".join(parts)

        # b) video fallback
        if raw_text is None:
            vid = block.query_selector("video")
            if vid:
                src = (vid.query_selector("source") \
                        .get_attribute("src") or "").split("?")[0]
                raw_text = f"[Video post] {src}"

        # c) image fallback
        if raw_text is None:
            img = block.query_selector("img")
            if img:
                src = (img.get_attribute("src") or "").split("?")[0]
                raw_text = f"[Image post] {src}"

        if raw_text is None:
            print("[DEBUG] No content found in block—skipping")
            continue

        # 4) boilerplate filter
        for bad in ("New to Truth?", "Join Truth Social", "Create Account",
                    "Truth Social uses cookies", "session cookies",
                    "automated attacks", "Learn more"):
            if bad in raw_text:
                print(f"[DEBUG] Blacklisted content ({bad!r})—skipping")
                raw_text = None
                break
        if raw_text is None:
            continue

        # 5) skip tiny text-only posts
        if len(raw_text.split()) < 3 and not raw_text.startswith(("[Video post]", "[Image post]")):
            print("[DEBUG] Very short text post—skipping")
            continue

        # 6) normalize, hash, dedupe
        normalized = normalize(raw_text)
        h = hash_post(normalized)
        if h in seen_hashes:
            print(f"[DEBUG] Duplicate post (hash={h})—skipping")
            continue

        # 7) record & return
        seen_hashes.add(h)
        new_posts.append((raw_text, normalized, h))
        print(f"[DEBUG] Queued new post (hash={h})")

        # 8) on the _first_ run, stop after one
        if initial_run:
            break

    return new_posts



def check_for_new_posts(page):
    # Scrape the latest posts, dedupe by hash, and fire notifications.
    # Uses extract_posts_from_page() and notify(), and the global seen_hashes.

    try:
        # page is already at TRUTH_URL on first poll;
        # all reloads happen in the loop below
        new_posts = extract_posts_from_page(page)
        if not new_posts:
            print("[DEBUG] No new posts found.")
            return

        for raw_text, normalized_text, h in new_posts:
            print(f"[DEBUG] New post detected -> Hash: {h}")
            seen_hashes.add(h)

            # derive a label for the notification
            if raw_text.startswith("[Video post]"):
                label = "Video post"
            elif raw_text.startswith("[Image post]"):
                label = "Image post"
            else:
                label = "New Trump post"

            # Fire your notification with the right label
            notify(raw_text, normalized_text, label)

    except Exception as e:
        print(f"[DEBUG] Error in check_for_new_posts: {e}")

# Notify function - performs native Windows Toast style notifications
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


# ----------------------------
# Browser launch + preload
# ----------------------------
def start_browser():
    """
    Launch headless Chromium, navigate to Truth Social, block images/fonts/media,
    then scroll until at least 2 posts are in the DOM.
    """
    global browser_context
    print("[DEBUG] Launching headless browser…")
    p = sync_playwright().start()
    browser = p.chromium.launch(
        executable_path=HEADLESS_PATH,
        headless=True,
        args=BROWSER_ARGS,
    )
    browser_context = browser.new_context(
        extra_http_headers={"user-agent": USER_AGENT}
    )
    page = browser_context.new_page()

    # block images/fonts/media
    def _block(route, req):
        if req.resource_type in ("image", "font", "media"):
            return route.abort()
        return route.continue_()
    page.route("**/*", _block)

    # go to the feed
    page.goto(TRUTH_URL, wait_until="networkidle")

    # scroll *all the way* down until we see 2 posts
    for i in range(5):
        blocks = page.query_selector_all("div.status__wrapper")
        print(f"[DEBUG] after scroll #{i+1}, found {len(blocks)} wrappers")
        if len(blocks) >= 2:
            break
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

    # hang onto these for restarts
    page._playwright = p
    page._browser   = browser
    print("[DEBUG] Browser launched successfully.")
    return browser_context, page


def close_browser(context):
    try:
        print("[DEBUG] Closing browser context.")
        # grab handles from the passed‐in context
        pages = context.pages or []
        page  = pages[0] if pages else None
        browser = getattr(page, "_browser", None)
        p       = getattr(page, "_playwright", None)

        # close the context itself
        context.close()

        # then tear down browser + playwright
        if browser:
            browser.close()
        if p:
            p.stop()

        print("[DEBUG] Browser context closed successfully.")
    except Exception as e:
        print(f"[DEBUG] Error during browser cleanup: {e}")


# ----------------------------
# Poll + restart loop
# ----------------------------
def monitor_loop():
    global exit_flag

    last_restart = time.time()
    context, page = start_browser()
    first_poll   = True

    print(f"[DEBUG] Monitor loop started. Polling every {POLL_INTERVAL}s, restarting every {RESTART_INTERVAL}s.")

    while not exit_flag:
        try:
            now = time.time()
            if now - last_restart >= RESTART_INTERVAL:
                print("[DEBUG] Restart interval hit — tearing down and relaunching browser")
                close_browser(context)
                context, page = start_browser()
                last_restart = time.time()

            print("[DEBUG] Polling for posts…")
            page.reload(wait_until="networkidle")

            # again, force-load more posts
            for i in range(3):
                blocks = page.query_selector_all("div.status__wrapper")
                print(f"[DEBUG] reload-scroll #{i+1}, found {len(blocks)} wrappers")
                if len(blocks) >= 2:
                    break
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_load_state("networkidle")
                time.sleep(1)

            if first_poll:
                seed_seen_hashes(page)
                first_poll = False
            else:
                check_for_new_posts(page)

            print(f"[DEBUG] Sleeping {POLL_INTERVAL}s until next poll")
        except Exception as e:
            print(f"[DEBUG] Error in monitor loop: {e}")

        # responsive sleep
        for _ in range(POLL_INTERVAL):
            if exit_flag:
                break
            time.sleep(1)

    print("[DEBUG] Exiting monitor loop, cleaning up…")
    close_browser(context)



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

        # Final summary report
        report_summary()    

        # Clean up the lockfile
        cleanup_single_instance()

        # Final shutdown log
        print("[DEBUG] TrumpWatcher shutdown complete.")

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
    # 1) Check for another instance  
    check_single_instance()
    
    # 2) Create the Start-Menu shortcut (uses the global APP_ID)
    ensure_aumid_shortcut()

    # 3) Register the AppUserModelID for this process
    set_app_id(APP_ID)

    # 4) Start the tray icon & monitoring loop
    create_icon()



