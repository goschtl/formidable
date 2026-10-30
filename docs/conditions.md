# Conditional fields

Fields can appear depending on other answers, without jQuery or any other
dependency:

```json
{
  "attest": {
    "ui:conditions": [
      {"field": "hat_attest", "operator": "equals", "value": "ja"}
    ],
    "ui:condition_logic": "or"
  }
}
```

The script is only included when a form uses conditions. It clears and disables
what is hidden, so browsers don't submit it, and it handles chains of
conditions, nested fields and list rows, where a condition looks at its own row
first.

## Operators

`equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `ends_with`,
`greater_than`, `less_than`, `greater_equal`, `less_equal`, `empty`,
`not_empty`, `in`, `not_in`.

## Requirements still belong in the model

The browser only decides what is visible. A field that is required only under
a condition has to be optional in the model, with a validator enforcing the
rule:

```python
class Claim(BaseModel):
    hat_attest: t.Literal["ja", "nein"]
    attest_datum: datetime.date | None = None

    @model_validator(mode="after")
    def attest_needs_a_date(self):
        if self.hat_attest == "ja" and not self.attest_datum:
            raise PydanticCustomError(
                "missing", "Pflichtfeld.", {"field": "attest_datum"})
        return self
```

See `/rueckfrage` in `ex.py` for a real form.

## Further attributes

These are set through `ui:attributes`, or directly in your own templates:

| Attribute | Purpose |
|---|---|
| `data-conditions` | The conditions as ready-made JSON, instead of `ui:conditions` |
| `data-condition-logic` | `or` or `and` |
| `data-conditional-options` | Limits a field's options depending on another answer |
| `data-not-required` | Keeps the field optional when it's shown |

## From JavaScript

The script dispatches on `change` events by itself. After changing values from
your own code, call `window.FormidableConditions.evaluate()`.
