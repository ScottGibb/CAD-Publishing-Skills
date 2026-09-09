#!/usr/bin/env python3
"""Create and verify Thingiverse drafts. Run with this skill's uv environment."""

import argparse
import mimetypes
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "publish-3d-model-release" / "scripts")
)
from publisher_support import (
    PublishingError,
    Release,
    State,
    emit,
    error_text,
    file_lock,
    fingerprint,
    token_value,
)

API = "https://api.thingiverse.com"
LICENSES = {"CC-BY-4.0": "cc", "CC-BY-SA-4.0": "cc-sa"}


class RejectedRequest(PublishingError):
    """The server explicitly rejected a request before creating a resource."""


def draft_only(thing):
    if thing.get("is_published") not in (False, 0) or "is_published" not in thing:
        raise PublishingError(
            "Remote Thing is published or its draft status is unknown; no further writes"
        )


class Thingiverse:
    def __init__(self, token, client=None, storage=None):
        import httpx

        self.client = client or httpx.Client(timeout=120, follow_redirects=False)
        self.storage = storage or httpx.Client(timeout=300, follow_redirects=False)
        self.token = token

    def request(self, method, path, **kwargs):
        allowed = {
            "GET": r"/(?:things/\d+(?:/(?:files|images|tags|categories))?|categories(?:/[^/?]+)?|files/\d+)",
            "POST": r"/(?:things|things/\d+/files|files/\d+/finalize)",
            "PATCH": r"/things/\d+",
        }
        if not re.fullmatch(allowed.get(method, "(?!)"), path):
            raise PublishingError(
                "Unsupported API operation; this uploader only creates drafts"
            )
        response = self.client.request(
            method,
            API + path,
            headers={"Authorization": f"Bearer {self.token}"},
            **kwargs,
        )
        if not 200 <= response.status_code < 300:
            error = (
                RejectedRequest
                if response.status_code in (400, 401, 403, 404, 405, 413, 415, 422, 429)
                else PublishingError
            )
            raise error(
                f"Thingiverse {method} {path}: HTTP {response.status_code}; request was not retried"
            )
        result = response.json()
        if isinstance(result, dict) and (result.get("error") or result.get("errors")):
            raise PublishingError(
                f"Thingiverse rejected {method} {path}; inspect the draft before retrying"
            )
        return result

    def upload(self, thing_id, asset):
        spec = self.request(
            "POST", f"/things/{thing_id}/files", json={"filename": asset["name"]}
        )
        action = urlparse(spec["action"])
        host = action.hostname or ""
        allowed = (
            (host == "www.thingiverse.com" and action.path == "/upload_file_storage")
            or host == "storage.googleapis.com"
            or host.endswith((".storage.googleapis.com", ".s3.amazonaws.com"))
        )
        if (
            not allowed
            or action.scheme != "https"
            or action.port not in (None, 443)
            or action.username
        ):
            raise PublishingError(
                "Thingiverse returned an unrecognized storage destination"
            )
        fields = spec["fields"]
        finalize = fields["success_action_redirect"]
        if not re.fullmatch(
            r"https://api\.thingiverse\.com/files/\d+/finalize", finalize
        ):
            raise PublishingError("Thingiverse returned an unrecognized finalize URL")
        with open(asset["path"], "rb") as stream:
            # Keep the server's field order and let HTTPX set the multipart boundary.
            parts = [(key, (None, str(value))) for key, value in fields.items()]
            parts.append(
                (
                    "file",
                    (
                        asset["name"],
                        stream,
                        mimetypes.guess_type(asset["name"])[0]
                        or "application/octet-stream",
                    ),
                )
            )
            response = self.storage.post(spec["action"], files=parts)
        if response.status_code not in (200, 201, 204, 302, 303):
            raise PublishingError(
                f"Storage upload failed: HTTP {response.status_code}; reconcile before retrying"
            )
        if response.status_code in (302, 303) and not response.headers.get(
            "location", ""
        ).startswith(finalize):
            raise PublishingError("Unexpected storage redirect; it was not followed")
        return self.request("POST", finalize.removeprefix(API), json=fields)


def metadata(release, category):
    data = release.plan["thingiverse"]
    if not category:
        raise PublishingError(
            "Provide --category using Thingiverse's full category name"
        )
    return {
        "name": data["title"],
        "description": data["description"],
        "instructions": data.get("post_printing", {}).get("description", ""),
        "license": LICENSES[data["license"]],
        "category": category,
        "tags": data["tags"],
    }


def verify_metadata(remote, expected, tags):
    draft_only(remote)
    for key in ("name", "description", "instructions"):
        if str(remote.get(key, "")).strip() != expected[key].strip():
            raise PublishingError(f"Saved Thingiverse {key} differs from the release")
    names = {
        item["name"].casefold() if isinstance(item, dict) else item.casefold()
        for item in tags
    }
    if names != {tag.casefold() for tag in expected["tags"]}:
        raise PublishingError("Saved Thingiverse tags differ from the release")
    label = str(remote.get("license", "")).lower()
    if label != expected["license"]:
        is_sa = "share" in label
        if "attribution" not in label or any(
            x in label for x in ("noncommercial", "non-commercial", "no derivatives")
        ):
            raise PublishingError("Saved Thingiverse licence could not be verified")
        if is_sa != (expected["license"] == "cc-sa"):
            raise PublishingError("Saved Thingiverse licence differs from the release")


def run(release, state, api, category, thing_id=None):
    expected = metadata(release, category)
    if state.data.get("metadata_sha256", fingerprint(expected)) != fingerprint(
        expected
    ):
        raise PublishingError(
            "Category or metadata changed during this upload; reconcile the existing draft"
        )
    state.data["metadata_sha256"] = fingerprint(expected)
    if thing_id:
        if state.data.get("id") not in (None, thing_id):
            raise PublishingError("--thing-id conflicts with the recorded draft")
        state.data["id"] = thing_id
        if state.data.get("pending") == "create":
            state.done()
    if not state.data.get("id"):
        if state.data.get("pending") or state.existing_record().get("draft_url"):
            raise PublishingError(
                "A draft may already exist; supply its --thing-id instead of creating a duplicate"
            )
        state.pending("create")
        try:
            created = api.request("POST", "/things", json=expected)
        except RejectedRequest:
            state.done()
            raise
        state.data["id"] = int(created["id"])
        state.done()
    thing_id = int(state.data["id"])
    remote = api.request("GET", f"/things/{thing_id}")
    draft_only(remote)
    # Reapplying metadata is idempotent; file registration is not.
    api.request("PATCH", f"/things/{thing_id}", json=expected)
    assets = release.assets("thingiverse")
    files = api.request("GET", f"/things/{thing_id}/files")
    images = api.request("GET", f"/things/{thing_id}/images")
    for asset in assets:
        pool = images if asset["kind"] == "image" else files
        saved = state.data["assets"].get(asset["name"])
        if saved:
            if saved["sha256"] != asset["sha256"] or not any(
                str(x["id"]) == str(saved["id"]) for x in pool
            ):
                raise PublishingError(
                    "A previously uploaded asset changed or disappeared; reconcile the draft"
                )
            continue
        if state.data.get("pending"):
            raise PublishingError(
                "An upload has an uncertain result; inspect the saved draft before resuming"
            )
        if any(x.get("name") == asset["name"] for x in pool):
            raise PublishingError(
                f"Remote filename already exists without a verified local receipt: {asset['name']}"
            )
        state.pending({"asset": asset["name"], "sha256": asset["sha256"]})
        uploaded = api.upload(thing_id, asset)
        state.data["assets"][asset["name"]] = {
            "id": uploaded["id"],
            "sha256": asset["sha256"],
            "kind": asset["kind"],
        }
        state.done()
        emit({"platform": "thingiverse", "uploaded": asset["name"]})
    remote = api.request("GET", f"/things/{thing_id}")
    tags = api.request("GET", f"/things/{thing_id}/tags")
    verify_metadata(remote, expected, tags)
    categories = api.request("GET", f"/things/{thing_id}/categories")
    if expected["category"].casefold() not in {
        c["name"].casefold() for c in categories
    }:
        raise PublishingError("Saved Thingiverse category differs from the release")
    files = api.request("GET", f"/things/{thing_id}/files")
    images = api.request("GET", f"/things/{thing_id}/images")
    for receipt in state.data["assets"].values():
        pool = images if receipt["kind"] == "image" else files
        if not any(str(item["id"]) == str(receipt["id"]) for item in pool):
            raise PublishingError(
                "Thingiverse is still processing an uploaded asset; rerun this command later"
            )
    url = f"https://www.thingiverse.com/thing:{thing_id}"
    result = {
        "id": thing_id,
        "draft_url": url,
        "visibility": "draft",
        "files_verified": len(assets),
    }
    state.record(result)
    emit({"platform": "thingiverse", "status": "verified", **result})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--category")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--list-categories", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--thing-id", type=int)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args(argv)
    if args.list_categories:
        emit(
            Thingiverse(token_value(args.token_file, "THINGIVERSE_TOKEN")).request(
                "GET", "/categories"
            )
        )
        return 0
    if not args.manifest:
        parser.error("--manifest is required")
    release = Release(args.manifest)
    metadata(release, args.category)
    if not args.execute or args.dry_run:
        emit(release.summary("thingiverse"))
        return 0
    api = Thingiverse(token_value(args.token_file, "THINGIVERSE_TOKEN"))
    path = args.state or release.path.parent / ".publication-state" / "thingiverse.json"
    with file_lock(path.with_suffix(".lock")):
        run(
            release,
            State(release, "thingiverse", path),
            api,
            args.category,
            args.thing_id,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 - redact network exception URLs at the CLI boundary
        # HTTP library exceptions can include signed URLs: do not print them.
        emit({"platform": "thingiverse", "status": "error", "error": error_text(error)})
        raise SystemExit(2)
