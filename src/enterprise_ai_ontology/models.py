"""Versioned DSL models and cross-reference validation. No executable expressions."""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
Text = Annotated[str, Field(min_length=1, max_length=10000)]
PropertyType = Literal[
    "string", "integer", "number", "boolean", "date", "datetime", "enum", "string_list", "json"
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Named(StrictModel):
    id: Identifier
    label: Annotated[str, Field(min_length=1, max_length=100)]
    description: Text


class Property(Named):
    type: PropertyType
    required: bool = False
    nullable: bool = False
    enum_values: list[str] = Field(default_factory=list, max_length=100)
    unit: str | None = None
    sensitive: bool = False

    @model_validator(mode="after")
    def valid_enum(self):
        if self.type == "enum":
            if not self.enum_values or len(set(self.enum_values)) != len(self.enum_values):
                raise ValueError(f"{self.id}: enum_values must be non-empty and unique")
        elif self.enum_values:
            raise ValueError(f"{self.id}: enum_values only applies to enum")
        return self


def unique(items: list, location: str):
    ids = [item.id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{location}: duplicate IDs")


class Entity(Named):
    properties: list[Property] = Field(min_length=1, max_length=100)
    primary_key: Identifier

    @model_validator(mode="after")
    def valid_properties(self):
        unique(self.properties, f"entity {self.id}.properties")
        prop = next((p for p in self.properties if p.id == self.primary_key), None)
        if (
            prop is None
            or not prop.required
            or prop.nullable
            or prop.type not in ("string", "integer")
        ):
            raise ValueError(
                f"{self.id}: primary_key must reference a required, non-null string/integer property"
            )
        return self


class Relationship(Named):
    source: Identifier
    target: Identifier
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]


class Predicate(StrictModel):
    property: Identifier
    operator: Literal[
        "eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "exists", "absent"
    ]
    value: JsonValue = None


class Rule(Named):
    entity: Identifier
    conditions: list[Predicate] = Field(min_length=1, max_length=30)
    match: Literal["all", "any"] = "all"
    severity: Literal["error", "warning"] = "error"
    message: Text


class Event(Named):
    entity: Identifier
    payload: list[Property] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_payload(self):
        unique(self.payload, f"event {self.id}.payload")
        return self


class Action(Named):
    entity: Identifier
    parameters: list[Property] = Field(default_factory=list, max_length=100)
    requires_rules: list[Identifier] = Field(default_factory=list, max_length=100)
    emits: list[Identifier] = Field(default_factory=list, max_length=100)
    human_approval: bool = False

    @model_validator(mode="after")
    def unique_parameters(self):
        unique(self.parameters, f"action {self.id}.parameters")
        return self


class AIScenario(Named):
    task: Text
    entities: list[Identifier] = Field(min_length=1, max_length=100)
    relationships: list[Identifier] = Field(default_factory=list, max_length=200)
    actions: list[Identifier] = Field(default_factory=list, max_length=100)
    rules: list[Identifier] = Field(default_factory=list, max_length=100)
    events: list[Identifier] = Field(default_factory=list, max_length=100)
    inputs: list[Text] = Field(min_length=1, max_length=30)
    outputs: list[Text] = Field(min_length=1, max_length=30)
    success_metrics: list[Text] = Field(min_length=1, max_length=30)
    human_oversight: Text


def value_error(prop: Property, value: JsonValue) -> str | None:
    """Check record and rule literal types identically, without coercion."""
    if value is None:
        return None if prop.nullable else "null is not allowed"
    kind = prop.type
    if kind == "integer" and type(value) is int:
        return None
    if kind == "number" and (type(value) is int or (type(value) is float and math.isfinite(value))):
        return None
    if kind == "boolean" and type(value) is bool:
        return None
    if kind == "string" and isinstance(value, str):
        return None
    if kind == "enum" and isinstance(value, str) and value in prop.enum_values:
        return None
    if kind == "string_list" and isinstance(value, list) and all(isinstance(v, str) for v in value):
        return None
    if kind in ("date", "datetime") and isinstance(value, str):
        try:
            if kind == "date":
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError("use YYYY-MM-DD")
                date.fromisoformat(value)
            else:
                if "T" not in value:
                    raise ValueError("use ISO 8601 with T and timezone")
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is None:
                    raise ValueError("timezone required")
            return None
        except ValueError:
            return f"invalid {kind}; use ISO 8601" + (
                " with timezone" if kind == "datetime" else ""
            )
    if kind == "json":
        return None
    return f"expected {kind}" + (f" in {prop.enum_values}" if kind == "enum" else "")


def validate_predicate(predicate: Predicate, prop: Property):
    op, value = predicate.operator, predicate.value
    if op in ("exists", "absent"):
        if value is not None:
            raise ValueError(f"{op} does not accept a value")
        return
    if op in ("gt", "gte", "lt", "lte"):
        if prop.type not in ("integer", "number", "date", "datetime") or value is None:
            raise ValueError(f"{op} requires a numeric/date/datetime property and non-null value")
    if op == "contains":
        if prop.type not in ("string", "string_list") or not isinstance(value, str):
            raise ValueError("contains requires string/string_list property and a string value")
        return
    values = value if op in ("in", "not_in") else [value]
    if not isinstance(values, list) or not values:
        raise ValueError(f"{op} requires a non-empty list")
    for item in values:
        error = value_error(prop, item)
        if error:
            raise ValueError(f"{prop.id}: {error}")


class Ontology(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    id: Identifier
    name: Text
    version: Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")] = "0.1.0"
    industry: Text
    description: Text
    entities: list[Entity] = Field(min_length=1, max_length=100)
    relationships: list[Relationship] = Field(default_factory=list, max_length=200)
    actions: list[Action] = Field(default_factory=list, max_length=100)
    rules: list[Rule] = Field(default_factory=list, max_length=100)
    events: list[Event] = Field(default_factory=list, max_length=100)
    ai_scenarios: list[AIScenario] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def semantic_validation(self):
        groups = {
            name: getattr(self, name)
            for name in ("entities", "relationships", "actions", "rules", "events", "ai_scenarios")
        }
        for name, items in groups.items():
            unique(items, name)
        indexes = {name: {item.id: item for item in items} for name, items in groups.items()}

        def ref(group, key, location):
            if key not in indexes[group]:
                raise ValueError(f"{location}: unknown {group} reference '{key}'")
            return indexes[group][key]

        def refs(group, keys, location):
            if len(set(keys)) != len(keys):
                raise ValueError(f"{location}: duplicate references")
            return [ref(group, key, location) for key in keys]

        for relation in self.relationships:
            ref("entities", relation.source, f"relationship {relation.id}.source")
            ref("entities", relation.target, f"relationship {relation.id}.target")
        for rule in self.rules:
            entity = ref("entities", rule.entity, f"rule {rule.id}.entity")
            properties = {p.id: p for p in entity.properties}
            for condition in rule.conditions:
                if condition.property not in properties:
                    raise ValueError(
                        f"rule {rule.id}: unknown property {rule.entity}.{condition.property}"
                    )
                try:
                    validate_predicate(condition, properties[condition.property])
                except ValueError as exc:
                    raise ValueError(f"rule {rule.id}: {exc}") from exc
        for event in self.events:
            ref("entities", event.entity, f"event {event.id}.entity")
        for action in self.actions:
            ref("entities", action.entity, f"action {action.id}.entity")
            for rule in refs("rules", action.requires_rules, f"action {action.id}.requires_rules"):
                if rule.entity != action.entity:
                    raise ValueError(
                        f"action {action.id}: precondition {rule.id} must belong to entity {action.entity}"
                    )
            refs("events", action.emits, f"action {action.id}.emits")
        for scenario in self.ai_scenarios:
            for group in ("entities", "relationships", "actions", "rules", "events"):
                refs(group, getattr(scenario, group), f"ai_scenario {scenario.id}.{group}")
        return self

    def counts(self) -> dict[str, int]:
        return {
            "entities": len(self.entities),
            "properties": sum(len(e.properties) for e in self.entities),
            **{
                name: len(getattr(self, name))
                for name in ("relationships", "actions", "rules", "events", "ai_scenarios")
            },
        }


def json_schema() -> dict:
    schema = Ontology.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "Enterprise AI Ontology DSL 1.0"
    schema["description"] = (
        "Structural validation only. Use enterprise-ontology validate for cross-reference and rule type checks."
    )
    return schema
