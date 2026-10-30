# Validation and errors

Pydantic is the only validator. Forms render with `novalidate`, so the browser
never blocks a submit; `FormRenderer(novalidate=False)` turns browser
validation back on.

Before validation, HTML form quirks are normalized:

- Unchecked checkboxes become `False`.
- Empty submissions are dropped. Optional fields fall back to their defaults,
  and required ones fail as *missing* rather than as an unparsable empty
  string.

## Where errors appear

Errors are routed by dot path to the exact widget, as a message plus an
`invalid` class on the input. Errors from a model-level validator appear at
the top of the form, unless they name a field:

```python
@model_validator(mode="after")
def nickname_required_when_agreeing(self):
    if self.agree and not self.nickname:
        raise PydanticCustomError(
            "nickname_required",
            "When agreeing to the terms, a nickname is required.",
            {"field": "nickname"})   # appears at the nickname widget
    return self
```

Several errors at once work too. Raise them with
`ValidationError.from_exception_data`, each with its own `field`. See
`ex_forms/LD_000_0V1100/model.py` in the repository.

Regular expressions with lookaround need Python's engine:

```python
model_config = ConfigDict(regex_engine="python-re")
```
