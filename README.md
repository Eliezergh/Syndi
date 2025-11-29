# <img src="src/media/syndi.png" width="32" height="32" alt="Syndi icon"> Syndi
Your simple syndication (RSS) notifier for macOS

A lightweight menu bar app that notifies you when your favorite RSS feeds have new content.

![macOS](https://img.shields.io/badge/macOS-11.0%2B-blue)
![Python](https://img.shields.io/badge/Python-3.9%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- 📰 **Menu Bar App** - Lives in your macOS menu bar, stays out of the way
- 🔔 **Native Notifications** - Get macOS notifications for new posts
- 🔗 **Quick Access** - Click recent items to open posts in your browser
- ⚙️ **Easy Config** - Simple JSON configuration for feeds
- 🔄 **Auto-Check** - Periodically checks feeds in the background
- 💾 **Smart Tracking** - Remembers what you've seen to avoid duplicate notifications
- 🚀 **Standalone** - Bundles into a native `.app` with no Python required

## Installation

### Option 1: Download Pre-built App (Recommended)

1. Download `Syndi-vX.X.X-macos.zip` from [Releases](https://github.com/eliezergh/Syndi/releases)
2. Unzip and drag `Syndi.app` to your Applications folder
3. On first launch, right-click → **Open** (to bypass Gatekeeper since app is not signed)
4. Configure your feeds in `~/.syndi/config.json`

### Option 2: Run from Source

```bash
# Clone the repository
git clone https://github.com/eliezergh/Syndi.git
cd Syndi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python src/syndi.py
```

### Option 3: Build the App Yourself

```bash
# Install dependencies
pip install -r requirements.txt

# Build the app
cd setup
python setup.py py2app

# The app will be in setup/dist/Syndi.app
open dist/Syndi.app
```

## Configuration

Configuration is stored in `~/.syndi/config.json`. On first run, a default config is created automatically.

```json
{
  "feeds": [
    {
      "name": "Hacker News",
      "url": "https://news.ycombinator.com/rss",
      "enabled": true
    },
    {
      "name": "GitHub Blog",
      "url": "https://github.blog/feed/",
      "enabled": true
    }
  ],
  "check_interval_seconds": 300,
  "notification_enabled": true,
  "show_preview": true,
  "max_recent_items": 10
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `feeds` | Array of RSS feeds to monitor | - |
| `feeds[].name` | Display name for the feed | - |
| `feeds[].url` | RSS/Atom feed URL | - |
| `feeds[].enabled` | Set to `false` to disable a feed | `true` |
| `check_interval_seconds` | How often to check feeds (in seconds) | `300` (5 min) |
| `notification_enabled` | Enable/disable notifications | `true` |
| `show_preview` | Show article preview in notifications | `true` |
| `max_recent_items` | Number of recent items to keep in menu | `10` |

## Menu Bar Options

Click the menu bar icon to access:

- **Check now** - Manually check all feeds immediately
- **Last check** - Shows when feeds were last checked
- **Recent Items** - Quick access to recent feed items
- **Options**
  - **Test notification** - Send a test notification
  - **Open config** - Edit config.json
  - **Reload config** - Reload configuration without restarting
  - **Clear seen data** - Reset all seen items and recent history
- **About Syndi** - View app information
- **Quit Syndi** - Exit the application

## Data Storage

Syndi stores its data in `~/.syndi/`:

```
~/.syndi/
├── config.json    # Your feed configuration
└── data.json      # Seen items and recent history
```

## Project Structure

```
Syndi/
├── src/
│   ├── syndi.py           # Main application
│   ├── config.json        # Default configuration
│   └── media/
│       ├── menubar_icon.png   # Menu bar icon
│       └── syndi.icns         # App icon
├── setup/
│   └── setup.py           # py2app build script
├── requirements.txt       # Python dependencies
└── README.md
```

## Troubleshooting

### "App can't be opened because it is from an unidentified developer"
Right-click the app → **Open** → **Open** (this bypasses Gatekeeper for unsigned apps)

### No notifications appearing
- Check System Settings → Notifications → Syndi is allowed
- Verify `notification_enabled: true` in config.json

### Feeds not updating
- Click "Check now" to manually trigger
- Check feed URLs are valid RSS/Atom feeds
- Run from source to see error messages: `python src/syndi.py`

### App won't build with py2app
```bash
rm -rf setup/build setup/dist
cd setup && python setup.py py2app
```

## Dependencies

- **[rumps](https://github.com/jaredks/rumps)** - Menu bar app framework
- **[feedparser](https://github.com/kurtmckee/feedparser)** - RSS/Atom feed parsing
- **[requests](https://github.com/psf/requests)** - HTTP requests
- **[py2app](https://py2app.readthedocs.io/)** - macOS app bundling

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

Built with ❤️ by [EliezerGH](https://github.com/eliezergh)
