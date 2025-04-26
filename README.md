# TrumpWatcher

**TrumpWatcher** is a lightweight Windows system tray app that monitors [Truth Social](https://truthsocial.com/) for Donald Trump's latest posts and sends desktop notifications.

This application is open-source and designed for personal use, but you are welcome to use or modify it under the MIT License.

---

## ✨ Features

- Monitors Trump's official Truth Social posts
- Sends native Windows desktop notifications
- Runs quietly in the system tray
- Efficient and minimal
- Auto-hashes posts to avoid duplicate alerts
- Requires no manual browser setup (bundled headless Chromium)

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
4. Right-click the tray icon for options like Open Truth Social, About, or Exit.

✅ That's it! No complicated installation required.

---

## 🔒 License

This project is licensed under the [MIT License](LICENSE).

You are free to use, modify, and distribute this software.

---

## 🛠️ Development

If you want to build it yourself:

- Python 3.11+
- Install dependencies: `pip install -r requirements.txt`
- Run locally: `python main.py`
- Or build a Windows EXE using: `python build_app.py`

GitHub Actions are set up to automatically build production-ready EXEs for Windows.

---

## 🙏 Acknowledgements

- [PyInstaller](https://www.pyinstaller.org/) — for building the standalone EXE
- [Playwright](https://playwright.dev/) — for headless browser automation
- [Winotify](https://github.com/kaustubhgupta/winotify) — for Windows notifications

---
