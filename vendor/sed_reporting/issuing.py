"""What issuing a signed report needs, shared by the PS1 and the SIR: fetch an
image (a signature, a logo, a photo) and check it really is one, and lock the
issued PDF.

Locking sets the PDF's permissions so it can be printed and copied from but not
edited (pypdf's RC4-128 encryption with an empty open password and a random,
discarded owner password). That stops ordinary editing in PDF software. It is
not a cryptographic digital signature, so it does not prove the file unaltered.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable

from pypdf import PdfWriter
from pypdf.constants import UserAccessPermissions as Allow

PNG, JPEG = b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff"


class ImageError(Exception):
    """An image could not be fetched, or is not a PNG or JPEG."""


def is_image(data: bytes) -> bool:
    return data[:8] == PNG or data[:3] == JPEG


def fetch_image(fetch: Callable[[str], bytes], url: str, what: str) -> bytes:
    """Fetch a PNG or JPEG; `what` names it in the error ("the reviewing engineer's signature")."""
    try:
        data = fetch(url)
    except Exception as e:  # noqa: BLE001 - any fetch failure is reported, saying why
        raise ImageError(f"could not fetch {what} ({type(e).__name__}: {e})") from e
    if not is_image(data):
        raise ImageError(f"{what} is not a PNG or JPEG image")
    return data


def lock(writer: PdfWriter) -> None:
    """Allow printing and copying; not editing."""
    writer.encrypt(user_password="", owner_password=secrets.token_urlsafe(32), algorithm="RC4-128",
                   permissions_flag=Allow.PRINT | Allow.PRINT_TO_REPRESENTATION | Allow.EXTRACT
                   | Allow.EXTRACT_TEXT_AND_GRAPHICS)
