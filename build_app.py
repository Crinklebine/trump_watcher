# build_app.py — Trump Watcher build script
# Compile main.py into a standalone Windows EXE

import os
import shutil
import subprocess
import sys
import glob

# ----------------------------
# Configuration
# ----------------------------
APP_NAME = "TrumpWatcher"
SOURCE_FILE = "main.py"
ICON_DIR = "icon"

# Detect whether we're inside GitHub Actions
IN_GITHUB = os.getenv("GITHUB_ACTIONS") == "true"

# Determine debug vs. production mode via a --prod flag
DEBUG_MODE = "--prod" not in sys.argv

# ----------------------------
# Helper Functions
# ----------------------------
def find_playwright_browser() -> str:
    """Locate the Playwright Chromium Headless Shell directory."""
    base_path = os.environ.get("LOCALAPPDATA")
    if not base_path:
        print("[ERROR] LOCALAPPDATA environment variable not found.")
        sys.exit(1)

    search_path = os.path.join(base_path, "ms-playwright", "chromium_headless_shell-*", "chrome-win")
    matches = glob.glob(search_path)
    if not matches:
        print("[ERROR] Could not find Playwright Chromium Headless Shell directory.")
        sys.exit(1)

    print(f"[INFO] Found Playwright Headless Shell at: {matches[0]}")
    return matches[0]

def clean_previous_builds() -> None:
    """Remove old build artifacts."""
    for folder in ("build", "dist"):
        if os.path.isdir(folder):
            print(f"[INFO] Removing '{folder}/'...")
            shutil.rmtree(folder)

    spec_file = f"{APP_NAME}.spec"
    if os.path.isfile(spec_file):
        print(f"[INFO] Removing '{spec_file}'...")
        os.remove(spec_file)

def build_exe(pw_root: str) -> int:
    """Run PyInstaller to build the EXE."""
    print("[INFO] Building executable...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name", APP_NAME,
        "--add-data", f"{ICON_DIR}{os.pathsep}{ICON_DIR}",
        "--hidden-import", "plyer.platforms.win.notification",
        "--hidden-import", "winotify",
        "--hidden-import", "pythoncom",
        "--hidden-import", "win32com.shell",
        "--hidden-import", "win32com.propsys",
        "--add-data", f"{pw_root}{os.pathsep}ms-playwright/chromium_headless_shell/chrome-win",
        "--version-file", "version_info.txt",
        "--add-data=VERSION;.",
    ]

    if not DEBUG_MODE:
        cmd.append("--noconsole")

    ico_path = os.path.join(ICON_DIR, "trump_watch_icon.ico")
    if os.path.isfile(ico_path):
        cmd.append(f"--icon={ico_path}")

    cmd.append(SOURCE_FILE)

    print(f"[DEBUG] Running PyInstaller with command: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    return result.returncode

# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    print(f"[DEBUG] Running inside GitHub Actions: {IN_GITHUB}")
    print(f"[DEBUG] Debug mode: {DEBUG_MODE}")
    print(f"[INFO] Building in {'production' if not DEBUG_MODE else 'debug'} mode.")

    clean_previous_builds()
    pw_root = find_playwright_browser()
    exit_code = build_exe(pw_root)

    if exit_code == 0:
        print("::notice::Build succeeded! Executable created at dist/TrumpWatcher.exe")
    else:
        print(f"::error::Build failed with exit code {exit_code}")
        sys.exit(exit_code)
