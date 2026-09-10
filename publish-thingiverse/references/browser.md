# Thingiverse browser setup

The uploader uses Python Playwright, not the Thingiverse API. No access token is required. Install Google Chrome and keep a dedicated owner-only profile outside the repository and vault.

From this skill directory:

```bash
uv sync --locked
uv run --locked scripts/upload_thingiverse.py login --profile-dir /absolute/private/thingiverse-profile
uv run --locked scripts/upload_thingiverse.py inspect --profile-dir /absolute/private/thingiverse-profile
```

`login` opens ordinary Chrome at `https://www.thingiverse.com/`, without automation or debugging flags. The user signs in, completes any checkpoint, returns to Thingiverse and presses Enter in the terminal. Only this helper's dedicated Chrome process is closed. The command does not claim authentication succeeded.

`inspect` uses the saved profile and reports page title, relevant navigation and form controls without passwords, input values, cookies or screenshots. If a checkpoint or access denial remains, stop and ask the user to resolve it in normal Chrome. Do not automate Google sign-in or add stealth settings. `--headed` shows an inspection; `--channel chromium` is optional but does not solve an account-security restriction.

## Establish the live editor

Follow the site's observed upload link and pass it to `inspect --url <observed-url>`. On 10 September 2026, the signed-in **Create → Upload a Thing / Remix** menu linked to `https://www.thingiverse.com/thing:0/edit`; `/thing:create` was incorrect. Verify navigation again if the site changes. A user-authorized test draft was saved and reopened, verifying 8 model/document files, 4 gallery images, 10 tags, category, licence and unpublished status. The initial rejected save was recovered on that same authorized test workflow; the original listing was not altered.

The bundled [Bathroom / CC-BY-4.0 map](bathroom-cc-by-map.json) records these live controls. Reuse it only for that category and licence. It is site structure, not a fixture or a release-specific content plan. Native section content is described in [sections.md](sections.md).

For a different category or licence, save an adapted JSON map with:

- `schema: 1`, `platform: "thingiverse"`, the chosen `category` and manifest `license`.
- `create_url` and `editor_url`: actual observed URLs. The editor pattern includes `{id}`. Do not use URLs from the local test fixture.
- `fields`: locators for `title`, `description`, `tags`, and optional `post_printing`.
- `choices`: category/licence steps with `field`, `locator`, `verify`, and `expected` or `checked: true`. Use `option_label` for a native select, `check: true` for a checkbox, or an inspected click otherwise.
- `uploads` and `uploaded_items`: `file` and `image` locators. The latter select exact filenames; optional `name_attribute` reads an inspected attribute instead of text.
- `tag_mode`: `chips` (default), `async-select`, or `comma-separated`. The first two require `tag_items`. The current Thingiverse picker uses `async-select`: wait for an exact matching search result before clicking, then verify its chip. Pressing Enter immediately can silently lose tags. A missing exact match stops for inspection rather than selecting a different tag.
- `save_draft` and `draft_marker`: an unpublished save action and a visible saved-page draft marker. For a generic Save label, also map `unpublished_marker` proving unpublished state. The script never clicks Publish.
- Optional `open_editor`: safe navigation controls needed to reveal the form.
- `user_checkboxes`: consent checkboxes that require user authorization. By default, `--headed` brings them into view and pauses **before uploading**. When the user explicitly authorizes this draft's Thingiverse upload terms, `--accept-upload-terms` checks the exact `{"label":"Terms & Conditions"}` control. Other consent and security checks are not covered by this flag; it is not stored as a standing config preference.

A locator uses one of `label`, `placeholder`, `text`, `css`, or `role` with `name`. Optional `frame` selects an inspected iframe. Field/upload locators may include `open`, a list of safe tab/accordion controls. Use [Playwright's locator](https://playwright.dev/python/docs/locators) and [file-input](https://playwright.dev/python/docs/input#upload-files) interfaces; maps contain site structure, not release text.

## Run or resume

```bash
uv run --locked scripts/upload_thingiverse.py --manifest /absolute/release/release-manifest.json --ui-map /absolute/private/thingiverse-map.json
uv run --locked scripts/upload_thingiverse.py --manifest /absolute/release/release-manifest.json --ui-map /absolute/private/thingiverse-map.json --profile-dir /absolute/private/thingiverse-profile --headed --execute
```

Keep `.publication-state/thingiverse.json` after an interrupted run. Supply `--thing-id` or `--resume-url` only for the exact existing draft; resume verifies without re-uploading. Include the same `--sections` file when the draft uses native sections. `--update-sections` is an explicit edit operation, not the default resume path. Conflicting IDs stop execution. Published listings are not converted back into drafts. Use a specifically authorized new draft for a smoke test, not a duplicate of an existing published release.

On an existing saved draft, Thingiverse may render its terms checkbox disabled and unchecked. The updater leaves a disabled control alone and uses the normal Save as Draft action; it never removes the disabled attribute or forces a click. An enabled, unchecked terms control still needs explicit authorization or user acceptance.

Optional `--config` accepts a private TOML **browser-settings** file:

```toml
[thingiverse]
profile_dir = "/absolute/private/thingiverse-profile"
ui_map = "/absolute/private/thingiverse-map.json"
channel = "chrome"
```

Flags override file settings. Old `[thingiverse] token = ...` settings are rejected; use a separate browser config or direct flags. Preserve unrelated credentials, including YouTube's.
