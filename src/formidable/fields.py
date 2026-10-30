"""Field types bridging HTML form uploads and Pydantic."""

import typing as t

from pydantic import BeforeValidator, GetPydanticSchema
from pydantic_core import core_schema
from werkzeug.datastructures import FileStorage


def read_upload(value: t.Any) -> t.Any:
    """Read a werkzeug FileStorage into bytes; pass anything else through."""
    if isinstance(value, FileStorage):
        return value.read()
    return value


#: The whole upload eagerly read into memory. Handy for small blobs
#: headed for a database column; filename and content type are lost.
FileUpload = t.Annotated[bytes, BeforeValidator(read_upload)]

#: The werkzeug FileStorage itself: a file-like `.stream` (in memory for
#: small uploads, spooled to a temp file for large ones) plus `.filename`,
#: `.content_type` and `.save(path)`. Prefer this for anything sizeable.
UploadedFile = t.Annotated[
    FileStorage,
    GetPydanticSchema(
        lambda tp, handler: core_schema.is_instance_schema(FileStorage)),
]
