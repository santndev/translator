# Translator

Author: solesantn@gmail.com

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

## Online AI configuration

The application works with local fallbacks when online AI is unavailable.
OpenAI (`gpt-5.6-luna`) is preferred when `TRANSLATOR_OPENAI_API_KEY` is configured;
Gemini remains the second provider. Set either key in the current Windows
user's environment and restart Translator:

```powershell
[Environment]::SetEnvironmentVariable(
    "TRANSLATOR_OPENAI_API_KEY",
    "your-openai-key-here",
    "User"
)

[Environment]::SetEnvironmentVariable(
    "GEMINI_API_KEY",
    "your-gemini-key-here",
    "User"
)
```

Optional overrides are `OPENAI_MODEL`, `OPENAI_API_BASE`, and
`OPENAI_TIMEOUT_SECONDS`. The default OpenAI model is `gpt-5.6-luna`. OpenAI
requests use the Responses API with `store: false`, structured output, low
verbosity, and no reasoning effort to minimize latency and token use.

No API key is stored in this repository or bundled in the installer.

## User profile

On first launch, Translator creates:

```text
%LOCALAPPDATA%\Translator\user_profile.json
```

Close Translator, edit the values you want it to use, then restart the app.
For example:

```json
{
  "preferred_name": "Minh",
  "birth_date": "2000-10-20",
  "job_title": "Software Engineer",
  "company": "Example Company",
  "location": "Ho Chi Minh City",
  "years_experience": 5,
  "preferred_reply_style": "short_and_natural",
  "custom_facts": {},
  "cloud_shareable_fields": ["preferred_reply_style"]
}
```

Questions such as “What year were you born?”, “How old are you?”, “What’s
your name?”, and “What do you do?” are answered directly from the local profile
without an API call. Exact age requires a full `birth_date`; with only
`birth_year`, Translator recommends the accurate birth-year answer instead of
guessing an age. Personal fields are sent to online AI only when explicitly
listed in `cloud_shareable_fields`.

## Privacy

- Audio is processed on the user's machine for speech recognition.
- When an online AI provider is configured, bounded conversation context is
  sent to that provider to generate contextual assistance.
- Profile fields remain local unless explicitly listed in
  `cloud_shareable_fields`.
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

## GitHub Releases

GitHub Actions builds and publishes an MSI only when a version tag is pushed.
Use the `vMAJOR.MINOR.PATCH` format:

```powershell
git tag v1.0.4
git push origin v1.0.4
```

Normal pushes and pull requests do not create releases.
