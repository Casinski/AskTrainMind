from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from asktrainmind.app.config import cache_dir

DEFAULT_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


@dataclass
class SharePointLocation:
    tenant: str
    site_path: str
    folder_path: str


@dataclass
class SharePointDownloadResult:
    ok: bool
    status: str
    message: str
    local_path: Path | None = None


def parse_sharepoint_folder_url(url: str) -> SharePointLocation:
    parsed = urlparse(url)
    tenant = parsed.netloc
    path = unquote(parsed.path)
    marker = "/sites/"
    if marker not in path:
        raise ValueError("URL SharePoint non riconosciuta")

    after = path.split(marker, maxsplit=1)[1].strip("/")
    parts = after.split("/")
    if len(parts) < 2:
        raise ValueError("Percorso sito/cartella non valido")
    site_path = parts[0]
    folder_parts = parts[1:]
    if folder_parts and folder_parts[0].lower() == "shared documents":
        folder_parts[0] = "Shared Documents"
    folder_path = "/".join(folder_parts)
    return SharePointLocation(tenant=tenant, site_path=site_path, folder_path=folder_path)


def _acquire_token(client_id: str = DEFAULT_CLIENT_ID) -> str:
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        raise RuntimeError("Autenticazione interattiva non disponibile in CI")

    try:
        import msal
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("msal non installato") from exc

    app = msal.PublicClientApplication(client_id=client_id, authority="https://login.microsoftonline.com/common")
    scopes = ["Files.Read", "Sites.Read.All"]
    use_device_code = os.environ.get("ASKTRAINMIND_USE_DEVICE_CODE", "").lower() in {"1", "true", "yes"}

    if use_device_code:
        flow = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            raise RuntimeError("Impossibile iniziare device-code flow")
        token = app.acquire_token_by_device_flow(flow, timeout=120)
    else:
        try:
            token = app.acquire_token_interactive(scopes=scopes)
        except Exception as exc:
            raise RuntimeError(f"Login interattivo non riuscito: {exc}") from exc

    if "access_token" not in token:
        raise RuntimeError(token.get("error_description", "Autenticazione non riuscita"))
    return str(token["access_token"])


def download_workbook(
    sharepoint_folder_url: str,
    target_filename: str,
    destination_dir: Path | None = None,
) -> SharePointDownloadResult:
    try:
        location = parse_sharepoint_folder_url(sharepoint_folder_url)
    except Exception as exc:
        return SharePointDownloadResult(False, "invalid_url", f"URL non valida: {exc}")

    dest_dir = destination_dir or cache_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        token = _acquire_token()
    except Exception as exc:
        return SharePointDownloadResult(False, "auth_error", f"Autenticazione fallita: {exc}")

    headers = {"Authorization": "Bearer " + token}

    try:
        site_url = f"{GRAPH_ROOT}/sites/{location.tenant}:/sites/{location.site_path}"
        site_resp = requests.get(site_url, headers=headers, timeout=30)
        site_resp.raise_for_status()
        site_id = site_resp.json()["id"]

        drive_resp = requests.get(f"{GRAPH_ROOT}/sites/{site_id}/drives", headers=headers, timeout=30)
        drive_resp.raise_for_status()
        drives = drive_resp.json().get("value", [])
        drive = next((d for d in drives if d.get("name", "").lower() in {"documents", "documenti"}), None) or (
            drives[0] if drives else None
        )
        if not drive:
            return SharePointDownloadResult(False, "no_drive", "Drive documenti non trovato")

        children_url = f"{GRAPH_ROOT}/drives/{drive['id']}/root:/{location.folder_path}:/children"
        children_resp = requests.get(children_url, headers=headers, timeout=30)
        children_resp.raise_for_status()
        files = children_resp.json().get("value", [])
        target = next((f for f in files if f.get("name") == target_filename), None)
        if not target:
            return SharePointDownloadResult(False, "not_found", f"File {target_filename} non trovato")

        download_url = target.get("@microsoft.graph.downloadUrl")
        if not download_url:
            return SharePointDownloadResult(False, "no_download_url", "URL download non disponibile")

        content = requests.get(download_url, timeout=60)
        content.raise_for_status()
        out = dest_dir / target_filename
        out.write_bytes(content.content)
        return SharePointDownloadResult(True, "ok", "Download completato", out)
    except requests.RequestException as exc:
        return SharePointDownloadResult(False, "network_error", f"Errore rete/permessi: {exc}")
    except Exception as exc:  # pragma: no cover
        return SharePointDownloadResult(False, "error", f"Errore SharePoint: {exc}")
