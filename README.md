# Translator

Translator is a real-time English-to-Vietnamese Windows call assistant. It
captures system audio and optionally microphone audio, then presents English
transcription, Vietnamese translation, conversation context, keywords, and a
recommended reply in fixed glanceable regions.

## Install

Download the newest Windows x64 MSI from GitHub Releases. The installer bundles
the offline Vosk model and creates Start Menu and Desktop shortcuts.

The MSI is not code-signed yet, so Windows SmartScreen may show an unknown
publisher warning. Verify the SHA-256 value published with each release before
installing.

## Gemini configuration

The application works with local fallbacks when Gemini is unavailable. To
enable the online Gemini path, set the API key in the current Windows user's
environment and restart Translator:

```powershell
[Environment]::SetEnvironmentVariable(
    "GEMINI_API_KEY",
    "your-key-here",
    "User"
)
```

No API key is stored in this repository or bundled in the installer.

## Privacy

- Audio is processed on the user's machine for speech recognition.
- When Gemini is configured, bounded conversation context is sent to the
  configured Gemini API to generate contextual assistance.
- Recordings and text exports stay under `%USERPROFILE%\Documents\Translator`.
- Runtime logs and window state stay under `%LOCALAPPDATA%\Translator`.

Do not record or process conversations without the participants' permission.

## Development

Requirements: Windows 10/11, Python 3.12, and the packages in
`requirements.txt`.

```powershell
python -m pip install -r requirements.txt
python main.py
python -m pytest -q
```

## Build the MSI

```powershell
.\build_msi.ps1 -Version 1.0.3
```

The build downloads WiX 3.14.1 into the ignored `.build-tools` directory and
leaves only the latest MSI under `release`.
