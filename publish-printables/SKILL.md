---
name: publish-printables
description: Create Printables model drafts from validated CAD release manifests with a uv-managed Python Patchright script, including metadata, tags, galleries and Printables-only G-code.
---

# Publish Printables

This skill uses scripted browser interaction, without model-directed clicking or routine screenshots. A supported public upload API was not verified. Keep this skill with the sibling `publish-3d-model-release` validator.

From this skill directory:

1. Run `uv run --locked scripts/upload_printables.py --manifest <manifest>` for offline preflight.
2. Read [browser setup](references/browser.md) for the one-time login and editor mapping. Use `uv run --locked scripts/upload_printables.py login --profile-dir <private-profile>` to open normal Chrome at the Printables homepage in a dedicated profile. The user completes sign-in and security checkpoints; the script does not automate the authentication provider.
3. Use `inspect --profile-dir <private-profile>` to discover the live upload link, then inspect that URL with `--url`. Run the uploader with `--execute --profile-dir <private-profile> --ui-map <map.json>`. The map must come from the current editor inspection, not guessed selectors or the local test fixture. Save the map for subsequent releases.
4. The script fills metadata, adds each tag as a whole value, uploads file groups and clicks only the configured draft-save control. It reopens the saved editor for verification. An interrupted save or upload requires reconciliation using its state; never create another draft automatically.

When the user wants to see the inspection, use `inspect --keep-open` in an interactive terminal. It prints the result first and keeps Chrome visible even after an HTTP/access error; Enter closes it without retrying. Explain the transition from normal login Chrome to the script-controlled browser before completing the login helper. Do not treat a working manual login as proof that scripted access works.

The initial live editor mapping and a signed-in smoke test are required before describing this adapter as live-verified. A mapping failure is an actionable script error: use a focused text inspection and update the map, without dumping the whole page or falling back to screenshots automatically. Stop for login, CAPTCHA or terms requiring the user. Keep G-code restricted to Printables; verify its detected printer/material settings when a slicing profile is recorded.

Tests: `uv run --locked python -m unittest discover -s tests`.
