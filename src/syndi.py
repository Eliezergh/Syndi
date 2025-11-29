#!/usr/bin/env python3
"""
Syndi - Your simple syndication (RSS) notifier
A lightweight macOS menu bar app for RSS feed notifications
"""
#Imports
import rumps
import subprocess
import sys
import json
import requests
import feedparser
import re
from pathlib import Path
from datetime import datetime

class SyndiApp(rumps.App):

    # Initialize the application
    def __init__(self):
        # Determine base path for resources
        if getattr(sys, 'frozen', False):
            # If bundled, resources are in the Resources folder
            resources_path = Path(sys.executable).parent.parent / "Resources"
        else:
            # If running as script, use script directory
            resources_path = Path(__file__).parent
        
        # Use custom icon
        icon_path = resources_path / "media" / "menubar_icon.png"
        if not icon_path.exists():
            # Fallback: check if icon is directly in Resources (flat structure)
            icon_path = resources_path / "menubar_icon.png"

        super(SyndiApp, self).__init__(
            name="Syndi",
            icon=str(icon_path) if icon_path.exists() else None,
            # Disable the default 'Quit' button in favour of a custom 'Quit' function.
            quit_button=None  
        )

        # Store resources path for later use
        self.resources_path = resources_path

        # Config and data paths - stored in ~/.syndi/ folder
        syndi_folder = Path.home() / ".syndi"
        syndi_folder.mkdir(exist_ok=True)
        self.config_path = syndi_folder / "config.json"
        self.data_path = syndi_folder / "data.json"

        # Ensure config file exists (copy default if not)
        if not self.config_path.exists():
            if getattr(sys, 'frozen', False):
                # Look for default config in Resources (bundled app)
                default_config_path = resources_path / "config.json"
            else:
                # Look for default config in script directory
                default_config_path = Path(__file__).parent / "config.json"
            
            if default_config_path.exists():
                self.config_path.write_text(default_config_path.read_text())
                print(f"Created default config at {self.config_path}")
            else:
                print(f"Warning: Default config not found at {default_config_path}")
        
        # Load configuration
        self.feeds = []  # Placeholder for feed list
        self.seen_items = set()  # To track seen items
        self.recent_items = []  # To store recent items
        self.check_interval = 300  # Default check interval in seconds
        self.last_check = None # Timestamp of last check
        self.notification_enabled = True  # Default notification setting
        self.show_preview = True  # Default preview setting
        self.max_recent_items = 10  # Default max recent items

        # Load configuration
        self.load_config()

        # Load previously seen items
        self.load_data()

        # Rebuild menu with loaded data
        self.build_menu()

        # Start background timer for feed checking
        self.timer = rumps.Timer(self.feeds_bg_checker, self.check_interval)
        self.timer.start()

    # Define the menu items
    def build_menu(self):
        # Clear menu items
        self.menu.clear()

        # Add action items
        self.menu.add(rumps.MenuItem("Check now", callback=self.feeds_bg_checker))
        
        # Show last check time
        if self.last_check:
            last_check_str = self.last_check.strftime("%H:%M:%S")
            self.menu.add(rumps.MenuItem(f"Last check: {last_check_str}"))
        else:
            self.menu.add(rumps.MenuItem("Last check: Never"))
        self.menu.add(rumps.separator)

        # *** Recent Items Menu
        if self.recent_items:
            recent_menu = rumps.MenuItem("Recent Items")
            # Items are stored newest-first
            for item in self.recent_items:
                title = item['title']
                link = item['link']
                timestamp = item.get('timestamp', '')
                
                # Trim title to 64 characters max
                if len(title) > 64:
                    title = title[:61] + "..."
                
                # Format: [Mon 29 14:32] Title or [14:32] Title for today
                if timestamp:
                    display_title = f"[{timestamp}] {title}"
                else:
                    display_title = title
                
                recent_menu.add(rumps.MenuItem(display_title, callback=lambda sender, url=link: subprocess.run(['open', url])))
            self.menu.add(recent_menu)
        else:
            self.menu.add(rumps.MenuItem("No recent items"))
        # *** End Recent Items Menu

        # *** Options Menu
        options_menu = rumps.MenuItem("Options")
        options_menu.add(rumps.MenuItem("Test notification", callback=self.test_notification))
        options_menu.add(rumps.MenuItem("Open config", callback=self.open_config))
        options_menu.add(rumps.MenuItem("Reload config", callback=self.reload_config))
        options_menu.add(rumps.separator)
        options_menu.add(rumps.MenuItem("Clear seen data", callback=self.clear_seen_data))
        self.menu.add(options_menu)
        # *** End Options Menu

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("About Syndi", callback=self.show_about))
        self.menu.add(rumps.MenuItem("Quit Syndi", callback=self.quit_app))

    # Test notification action
    def test_notification(self,sender):
        current_time = datetime.now().strftime("%H:%M:%S")
        rumps.notification("Syndi", "Test Notification", current_time + " - This is a test notification from Syndi.")

    # Open config action
    def open_config(self,sender):
        # Try to open config.json with VSCode if available, otherwise use 'open'
        if subprocess.run(['which', 'code'], capture_output=True).returncode == 0:
            subprocess.run(['code', str(self.config_path)])
        else:
            subprocess.run(['open', str(self.config_path)])

    # Reload config action
    def reload_config(self,sender):
        self.load_config()
        self.build_menu()

        # Restart the feed checking timer with new interval
        self.timer.stop()
        self.timer = rumps.Timer(self.feeds_bg_checker, self.check_interval)
        self.timer.start()

        self.send_notification("Syndi", "Configuration Reloaded", "The configuration has been reloaded successfully.")

    # Clear seen data action
    def clear_seen_data(self, sender):
        # Bring dialog to front
        self.dialog_to_front()

        # Define the confirmation dialog
        response = rumps.alert(
            title="Clear Seen Data",
            message=f"Are you sure you want to clear all {len(self.seen_items)} seen items and {len(self.recent_items)} recent items?\n\nThis will trigger notifications for all RSS items on the next check.",
            ok="Clear",
            cancel="Cancel"
        )

        if response == 1:  # User clicked "Clear"
            self.seen_items = set()
            self.recent_items = []
            self.save_data()
            self.build_menu()
            self.send_notification("Syndi", "Data Cleared", "All seen and recent items have been cleared.")

    # About Syndi action
    def show_about(self,sender):

        # Bring dialog to front
        self.dialog_to_front()
        
        # Define the alert dialog
        rumps.alert(
            title="About Syndi",
            message="Syndi - Your simple syndication (RSS) notifier\n\n"
                    "Version 1.0\n"
                    "A lightweight macOS menu bar app for RSS feed notifications\n\n"
                    "Developed by EliezerGH\n"
                    "https://github.com/Eliezergh"
                #    f"Monitoring {len([f for f in self.feeds if f.get('enabled', True)])} feeds\n"
                #    f"Check interval: {self.check_interval}s"
        )

    # Quit Syndi action
    def quit_app(self,sender):
        rumps.quit_application()
    
    # ***** Functions *****

    # Load configuration from config.json
    def load_config(self):
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.config = config
                    self.feeds = config.get('feeds', [])
                    self.check_interval = config.get('check_interval_seconds', 300)
                    self.notification_enabled = config.get('notification_enabled', True)
                    self.show_preview = config.get('show_preview', True)
                    self.max_recent_items = config.get('max_recent_items', 10)
            else:
                print(f"Config file not found at {self.config_path}")
                self.config = {}
                self.feeds = []
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = {}
            rumps.alert("Config Error", f"Could not load config: {e}")

    # Save seen items to data.json
    def save_data(self):
        try:
            data = {
                'seen_items': list(self.seen_items),
                'recent_items': self.recent_items
            }
            with open(self.data_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving data: {e}")

    # Load seen items from data.json
    def load_data(self):
        try:
            if self.data_path.exists():
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    self.seen_items = set(data.get('seen_items', []))
                    self.recent_items = data.get('recent_items', [])
                    # Trim recent items to max configured
                    if len(self.recent_items) > self.max_recent_items:
                        self.recent_items = self.recent_items[-self.max_recent_items:]
                    print(f"Loaded {len(self.seen_items)} seen items and {len(self.recent_items)} recent items from data file")
            else:
                print(f"Data file not found at {self.data_path}, starting fresh")
                self.seen_items = set()
                self.recent_items = []
        except Exception as e:
            print(f"Error loading data: {e}")
            self.seen_items = set()
            self.recent_items = []

    # Feeds background checker
    def feeds_bg_checker(self, sender):
        if not self.feeds:
            return  # No feeds to check
        
        new_items_counter = 0
        self.last_check = datetime.now()

        for feed in self.feeds:
            if not feed.get('enabled', True):
                continue  # Skip disabled feeds
            
            try:
                # Fetch and parse the feed
                response = requests.get(feed['url'], timeout=10, headers={'User-Agent': 'Syndi RSS Notifier'})
                response.raise_for_status()  # Raise exception for HTTP errors
                parsed_feed = feedparser.parse(response.content)

                # Check for new items
                for entry in parsed_feed.entries:
                    item_id = entry.get('id', entry.get('link'))

                    if item_id not in self.seen_items:
                        # New item found
                        self.seen_items.add(item_id)
                        new_items_counter += 1

                        # Store recent item with timestamp from article's published date
                        link = entry.get('link', 'No link available')
                        entry_title = entry.get('title', 'No title')
                        
                        # Try to get published date from feed entry
                        published = entry.get('published_parsed') or entry.get('updated_parsed')
                        if published:
                            try:
                                from time import mktime
                                pub_datetime = datetime.fromtimestamp(mktime(published))
                                timestamp = pub_datetime.strftime("%d-%m-%y %H:%M")
                            except:
                                timestamp = datetime.now().strftime("%d-%m-%y %H:%M")
                        else:
                            timestamp = datetime.now().strftime("%d-%m-%y %H:%M")
                        
                        self.recent_items.append({
                            'title': entry_title,
                            'link': link,
                            'feed_title': parsed_feed.feed.get('title', 'No feed title'),
                            'timestamp': timestamp
                        })

                        # Trim recent items list
                        if len(self.recent_items) > self.max_recent_items:
                            self.recent_items.pop(0)  # Maintain only max recent items
                        
                        # Send notification
                        if self.notification_enabled:
                            notification_title = feed['name']
                            subtitle = entry_title
                            message = ""

                            if self.show_preview:
                                # Clean HTML tags from summary and get first 100 characters
                                summary = entry.get('summary', '')
                                clean_summary = re.sub('<[^<]+?>', '', summary)[:100]
                                message = clean_summary + "..."
                            else:
                                message = link

                            self.send_notification(notification_title, subtitle, message)
            except Exception as e:
                print(f"Error fetching feed {feed['url']}: {e}")
            
        # Save seen items to data file
        if new_items_counter > 0:
            self.save_data()
        
        # Update menu with recent items
        self.build_menu()

    # Send notification helper
    def send_notification(self, title, subtitle="", message=""):
        rumps.notification(title, subtitle, message)
    
    def dialog_to_front(self):
        # Use osascript to bring the alert to the front
        if getattr(sys, 'frozen', False):
            # When bundled, use the app name
            app_name = "Syndi"
        else:
            # When running as script, use Python
            app_name = "Python"
        script = f'tell application "System Events" to set frontmost of (first process whose name contains "{app_name}") to true'
        subprocess.run(['osascript', '-e', script])

def main():
    SyndiApp().run()

if __name__ == "__main__":
    main()
