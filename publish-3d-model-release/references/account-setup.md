# Publishing account setup

Each platform has its own Python skill and locked `uv` environment. First-time setup:

- [Thingiverse dedicated login and editor mapping](../../publish-thingiverse/references/browser.md).
- [Printables manual upload package](../../publish-printables/SKILL.md).
- [YouTube OAuth and resumable uploads](../../publish-youtube/references/oauth.md).

The coordinator accepts JSON settings with these platform objects. Omit YouTube when the release has no video. Use absolute paths for files; the example paths are illustrative.

```json
{
  "thingiverse": {"category": "Bathroom", "profile_dir": "/private/credentials/thingiverse-profile", "ui_map": "/private/settings/thingiverse-map.json"},
  "printables": {"output_dir": "/absolute/release/printables-manual-upload", "format": "json"},
  "youtube": {"config": "/private/credentials/config.toml"}
}
```

Optional resume settings are `thing_id`, `resume_url`, and `video_id` on their corresponding platforms. `state` overrides a platform's receipt file. Printables accepts `output_dir` and `format` (`json` or `markdown`) for its browser-free manual upload package. YouTube also accepts `session_path`; Thingiverse accepts `headed` and `channel` (`chrome` by default), plus `config` pointing to a private TOML browser-settings file.

Thingiverse accepts `sections` pointing to its [native section content plan](../../publish-thingiverse/references/sections.md), including print settings, post-printing photos and custom sections. Keep supplying the same plan on verification runs. Per-draft terms acceptance and explicit section edits use the direct Thingiverse CLI flags; they are not stored as standing coordinator settings.

Run `uv run --locked scripts/publish_release.py --manifest <manifest> --config <settings.json>` to preflight the configured commands and create the Printables manual package. Add `--execute` for authorized Thingiverse or YouTube uploads; the Printables package is already prepared during preflight and is reported as `ready-for-manual-upload`. The coordinator runs platforms sequentially and reports each failure once; it continues independent platforms and exits nonzero if anything failed.
