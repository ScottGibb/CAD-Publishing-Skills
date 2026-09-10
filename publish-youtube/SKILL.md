---
name: publish-youtube
description: Upload a prepared CAD exploded-view or assembly video privately to YouTube using a uv-managed Python script, with manifest tags, OAuth, resumable transfer and recorded video IDs.
---

# Publish YouTube

Use this API script with a validated release manifest. Keep this skill with the sibling `publish-3d-model-release` validator. Commands run from this skill directory.

1. Run `uv run --locked scripts/upload_youtube.py --manifest <manifest>` for a compact offline preflight, including tags and the private setting.
2. Add `--execute --client-secrets <desktop-oauth-client.json> --token-path <private-token.json>` for the authorized private upload. Read [OAuth and resuming](references/oauth.md) for first-time setup or interrupted uploads.
3. Reuse the saved state. A known video ID is verified rather than uploaded again. Run `--verify-only` to check processing later; do not repeatedly poll in the conversation.
4. Report the private URL and processing status returned by the script. Preserve other platforms in `publication-record.json`.

Run the script rather than reading its implementation. It hashes the video, reuses manifest tags, validates YouTube length limits and sets `privacyStatus=private`. It never opens YouTube Studio or changes privacy to public/unlisted. OAuth consent may need a browser once. Do not store credentials or resumable upload URLs in the vault or repository.

Tests: `uv run --locked python -m unittest discover -s tests`.

## Shared TOML configuration

Use `--config /Users/scottgibb/.config/cad-publishing/config.toml` for the same private configuration used by Thingiverse:

```toml
[youtube]
client_secrets = "google-client.json"
token_path = "youtube-token.json"
```

Paths resolve relative to the TOML file; explicit CLI path options override them. Google OAuth client and refresh credentials remain in their native JSON files outside the repository and vault. The client file must be downloaded from Google Cloud; the token file is created by the first successful consent flow. Do not create placeholder credential JSON files.
