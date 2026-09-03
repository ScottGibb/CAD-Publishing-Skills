#!/usr/bin/env python3
"""Upload a prepared model video privately; OAuth material remains outside the vault."""

import argparse
import json
import sys
import time
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--client-secrets", required=True, type=Path,
                        help="Google OAuth desktop-client JSON, outside the vault")
    parser.add_argument("--token-path", required=True, type=Path,
                        help="OAuth token location, outside the vault")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    video = manifest.get("video")
    if not video:
        raise ValueError("This release has no video")
    video_path = manifest_path.parent / video["path"]
    if not video_path.is_file():
        raise ValueError("Release video is missing")
    request_data = {"snippet": {"title": video["title"], "description": video["description"],
                                "tags": manifest["publication"]["tags"], "categoryId": "28"},
                    "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
    if args.dry_run:
        print(json.dumps({"video": str(video_path), "metadata": request_data, "privacy": "private"}, indent=2))
        return 0
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as error:
        raise RuntimeError("Run this script through this skill's `uv run` environment") from error
    credentials = None
    if args.token_path.is_file():
        credentials = Credentials.from_authorized_user_file(str(args.token_path), SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(args.client_secrets), SCOPES)
            credentials = flow.run_local_server(port=0)
        args.token_path.parent.mkdir(parents=True, exist_ok=True)
        args.token_path.write_text(credentials.to_json(), encoding="utf-8")
    youtube = build("youtube", "v3", credentials=credentials)
    request = youtube.videos().insert(part="snippet,status", body=request_data,
        media_body=MediaFileUpload(str(video_path), resumable=True))
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response["id"]
    for _ in range(60):
        status = youtube.videos().list(part="processingDetails,status", id=video_id).execute()["items"][0]
        if status.get("processingDetails", {}).get("processingStatus") != "processing":
            break
        time.sleep(10)
    record_path = manifest_path.parent / "publication-record.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {"schema": 1}
    record["youtube"] = {"url": f"https://www.youtube.com/watch?v={video_id}", "privacy": "private"}
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Private video uploaded: {record['youtube']['url']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        print(f"YouTube upload failed: {error}", file=sys.stderr)
        raise SystemExit(2)
