# Windows MSI packaging

Run from PowerShell:

```powershell
.\build_msi.ps1
```

The build creates `release\Translator-<version>-x64.msi`. It includes the Vosk
and faster-whisper `tiny.en` models, so speech recognition can start without
downloading a model on the target PC. WiX 3.14.1 is downloaded from the official
WiX Toolset GitHub release into the ignored `.build-tools` directory.

Before each build, the script recursively removes existing `.msi` files inside
the project's validated `release` directory. A successful build therefore
leaves exactly one MSI: the newest `Translator-<version>-x64.msi`. If the build
fails, no obsolete installer is retained and accidentally mistaken for the new
release.

The installer targets 64-bit Windows and installs per-machine under Program
Files. It adds Start Menu and Desktop shortcuts, provides standard uninstall
support, and offers a checked-by-default `Launch Translator` option when setup
finishes. Runtime logs and window state are stored under
`%LOCALAPPDATA%\Translator`; recordings and exports remain under
`%USERPROFILE%\Documents\Translator`.

Secrets are never bundled. Configure `GEMINI_API_KEY` in the target Windows
user environment to enable Gemini; the deterministic offline fallback remains
available without it.
