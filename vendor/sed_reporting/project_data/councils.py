"""New Zealand's territorial authorities (data/territorial_authorities.json): the
councils a building consent is applied to.

The portal links the same list: the user picks the council when creating a
project, and the portal sends its `name` as `territorialAuthority`. The reports
print the name, and the PS1's B2 letter is addressed to the council's postal
address. Converted from TA_NZ.xlsx on 2026-10-10; maintained in the JSON file
from then on.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from sed_reporting.project_data._base import Strict

COUNCILS_FILE = Path(__file__).resolve().parents[1] / "data" / "territorial_authorities.json"

Text = Annotated[str, Field(min_length=1)]


class TerritorialAuthority(Strict):
    name: Text                 # "Wellington City Council": what the portal sends as territorialAuthority
    territory: Text            # "Wellington"
    authority: Literal["City Council", "District Council", "Council"]
    physical_address: Text
    postal_address: list[Text] = Field(min_length=1)   # lines, e.g. ["PO Box 2199", "Wellington 6140"]
    website: str = ""


class TerritorialAuthorities(Strict):
    territorial_authorities: list[TerritorialAuthority]

    @model_validator(mode="after")
    def _unique(self) -> TerritorialAuthorities:
        names = [c.name for c in self.territorial_authorities]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"council(s) listed more than once: {', '.join(dupes)}")
        return self

    def find(self, name: str) -> TerritorialAuthority | None:
        """The council with exactly this name (as picked in the portal)."""
        return next((c for c in self.territorial_authorities if c.name == name), None)

    def suggestions(self, name: str) -> list[str]:
        """Listed names that `name` probably means, for a "did you mean" hint.
        Matched on the place, not the whole name: every name ends in "Council",
        so "Tauranga District Council" would otherwise suggest Tararua. Ignores
        case, macrons and hyphens; gives every candidate when the place is
        ambiguous ("Hutt" -> Lower Hutt and Upper Hutt)."""
        place = _place(name)
        if not place:
            return []
        by_place = {_place(c.territory): c.name for c in self.territorial_authorities}
        if place in by_place:
            return [by_place[place]]
        words = set(place.split())
        overlap = [n for p, n in by_place.items() if set(p.split()) <= words or words <= set(p.split())]
        if overlap:
            return sorted(overlap)
        return [by_place[p] for p in difflib.get_close_matches(place, list(by_place), n=1, cutoff=0.8)]


def _place(name: str) -> str:
    """The place in a council's name, normalised: "Whangarei District Council",
    "Whangārei" -> "whangarei"; "Queenstown Lakes" -> "queenstown lakes"."""
    text = "".join(ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch))
    text = re.sub(r"[-\s]+", " ", text.lower()).strip()
    return re.sub(r"\s*\b(city|district|regional)?\s*council$", "", text).strip()


def load_councils(path: str | Path = COUNCILS_FILE) -> TerritorialAuthorities:
    """Read and validate the list of territorial authorities."""
    return TerritorialAuthorities.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
