"""Load HTTP/Vosk modules before PySide's frozen runtime import hook.

PySide installs a feature importer during PyInstaller bootstrap. urllib3's
vendored ``six`` importer is not compatible with Shiboken source inspection,
so preload this dependency chain before the Qt runtime hook becomes active.
"""

import requests  # noqa: F401
import vosk  # noqa: F401
