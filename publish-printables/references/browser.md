# Printables browser status

The Printables browser adapter is retained as historical diagnostic code. It is not the supported upload workflow for this skill.

The user signed in successfully in ordinary Chrome, and the same dedicated profile remained signed in after a normal restart. When the Python-controlled browser opened that profile, the initial homepage request returned HTTP 403 and a security checkpoint. No live editor map or saved-and-reopened Printables draft was verified.

The observed result means the automated route is blocked by the site's bot detection. Patchright changes the browser driver, but this repository does not claim that it can get past the checkpoint. Do not add stealth flags, fingerprint changes, token extraction, cookie copying or alternate identities, and do not loop on the checkpoint.

Use the browser-free package command instead:

```bash
uv run --locked --no-dev scripts/upload_printables.py package \
  --manifest /absolute/release/release-manifest.json \
  --format markdown
```

It validates the release and produces paste-ready Markdown, newline-separated tags, grouped upload folders, per-file descriptions and an `UPLOAD.md` guide. The user completes the category, licence, file uploads and draft save in normal Chrome.
