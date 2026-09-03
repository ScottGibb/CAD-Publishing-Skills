# Publishing account setup

Sign in to Thingiverse and Printables in the browser Codex will use. The publishing workflow only creates drafts, and requires review of each saved draft URL.

For YouTube, create a Google Cloud OAuth Desktop client with the YouTube Data API enabled. Keep the downloaded client-secret JSON and generated token file outside this vault. From the publishing skill directory, `uv run scripts/upload_youtube.py` resolves the locked project dependencies; run it first with `--dry-run`.
