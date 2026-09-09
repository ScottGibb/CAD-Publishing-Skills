# Thingiverse API setup

Primary reference: [Thingiverse Upload Guide](https://www.thingiverse.com/developers/upload-guide). The [current OpenAPI reference](https://www.thingiverse.com/developers/swagger) supplies metadata fields and licence codes. Checked 9 September 2026.

Supply your Thingiverse application access token in a private text file outside the repository/vault, or through `THINGIVERSE_TOKEN`. Use the developer account's normal application/OAuth setup; never extract another app's embedded key or browser cookies. The uploader sends the token only to `api.thingiverse.com`.

The guide's flow is implemented: create/load the Thing; request a file attachment; POST multipart data to the returned storage action; then POST to the returned finalize URL. Field order is retained. Storage requests use a separate HTTP client without the API Authorization header. Some finalize endpoints are marked deprecated in the current Swagger files, while the requested guide still uses them. If this documented flow stops working, retain its receipt and update the adapter against current first-party docs before retrying.

`is_wip` is not a privacy flag. The uploader never calls `/publish`, and checks `is_published` after creating/loading the Thing and before recording success. This implementation has offline HTTP contract coverage, not a live authenticated upload certification.

Use the full category name from the API. For example, from the skill directory:

```bash
uv run --locked scripts/upload_thingiverse.py --list-categories --token-file /private/credentials/thingiverse-token.txt
uv run --locked scripts/upload_thingiverse.py --manifest /absolute/release/release-manifest.json --category Bathroom
```

Add `--execute` and the token-file argument for the authorized draft. The local `.publication-state/thingiverse.json` records the draft ID and completed asset IDs. Never delete this receipt to resolve an error: it prevents duplicate uploads. For an ambiguous creation, identify the existing draft and pass `--thing-id`. For an ambiguous file upload, inspect that exact draft/file before reconciling its receipt.

Gallery images use the file-attachment flow. The API instructions field includes assembly text; the script does not claim to reproduce or verify the website's dedicated Post-Printing editor or hero-image layout.
