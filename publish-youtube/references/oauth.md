# YouTube OAuth and resuming

Use a Google Cloud OAuth Desktop client with the YouTube Data API enabled. Keep the client JSON, token JSON and upload session file outside the repository and Obsidian vault. The script uses Google's Python OAuth library and [documented resumable upload protocol](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol).

First perform the offline preflight, then the authorized upload:

```bash
uv run --locked scripts/upload_youtube.py --manifest /absolute/release/release-manifest.json
uv run --locked scripts/upload_youtube.py --manifest /absolute/release/release-manifest.json --client-secrets /private/credentials/google-client.json --token-path /private/credentials/youtube-token.json --execute
```

The user completes Google's consent flow once. Scopes are `youtube.upload` and `youtube.readonly`, the latter for checking the private video's metadata and processing. Existing upload-only tokens need fresh consent using a new token path. Credentials refresh through Google and are saved with owner-only file permissions.

Video metadata follows [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert): manifest title, description and tags, Science & Technology category, private visibility and the existing workflow's not-made-for-kids setting. Title/tag/description limits are validated before upload. No YouTube Studio automation is used.

Transfer checkpoints live beside the token by default, named `youtube-upload-<manifest-hash>.json`. This file can contain a sensitive resumable URL; never paste it into chat. Completed video IDs also go into the release's `.publication-state/youtube.json`. Repeating `--execute` resumes the same session or verifies its completed video, including when the final upload response was lost. An ambiguous initiation or expired session stops rather than creating a possible duplicate.

Verification reads privacy, title, description, tags, category and processing once. A processing failure is an error; a video still processing is reported as pending, not finished. Use the same command with `--verify-only` to check later. It preserves the other platforms in `publication-record.json`. Authentication, quota and live transfer behaviour still need an authenticated smoke test; automated tests use a simulated server.

## Shared TOML configuration

Use `--config /Users/scottgibb/.config/cad-publishing/config.toml` for the same private configuration used by Thingiverse:

```toml
[youtube]
client_secrets = "google-client.json"
token_path = "youtube-token.json"
```

Paths resolve relative to the TOML file; explicit CLI path options override them. Google OAuth client and refresh credentials remain in their native JSON files outside the repository and vault. The client file must be downloaded from Google Cloud; the token file is created by the first successful consent flow. Do not create placeholder credential JSON files.
