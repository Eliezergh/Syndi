"""
py2app setup script for Syndi

Development build (fast, requires Python locally installed):
    python setup.py py2app -A

Production build MacOS app:
    python setup.py py2app
"""

from setuptools import setup

APP = ['../src/syndi.py']
DATA_FILES = [
    ('', ['../src/config.json']),  # Place config.json in Resources/
    ('', ['../src/media/menubar_icon.png']),  # Place icon in Resources/
]
OPTIONS = {
    'argv_emulation': False,
    'iconfile': '../src/media/syndi.icns',  # App icon for notifications and Finder
    'plist': {
        'CFBundleName': 'Syndi',
        'CFBundleDisplayName': 'Syndi',
        'CFBundleGetInfoString': 'Your simple syndication (RSS) notifier',
        'CFBundleIdentifier': 'com.eliezergh.syndi',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': True,  # This makes it a menu bar app (no dock icon)
        'NSHumanReadableCopyright': '2025 EliezerGH'
    },
    'packages': ['rumps', 'feedparser', 'requests', 'certifi', 'pkg_resources'],
    'excludes': ['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'test'],
    'strip': True,
    'optimize': 2,
}

setup(
    name='Syndi',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
