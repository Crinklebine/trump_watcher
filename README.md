# Trump Watcher

Monitors [Truth Social](https://truthsocial.com/@realDonaldTrump) for new posts by **@realDonaldTrump**  
Provides instant Windows notifications for text, video, and image posts.

---

## Features

- ✅ Real-time post monitoring (polls every 30 seconds)
- ✅ Detects text, videos, and images separately
- ✅ Desktop notifications for new posts
- ✅ Lightweight system tray app
- ✅ No TruthSocial account required
- ✅ Built with Python, Playwright, and PyInstaller

---

## Installation

1. Clone this repository:

    ```bash
    git clone https://github.com/youruser/trumpwatcher.git
    cd trumpwatcher
    ```

2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Download Chromium manually (or ensure Chrome/Chromium exists).
   
4. Build the app:

    ```bash
    python build_app.py
    ```

5. Find your executable in `dist/TrumpWatcher/`.

---

## Usage

- **Double-click** the EXE to run
- The app will monitor silently from the Windows system tray
- Right-click tray icon for:
  - About info
  - Open @realDonaldTrump’s page
  - Exit the app

---

## Development Notes

- Edit `DEBUG_MODE` inside `build_app.py` to enable or disable console window for debugging.
- The app uses **Playwright** with a **user-supplied Chromium** or Chrome executable path.

---

## License

MIT License (or specify one later)

---

