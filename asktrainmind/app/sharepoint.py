from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import unquote, urlparse

DEFAULT_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


def acquire_graph_token(client_id: str = DEFAULT_CLIENT_ID) -> str:
    """Public helper: acquire an MS Graph access token (reuses _acquire_token logic)."""
    return _acquire_token(client_id=client_id)


@dataclass
class SharePointLocation:
    tenant: str
    site_path: str
    folder_path: str


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
