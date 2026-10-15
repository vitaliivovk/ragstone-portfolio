#!/usr/bin/env python3
"""
Upload pinecone-pipeline/source_data to SharePoint under AI/<version>/ mirroring folder layout.

Requires: pip install -r scripts/sharepoint_sync_requirements.txt

Agents: default is **human upload** (`.cursor/skills/knowledge-base-curator`) — automated sync often blocked by access rights.

Auth:
  --auth device   Delegated (device code); needs Files.ReadWrite.All + Sites.Read.All (or SharePoint file scopes).
  --auth app      Application (client credentials); needs Sites.Selected + per-site grant (see docs/TASKS.md task 35).

Examples:
  python scripts/sharepoint_sync.py --auth device --dry-run
  python scripts/sharepoint_sync.py --auth device --remote-prefix prod
  See .cursor/skills/knowledge-base-curator/citation-sharepoint-links.md — use dev/prod to match Terraform sharepoint_library_base_url.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

GRAPH = "https://graph.microsoft.com/v1.0"
LARGE_FILE_BYTES = 4 * 1024 * 1024


def encode_drive_item_path(rel: str) -> str:
    """Encode each path segment for Graph ``root:/...:/`` URLs."""
    return "/".join(quote(segment, safe="") for segment in rel.split("/") if segment)


def _require_deps() -> None:
    try:
        import httpx  # noqa: F401
        import msal  # noqa: F401
    except ImportError as exc:
        sys.stderr.write(
            "Missing dependencies. Run:\n"
            "  pip install -r scripts/sharepoint_sync_requirements.txt\n"
        )
        raise SystemExit(1) from exc


def _tenant_id() -> str:
    tenant = os.environ.get("MICROSOFT_APP_TENANT_ID", "").strip()
    if not tenant:
        raise SystemExit("Set MICROSOFT_APP_TENANT_ID in the environment.")
    return tenant


def _app_token() -> str:
    _require_deps()
    import httpx

    app_id = os.environ["MICROSOFT_APP_ID"].strip()
    secret = os.environ["MICROSOFT_APP_PASSWORD"].strip()
    tenant = _tenant_id()
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": app_id,
        "client_secret": secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(token_url, data=data)
        response.raise_for_status()
        payload = response.json()
    return str(payload["access_token"])


def _device_token(scopes: list[str]) -> str:
    _require_deps()
    import msal

    tenant = _tenant_id()
    app_id = os.environ.get("GRAPH_DEVICE_CLIENT_ID", "").strip() or os.environ.get(
        "MICROSOFT_APP_ID", ""
    ).strip()
    if not app_id:
        raise SystemExit(
            "Set MICROSOFT_APP_ID (or GRAPH_DEVICE_CLIENT_ID) for delegated device flow."
        )
    authority = f"https://login.microsoftonline.com/{tenant}"
    app = msal.PublicClientApplication(app_id, authority=authority)
    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise SystemExit(f"Device flow failed: {flow}")
    print(flow["message"], flush=True)
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise SystemExit(f"Auth failed: {result.get('error_description', result)}")
    return str(result["access_token"])


def _graph_get(token: str, url: str) -> dict[str, Any]:
    _require_deps()
    import httpx

    with httpx.Client(timeout=120.0) as client:
        response = client.get(
            url, headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json()


def _graph_put_bytes(
    token: str, upload_url: str, body: bytes, content_type: str
) -> dict[str, Any]:
    _require_deps()
    import httpx

    with httpx.Client(timeout=300.0) as client:
        response = client.put(
            upload_url,
            content=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": content_type,
            },
        )
        response.raise_for_status()
        if response.content:
            return response.json()
        return {}


def _resolve_drive(
    token: str, hostname: str, site_path: str, library_name: str
) -> tuple[str, str]:
    site_key = f"{hostname}:{site_path}"
    site = _graph_get(token, f"{GRAPH}/sites/{site_key}")
    if not site or "id" not in site:
        raise SystemExit(f"Site not found or no access: {site_key}")
    site_id = site["id"]
    drives = _graph_get(token, f"{GRAPH}/sites/{site_id}/drives")
    items = drives.get("value", [])
    drive_id = ""
    for drive in items:
        if drive.get("name") == library_name:
            drive_id = str(drive["id"])
            break
    if not drive_id and items:
        drive_id = str(items[0]["id"])
    if not drive_id:
        raise SystemExit("No document library found on site.")
    return str(site_id), drive_id


def _ensure_folder_path(
    token: str, drive_id: str, segments: list[str], dry_run: bool
) -> None:
    if not segments:
        return
    _require_deps()
    import httpx

    parent_path = ""
    for segment in segments:
        next_path = f"{parent_path}/{segment}" if parent_path else segment
        encoded = encode_drive_item_path(next_path)
        check_url = f"{GRAPH}/drives/{drive_id}/root:/{encoded}:"
        existing = _graph_get(token, check_url)
        if existing.get("id"):
            parent_path = next_path
            continue
        if dry_run:
            print(f"[dry-run] would create folder: {next_path}")
            parent_path = next_path
            continue
        parent_encoded = encode_drive_item_path(parent_path) if parent_path else ""
        if parent_encoded:
            create_url = f"{GRAPH}/drives/{drive_id}/root:/{parent_encoded}:/children"
        else:
            create_url = f"{GRAPH}/drives/{drive_id}/root/children"
        body = {
            "name": segment,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                create_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                content=json.dumps(body),
            )
            if response.status_code in (200, 201):
                parent_path = next_path
                continue
            if response.status_code == 409:
                parent_path = next_path
                continue
            response.raise_for_status()
            parent_path = next_path


def _upload_file(
    token: str,
    drive_id: str,
    remote_rel: str,
    local_path: Path,
    dry_run: bool,
) -> str:
    rel_encoded = encode_drive_item_path(remote_rel)
    upload_url = f"{GRAPH}/drives/{drive_id}/root:/{rel_encoded}:/content"
    size = local_path.stat().st_size
    content_type = "application/octet-stream"
    suffix = local_path.suffix.lower()
    if suffix == ".pdf":
        content_type = "application/pdf"
    elif suffix in (".docx",):
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    elif suffix in (".pptx",):
        content_type = (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    elif suffix in (".xlsx",):
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if dry_run:
        return f"[dry-run] {local_path} -> {remote_rel} ({size} bytes)"

    data = local_path.read_bytes()
    if len(data) <= LARGE_FILE_BYTES:
        _graph_put_bytes(token, upload_url, data, content_type)
        return f"uploaded {remote_rel} ({len(data)} bytes)"

    return _upload_large_session(
        token, drive_id, rel_encoded, data, content_type
    )


def _upload_large_session(
    token: str,
    drive_id: str,
    rel_encoded: str,
    data: bytes,
    content_type: str,
) -> str:
    _require_deps()
    import httpx

    session_url = f"{GRAPH}/drives/{drive_id}/root:/{rel_encoded}:/createUploadSession"
    file_name = unquote(rel_encoded.split("/")[-1]) if "/" in rel_encoded else unquote(rel_encoded)
    meta = {
        "item": {
            "@microsoft.graph.conflictBehavior": "replace",
            "name": file_name,
        }
    }
    with httpx.Client(timeout=300.0) as client:
        response = client.post(
            session_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            content=json.dumps(meta),
        )
        response.raise_for_status()
        upload_session = response.json()
    upload_url_session = str(upload_session["uploadUrl"])
    chunk_size = 8 * 1024 * 1024
    start = 0
    total = len(data)
    while start < total:
        end = min(start + chunk_size, total) - 1
        chunk = data[start : end + 1]
        with httpx.Client(timeout=600.0) as client:
            response = client.put(
                upload_url_session,
                content=chunk,
                headers={
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {start}-{end}/{total}",
                },
            )
        if response.status_code not in (200, 201, 202):
            response.raise_for_status()
        if response.status_code in (200, 201):
            break
        start = end + 1
    return f"uploaded (large) {rel_encoded} ({total} bytes)"


def _should_skip(
    token: str, drive_id: str, remote_rel: str, local_path: Path
) -> bool:
    rel_encoded = encode_drive_item_path(remote_rel)
    meta_url = f"{GRAPH}/drives/{drive_id}/root:/{rel_encoded}:"
    remote = _graph_get(token, meta_url)
    if not remote or "size" not in remote:
        return False
    remote_size = int(remote["size"])
    local_size = local_path.stat().st_size
    if remote_size != local_size:
        return False
    lm_remote = remote.get("lastModifiedDateTime") or ""
    lm_local = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(local_path.stat().st_mtime)
    )
    if lm_remote[:16] == lm_local[:16]:
        return True
    return False


def _collect_local_files(source_root: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("~$"):
            continue
        rel = path.relative_to(source_root).as_posix()
        out.append((path, rel))
    return out


def _report_urls(base_url: str, files: list[tuple[Path, str]]) -> None:
    base = base_url.rstrip("/")
    for _local, rel in files:
        suffix = encode_drive_item_path(rel)
        print(f"{base}/{suffix}")


def main() -> None:
    _require_deps()

    parser = argparse.ArgumentParser(
        description="Sync source_data to SharePoint AI/<remote-prefix>/ (match Terraform citation base URL)"
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("pinecone-pipeline/source_data"),
        help="Local corpus root (default: pinecone-pipeline/source_data)",
    )
    parser.add_argument(
        "--remote-prefix",
        default="dev",
        help="Folder under AI/ (default: dev -> AI/dev/...); use prod for production library",
    )
    parser.add_argument("--site-host", default="contoso.sharepoint.com")
    parser.add_argument("--site-path", default="/sites/Northwind-AI")
    parser.add_argument(
        "--library",
        default="Shared Documents",
        help="Document library display name",
    )
    parser.add_argument("--auth", choices=("device", "app"), default="device")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report-urls",
        action="store_true",
        help="Print resolved file URLs (needs SHAREPOINT_LIBRARY_BASE_URL)",
    )
    parser.add_argument("--skip-unchanged", action="store_true", default=True)
    parser.add_argument("--no-skip-unchanged", action="store_false", dest="skip_unchanged")
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    if not source_root.is_dir():
        raise SystemExit(f"Source root is not a directory: {source_root}")

    if args.auth == "app":
        token = _app_token()
        scopes_note = "app-only (Sites.Selected grant required for uploads)"
    else:
        token = _device_token(
            scopes=[
                "https://graph.microsoft.com/Files.ReadWrite.All",
                "https://graph.microsoft.com/Sites.Read.All",
            ]
        )
        scopes_note = "delegated device flow"

    print(f"Auth: {scopes_note}", flush=True)
    site_id, drive_id = _resolve_drive(
        token, args.site_host, args.site_path, args.library
    )
    print(f"site_id={site_id} drive_id={drive_id}", flush=True)

    remote_base = f"AI/{args.remote_prefix.strip('/')}".strip("/")
    _ensure_folder_path(
        token, drive_id, remote_base.split("/"), args.dry_run
    )

    files = _collect_local_files(source_root)
    print(f"Local files: {len(files)}", flush=True)

    if args.report_urls:
        base = ""
        for env_key in ("SHAREPOINT_LIBRARY_BASE_URL", "SHAREPOINT_BASE_URL"):
            candidate = os.environ.get(env_key, "").strip()
            if candidate:
                base = candidate
                break
        if not base:
            raise SystemExit(
                "Set SHAREPOINT_LIBRARY_BASE_URL or SHAREPOINT_BASE_URL for --report-urls "
                "(e.g. https://contoso.sharepoint.com/sites/Northwind-AI/Shared%20Documents/AI/dev)"
            )
        _report_urls(base, files)
        return

    uploaded = 0
    skipped = 0
    for local_path, rel in files:
        remote_rel = f"{remote_base}/{rel}"
        parent_segments = Path(remote_rel).parent.as_posix().split("/")
        if parent_segments and parent_segments != [""]:
            _ensure_folder_path(token, drive_id, parent_segments, args.dry_run)
        if args.skip_unchanged and not args.dry_run:
            try:
                if _should_skip(token, drive_id, remote_rel, local_path):
                    skipped += 1
                    continue
            except Exception:
                pass
        msg = _upload_file(token, drive_id, remote_rel, local_path, args.dry_run)
        print(msg, flush=True)
        uploaded += 1

    print(f"Done. uploaded={uploaded} skipped_unchanged={skipped}", flush=True)


if __name__ == "__main__":
    main()
