from wired import ServiceRegistry
from formidable.renderers import (
    StringFieldRenderer,
    IntFieldRenderer,
    BoolFieldRenderer,
)
from formidable.renderers import StringToken, IntToken, BoolToken
from formidable.renderers import FormRenderer


# --- wired setup ---
def setup_container():
    registry = ServiceRegistry()

    # Register renderers with tokens
    registry.register_factory(lambda c: StringFieldRenderer(), StringToken)
    registry.register_factory(lambda c: IntFieldRenderer(), IntToken)
    registry.register_factory(lambda c: BoolFieldRenderer(), BoolToken)

    registry.register_factory(lambda c: FormRenderer(c), FormRenderer)
    return registry.create_container()
