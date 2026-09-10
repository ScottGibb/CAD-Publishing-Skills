#!/usr/bin/env python3
"""Private YouTube uploads using OAuth and persistent resumable HTTP sessions."""

import argparse
import json
import mimetypes
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "publish-3d-model-release" / "scripts")
)
from publisher_support import (
    PublishingError,
    Release,
    State,
    atomic_json,
    emit,
    error_text,
    file_lock,
    private_path,
    read_json,
)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
CHUNK_SIZE = 8 * 1024 * 1024


def metadata(release):
    video = release.plan.get("video")
    if not video:
        raise PublishingError("This release has no video")
    tags = release.manifest["publication"]["tags"]
    if (
        not video["title"]
        or len(video["title"]) > 100
        or any(x in video["title"] for x in "<>")
    ):
        raise PublishingError(
            "YouTube title must be 1-100 characters without angle brackets"
        )
    if len(video["description"].encode("utf-8")) > 5000:
        raise PublishingError("YouTube description exceeds 5000 UTF-8 bytes")
    if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise PublishingError("YouTube tags must be nonempty strings")
    tag_length = sum(len(t) + (2 if " " in t else 0) for t in tags) + max(
        0, len(tags) - 1
    )
    if tag_length > 500:
        raise PublishingError(
            "YouTube tags exceed 500 characters including separators and quotes"
        )
    return {
        "snippet": {
            "title": video["title"],
            "description": video["description"],
            "tags": tags,
            "categoryId": "28",
        },
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }


def session_url(url):
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.googleapis.com"
        or parsed.path != "/upload/youtube/v3/videos"
        or not parse_qs(parsed.query).get("upload_id")
    ):
        raise PublishingError("Unrecognized YouTube upload-session URL")
    return url


def parse_upload_response(response, total):
    if response.status_code in (200, 201):
        data = response.json()
        if not re.fullmatch(r"[\w-]{11}", data.get("id", "")):
            raise PublishingError("Upload response has no valid YouTube video ID")
        return total, data
    if response.status_code == 308:
        value = response.headers.get("Range", "")
        match = re.fullmatch(r"bytes=0-(\d+)", value) if value else None
        if value and not match:
            raise PublishingError("Unrecognized resumable upload range")
        offset = int(match.group(1)) + 1 if match else 0
        if offset > total:
            raise PublishingError("Server upload range exceeds video length")
        return offset, None
    raise PublishingError(
        f"YouTube upload HTTP {response.status_code}; retain the session and resolve the error before retrying"
    )


def get_credentials(client_secrets, token_path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = private_path(token_path)
    credentials = (
        Credentials.from_authorized_user_file(str(token_path))
        if token_path.exists()
        else None
    )
    if credentials and not credentials.has_scopes(SCOPES):
        raise PublishingError(
            "OAuth token needs youtube.upload and youtube.readonly; reauthorize with a new token path"
        )
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not client_secrets:
                raise PublishingError(
                    "Supply --client-secrets for first-time Google OAuth consent"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(private_path(client_secrets)), SCOPES
            )
            credentials = flow.run_local_server(port=0)
        atomic_json(token_path, json.loads(credentials.to_json()))
    return credentials


def upload(release, state, http, upload_state_path):
    body = metadata(release)
    video = (release.path.parent / release.plan["video"]["path"]).resolve()
    if not video.is_relative_to(release.path.parent):
        raise PublishingError("Video path must stay inside the release directory")
    total = video.stat().st_size
    if not total:
        raise PublishingError("Video is empty")
    upload_state_path = private_path(upload_state_path)
    session = read_json(upload_state_path) if upload_state_path.exists() else {}
    if session and session.get("manifest_sha256") != release.digest:
        raise PublishingError("Upload session belongs to a different manifest")
    if session.get("id"):
        state.data["id"] = session["id"]
        state.done()
        return session["id"]
    if session.get("url"):
        url = session_url(session["url"])
    else:
        if state.data.get("pending"):
            raise PublishingError(
                "Upload initiation has an uncertain result; retain the state and inspect before retrying"
            )
        state.pending("initiate-upload")
        response = http.post(
            UPLOAD,
            params={"uploadType": "resumable", "part": "snippet,status"},
            json=body,
            headers={
                "X-Upload-Content-Length": str(total),
                "X-Upload-Content-Type": mimetypes.guess_type(video.name)[0]
                or "application/octet-stream",
            },
            timeout=60,
            allow_redirects=False,
        )
        if response.status_code != 200:
            if response.status_code in (400, 401, 403, 404, 405, 413, 415, 422, 429):
                state.done()
            raise PublishingError(
                f"YouTube upload initiation HTTP {response.status_code}; no automatic retry"
            )
        url = session_url(response.headers.get("Location", ""))
        atomic_json(upload_state_path, {"manifest_sha256": release.digest, "url": url})
        state.done()
    response = http.put(
        url,
        data=b"",
        headers={"Content-Length": "0", "Content-Range": f"bytes */{total}"},
        timeout=60,
        allow_redirects=False,
    )
    offset, result = parse_upload_response(response, total)
    with video.open("rb") as stream:
        while result is None:
            stream.seek(offset)
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                raise PublishingError(
                    "Server has all bytes but has not confirmed a video ID; verify again later"
                )
            response = http.put(
                url,
                data=chunk,
                headers={
                    "Content-Length": str(len(chunk)),
                    "Content-Type": "application/octet-stream",
                    "Content-Range": f"bytes {offset}-{offset + len(chunk) - 1}/{total}",
                },
                timeout=60,
                allow_redirects=False,
            )
            next_offset, result = parse_upload_response(response, total)
            if result is None and next_offset <= offset:
                raise PublishingError(
                    "YouTube accepted no additional bytes; retain the session and retry later"
                )
            offset = next_offset
            emit(
                {"platform": "youtube", "uploaded_percent": round(100 * offset / total)}
            )
    video_id = result["id"]
    state.data["id"] = video_id
    state.done()
    atomic_json(upload_state_path, {"manifest_sha256": release.digest, "id": video_id})
    return video_id


def verify(release, state, http, video_id):
    response = http.get(
        VIDEOS,
        params={"id": video_id, "part": "snippet,status,processingDetails"},
        timeout=60,
        allow_redirects=False,
    )
    if response.status_code != 200:
        raise PublishingError(
            f"YouTube verification HTTP {response.status_code}; video ID was retained"
        )
    items = response.json().get("items", [])
    if len(items) != 1:
        raise PublishingError(
            "Uploaded video could not be read back using this Google account"
        )
    video, expected = items[0], metadata(release)
    if video.get("status", {}).get("privacyStatus") != "private":
        raise PublishingError(
            "YouTube video is not private; privacy was not changed automatically"
        )
    for key in ("title", "description", "tags", "categoryId"):
        actual = video.get("snippet", {}).get(key, [] if key == "tags" else None)
        wanted = expected["snippet"][key]
        equal = set(actual) == set(wanted) if key == "tags" else actual == wanted
        if not equal:
            raise PublishingError(f"Saved YouTube {key} differs from the release")
    status = video.get("status", {}).get("uploadStatus")
    processing = video.get("processingDetails", {}).get("processingStatus", "unknown")
    if status in ("failed", "rejected", "deleted") or processing in (
        "failed",
        "terminated",
    ):
        raise PublishingError(
            "YouTube processing failed; the recorded video will not be reuploaded automatically"
        )
    result = {
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "privacy": "private",
        "processing": processing,
    }
    state.record(result)
    label = (
        "verified"
        if processing == "succeeded"
        else "processing"
        if processing == "processing"
        else "processing-unknown"
    )
    emit({"platform": "youtube", "status": label, **result})


def apply_config(args):
    if not args.config:
        return
    path = private_path(args.config)
    try:
        data = tomllib.loads(path.read_text())["youtube"]
        if not isinstance(data, dict):
            raise ValueError()
        for key in ("client_secrets", "token_path", "session_path"):
            value = data.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError()
            if getattr(args, key) is None and value:
                candidate = Path(value).expanduser()
                setattr(args, key, private_path(candidate if candidate.is_absolute() else path.parent / candidate))
    except (OSError, ValueError, KeyError, TypeError):
        raise PublishingError("Invalid YouTube config: expected [youtube] credential file paths") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--config", type=Path, help="Shared private publishing config.toml")
    parser.add_argument("--client-secrets", type=Path)
    parser.add_argument("--token-path", type=Path)
    parser.add_argument("--session-path", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--video-id")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    apply_config(args)
    release = Release(args.manifest)
    metadata(release)
    if (not args.execute and not args.verify_only) or args.dry_run:
        emit(release.summary("youtube"))
        return 0
    if not args.token_path:
        parser.error("--token-path is required for authenticated operations")
    path = args.state or release.path.parent / ".publication-state" / "youtube.json"
    with file_lock(path.with_suffix(".lock")):
        state = State(release, "youtube", path)
        recorded = state.existing_record()
        url_id = parse_qs(urlparse(recorded.get("url", "")).query).get("v", [None])[0]
        video_id = state.data.get("id") or recorded.get("id") or url_id
        if args.video_id and video_id and video_id != args.video_id:
            raise PublishingError("--video-id conflicts with the recorded video")
        video_id = args.video_id or video_id
        if video_id and not re.fullmatch(r"[\w-]{11}", video_id):
            raise PublishingError("Invalid YouTube video ID")
        if args.verify_only and not video_id:
            raise PublishingError(
                "No completed video ID to verify; rerun --execute to resume its upload"
            )
        credentials = get_credentials(args.client_secrets, args.token_path)
        from google.auth.transport.requests import AuthorizedSession

        with AuthorizedSession(credentials) as http:
            if not video_id:
                session_path = (
                    args.session_path
                    or private_path(args.token_path).parent
                    / f"youtube-upload-{release.digest[:16]}.json"
                )
                video_id = upload(release, state, http, session_path)
            state.data["id"] = video_id
            state.done()
            verify(release, state, http, video_id)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 - redact signed upload-session URLs
        emit({"platform": "youtube", "status": "error", "error": error_text(error)})
        raise SystemExit(2)
