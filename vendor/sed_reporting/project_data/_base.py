"""Base models: camelCase in JSON, snake_case in Python."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Strict(BaseModel):
    """Our own data: unknown keys rejected, so a misspelt input can't silently
    drop a value from a signed document."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid",
                              str_strip_whitespace=True)


class Portal(BaseModel):
    """The portal's data: unknown keys ignored, so the portal can add fields
    without breaking anything here."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore",
                              str_strip_whitespace=True)
