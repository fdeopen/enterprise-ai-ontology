"""Bounded, JSON-compatible YAML/JSON IO; duplicate keys and aliases are rejected."""

import json
import math
import re
from pathlib import Path

import yaml
from yaml.events import AliasEvent

from .models import Ontology

MAX_BYTES = 2 * 1024 * 1024
MAX_NODES = 50000
MAX_DEPTH = 40


class DefinitionError(ValueError):
    pass


class DefinitionLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self.depth = 0
        self.nodes = 0

    def compose_node(self, parent, index):
        if self.check_event(AliasEvent):
            raise DefinitionError(
                "YAML aliases are not supported; expand reusable definitions explicitly"
            )
        self.depth += 1
        self.nodes += 1
        if self.depth > MAX_DEPTH or self.nodes > MAX_NODES:
            raise DefinitionError("Definition exceeds depth/node limit")
        try:
            return super().compose_node(parent, index)
        finally:
            self.depth -= 1

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise DefinitionError("Mapping keys must be strings")
            if key in result:
                raise DefinitionError(f"Duplicate key: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


# Preserve yes/no/on/off and dates as strings. This is a documented YAML subset,
# not a claim to implement the entire YAML 1.2 specification.
DefinitionLoader.yaml_implicit_resolvers = {
    key: [
        (tag, pattern)
        for tag, pattern in entries
        if tag not in ("tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp")
    ]
    for key, entries in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
DefinitionLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf")
)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DefinitionError(f"Duplicate key: {key}")
        result[key] = value
    return result


def _json_tree(value, depth=0, budget=None):
    if budget is None:
        budget = [MAX_NODES]
    budget[0] -= 1
    if depth > MAX_DEPTH or budget[0] < 0:
        raise DefinitionError("Definition exceeds depth/node limit")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise DefinitionError("Mapping keys must be strings")
            _json_tree(child, depth + 1, budget)
    elif isinstance(value, list):
        for child in value:
            _json_tree(child, depth + 1, budget)
    elif type(value) not in (str, int, float, bool, type(None)):
        raise DefinitionError("Only JSON-compatible YAML values are supported")
    elif isinstance(value, float) and not math.isfinite(value):
        raise DefinitionError("Non-finite numbers are not supported")
    elif type(value) is int and abs(value) > 2**53 - 1:
        raise DefinitionError(
            "Integer exceeds JavaScript-safe range; encode large identifiers as strings"
        )


def parse(text: str, format: str = "yaml"):
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise DefinitionError("Input exceeds 2 MiB limit")
    try:
        if format == "json":
            value = json.loads(text, object_pairs_hook=_pairs)
        elif format in ("yaml", "yml"):
            value = yaml.load(text, Loader=DefinitionLoader)
        else:
            raise DefinitionError(f"Unsupported format: {format}")
        _json_tree(value)
        return value
    except (yaml.YAMLError, json.JSONDecodeError, RecursionError) as exc:
        raise DefinitionError(f"Invalid {format}: {exc}") from exc


def loads(text: str, format: str = "yaml") -> Ontology:
    return Ontology.model_validate(parse(text, format))


def read_text(path: str | Path) -> str:
    with Path(path).open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise DefinitionError("Input exceeds 2 MiB limit")
    return content.decode("utf-8-sig")


def load(path: str | Path) -> Ontology:
    return loads(read_text(path), Path(path).suffix.lstrip(".").lower())


def dumps(ontology: Ontology, format: str = "yaml") -> str:
    data = ontology.model_dump(mode="json")
    if format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if format in ("yaml", "yml"):
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    raise DefinitionError(f"Unsupported format: {format}")


def write_new(path: str | Path, content: str):
    """Exclusive creation prevents accidental overwrite; choose another output path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content)
