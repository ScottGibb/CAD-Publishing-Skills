# Publishing account setup

Each platform has its own Python skill and locked `uv` environment. First-time setup:

- [Thingiverse API token and upload guide](../../publish-thingiverse/references/api.md).
- [Printables dedicated login and editor mapping](../../publish-printables/references/browser.md).
- [YouTube OAuth and resumable uploads](../../publish-youtube/references/oauth.md).

The coordinator accepts JSON settings with these platform objects. Omit YouTube when the release has no video. Use absolute paths for files; the example paths are illustrative.

```json
{
  "thingiverse": {"category": "Bathroom", "token_file": "/private/credentials/thingiverse-token.txt"},
  "printables": {"profile_dir": "/private/credentials/printables-profile", "ui_map": "/private/settings/printables-map.json"},
  "youtube": {"client_secrets": "/private/credentials/google-client.json", "token_path": "/private/credentials/youtube-token.json"}
}
```

Optional resume settings are `thing_id`, `resume_url`, and `video_id` on their corresponding platforms. `state` overrides a platform's receipt file. YouTube also accepts `session_path`; Printables accepts `headed` for a visible diagnostic run.

Run `uv run --locked scripts/publish_release.py --manifest <manifest> --config <settings.json>` to preflight the configured commands. Add `--execute` only for an authorized upload. The coordinator runs platforms sequentially and reports each failure once; it continues independent platforms and exits nonzero if anything failed.
