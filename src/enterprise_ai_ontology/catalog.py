"""Built-in, fictional industry examples shipped inside the wheel."""

from importlib.resources import files

from .serialization import loads

EXAMPLES = ("ecommerce", "foreign_trade", "manufacturing", "medical_aesthetics", "recruitment")


def example_text(name: str, format: str = "yaml") -> str:
    if name not in EXAMPLES:
        raise ValueError(f"Unknown example: {name}. Choose from {', '.join(EXAMPLES)}")
    if format not in ("json", "yaml"):
        raise ValueError("Example format must be json or yaml")
    return (
        files("enterprise_ai_ontology")
        .joinpath("examples", name, f"ontology.{format}")
        .read_text(encoding="utf-8")
    )


def get_example(name: str):
    return loads(example_text(name))


def list_examples():
    result = []
    for name in EXAMPLES:
        ontology = get_example(name)
        result.append(
            {
                "id": name,
                "name": ontology.name,
                "industry": ontology.industry,
                "description": ontology.description,
                "counts": ontology.counts(),
            }
        )
    return result


def sample_records(name: str) -> str:
    if name not in EXAMPLES:
        raise ValueError(f"Unknown example: {name}")
    return (
        files("enterprise_ai_ontology")
        .joinpath("examples", name, "records.json")
        .read_text(encoding="utf-8")
    )
