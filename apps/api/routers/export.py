"""Export: the receipt bundle (S8). The file is not encrypted, so the response carries a warning (L13)."""

from __future__ import annotations

import tempfile

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from packages.vault import Vault

from ..pipeline import deal_of
from ..state import current_vault

router = APIRouter()
WARNING = "Exported files are not encrypted. Share them only with people you trust."


class BundleBody(BaseModel):
    include_media: bool = False


@router.post("/deals/{deal_id}/export/bundle")
def bundle(deal_id: str, body: BundleBody | None = None, vault: Vault = Depends(current_vault)) -> Response:
    deal_of(vault, deal_id)
    with tempfile.TemporaryDirectory() as folder:
        path = vault.export_bundle(deal_id, folder, include_media=bool(body and body.include_media))
        data, name = path.read_bytes(), path.name
    return Response(data, media_type="application/zip",
                    headers={"X-VeriDoc-Warning": WARNING, "Content-Disposition": f'attachment; filename="{name}"'})
