# File uploads

There are two ways to handle files. The model decides which one a field uses.

| | With the form | In the background |
|---|---|---|
| Model field | `UploadedFile`, `FileUpload` | `str`, `list[str]` |
| Needs | Nothing | An upload URL in your application |
| After a validation error | Choose the files again | Files stay |
| Progress, drag and drop | No | Yes |
| Requires JavaScript | No | Yes |

## With the form

`formidable.fields` has two types:

- `UploadedFile` is werkzeug's `FileStorage`, with `.stream`, `.filename`,
  `.content_type` and `.save(path)`. Large uploads are spooled to disk, so
  prefer it for anything sizeable.
- `FileUpload` is the content read into `bytes`, for small files.

```python
class Claim(BaseModel):
    belege: list[UploadedFile] = Field(default_factory=list, title="Belege")
```

With `{"ui:widget": "file", "ui:multiple": true}` in the UI schema, users can
choose several files. The form gets `enctype="multipart/form-data"`
automatically, and an empty file input counts as not submitted.

Browsers can't fill in file inputs, so if another field fails validation, users
are told to choose their files again. Set `max_content_length` on your request
class to limit the total size.

## In the background

With an upload URL, a file field holding references uploads each file as soon
as it's chosen, through the bundled [FilePond](https://pqina.nl/filepond/). The
form then submits only the ids, and the files come back after a validation
error.

```python
class Claim(BaseModel):
    belege: list[str] = Field(..., title="Belege")


FormRenderer(
    ui=parse_ui({"belege": {"ui:widget": "file", "ui:multiple": True,
                            "ui:accept": ["application/pdf", "image/png"]}}),
    upload_url="/upload",
    upload_options=i18n.UPLOAD_GERMAN,   # German labels, or any FilePond option
)
```

!!! warning "A reference field needs an upload URL"
    Without `upload_url`, a `list[str]` file field renders a plain file input,
    and fails validation on submit.

### The upload URL

Storing files is up to your application. The URL has to handle:

| Request | Purpose | Response |
|---|---|---|
| `POST` | Store the file, sent as a multipart part named like the field | The id, as plain text |
| `DELETE` | Remove a file; the id is the request body | Empty |
| `GET ?id=` | Give a file back | The file, with its name in `Content-Disposition` |

The CSRF token arrives in an `X-CSRF-Token` header. `Uploads` in `ex.py` is a
small example, which you can try at `/upload-demo`. It keeps its list of files
in memory, so don't use it as it is.

### What your endpoint must do

!!! danger "Ids are user input"
    Generate ids on the server, and check on submit that they belong to the
    user. Otherwise anyone can post someone else's id and claim that file.

- **Check size and type on the server.** The browser checks are a convenience
  and can be bypassed.
- **Remove abandoned files.** Forms that are never submitted leave their uploads
  behind, as does a file in a field that gets hidden again.

### Limits in the browser

`ui:accept` limits the type and `data-max-file-size` in `ui:attributes` the
size:

```json
{"attest": {"ui:widget": "file",
            "ui:accept": ["application/pdf"],
            "ui:attributes": {"data-max-file-size": "2MB"}}}
```

Use mime types in `ui:accept`, not file extensions.

### Page size

FilePond is part of the form rather than a separate file, which adds about
140 KB to each page that uses it. No third-party server is involved.
