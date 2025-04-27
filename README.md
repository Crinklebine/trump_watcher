# TrumpWatcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Build Status](https://github.com/Crinklebine/trump_watcher/actions/workflows/windows-build.yml/badge.svg)](https://github.com/Crinklebine/trump_watcher/actions)

**TrumpWatcher** is a Windows system tray application that monitors [Truth Social](https://truthsocial.com/) for Donald Trump's latest posts and sends desktop notifications.

It is designed to be a fully self-contained app, bundling its own headless browser internally for reliability.  
No external browsers or configuration are required.

This application is open-source and released under the MIT License.

---

## ✨ Features

- Monitors Trump's official Truth Social posts
- Sends native Windows desktop notifications
- Runs quietly in the system tray
- Auto-detects new posts without manual refresh
- Fully self-contained single EXE file
- Right mouse click menu
- Start Menu link installed automatically

---

## 💻 Screenshot

![TrumpWatcher Notification Screenshot](assets/screenshot.png)

---

## 📦 Download

- Latest Release: [Releases Page](https://github.com/Crinklebine/trump_watcher/releases)

> ⚠️ **Important:**  
> On first launch, Windows SmartScreen may show a "Windows protected your PC" warning because the app is unsigned.  
> 
> To run the app:
> 1. Click **More info**.
> 2. Click **Run anyway**.

This is normal for new open-source projects. TrumpWatcher is open-source and you are welcome to review the full source code.

---

## ⚙️ Installation

1. Download `TrumpWatcher.exe` from the [Releases Page](https://github.com/Crinklebine/trump_watcher/releases).
2. Double-click to run.
3. TrumpWatcher will appear in your system tray (near the clock).


✅ No installation process — just Unzip run the EXE

---
## 🗑️ Unintsall

1. Delete TrumpWatcher.EXE
2. Delete Start Menu Item
3. Win Key + R
4. Paste %APPDATA%\Microsoft\Windows\Start Menu\Programs
5. Delete TrumpWatcher Menu Item


✅ No registry entries or configuration files.

---

## 🔒 License

This project is licensed under the [MIT License](LICENSE).

You are free to use, modify, and distribute this software.

---

## 🛠️ Development

If you want to build it yourself:

- Python 3.9+
- Install dependencies: `pip install -r requirements.txt`
- Build a Windows EXE using: `python build_app.py` find your EXE in /dist
- `python main.py` currently unsupported due to bound playwright chromium-headless-shell

GitHub Actions are configured to automatically build production ZIP file with version number.

---

## 🙏 Acknowledgements

- [PyInstaller](https://www.pyinstaller.org/) — for building the standalone EXE
- [Playwright](https://playwright.dev/) — for headless browser automation
- [Winotify](https://github.com/kaustubhgupta/winotify) — for Windows notifications

---

