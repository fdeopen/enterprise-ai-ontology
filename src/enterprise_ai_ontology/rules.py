"""Pure record validation and rule evaluation, with no side effects or rule eval()."""

from datetime import date, datetime
from operator import ge, gt, le, lt

from .models import Ontology, value_error
from .serialization import _json_tree


def _equal(left, right):
    """JSON equality: booleans are distinct from numbers, including in containers."""
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _equal(a, b) for a, b in zip(left, right, strict=True)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_equal(left[key], right[key]) for key in left)
    return left == right


def check_record(ontology: Ontology, entity_id: str, record: dict) -> dict:
    _json_tree(record)
    entity = next((e for e in ontology.entities if e.id == entity_id), None)
    if entity is None:
        raise ValueError(f"Unknown entity: {entity_id}")
    if not isinstance(record, dict):
        raise ValueError("Record must be an object")
    properties = {p.id: p for p in entity.properties}
    errors = [f"{key}: unknown property" for key in record if key not in properties]
    for prop in entity.properties:
        if prop.id not in record:
            if prop.required:
                errors.append(f"{prop.id}: required property is missing")
        else:
            error = value_error(prop, record[prop.id])
            if error:
                errors.append(f"{prop.id}: {error}")
    if errors:
        return {"entity": entity_id, "valid": False, "errors": errors, "rules": []}

    def matches(condition):
        key, op, expected = condition.property, condition.operator, condition.value
        # exists means present and non-null; absent is its inverse.
        present = key in record and record[key] is not None
        if op == "exists":
            return present
        if op == "absent":
            return not present
        if key not in record:
            return False
        actual = record[key]
        if op in ("eq", "ne"):
            return _equal(actual, expected) if op == "eq" else not _equal(actual, expected)
        if op in ("in", "not_in"):
            included = any(_equal(actual, option) for option in expected)
            return included if op == "in" else not included
        if actual is None:
            return False
        if op == "contains":
            return expected in actual
        kind = properties[key].type
        if kind == "date":
            actual, expected = date.fromisoformat(actual), date.fromisoformat(expected)
        elif kind == "datetime":
            actual = datetime.fromisoformat(actual)
            expected = datetime.fromisoformat(expected)
        return {"gt": gt, "gte": ge, "lt": lt, "lte": le}[op](actual, expected)

    results = []
    for rule in ontology.rules:
        if rule.entity != entity_id:
            continue
        decisions = [matches(condition) for condition in rule.conditions]
        passed = all(decisions) if rule.match == "all" else any(decisions)
        results.append(
            {
                "id": rule.id,
                "label": rule.label,
                "passed": passed,
                "severity": rule.severity,
                "message": rule.message,
                "conditions": decisions,
            }
        )
    return {
        "entity": entity_id,
        "valid": not any(not r["passed"] and r["severity"] == "error" for r in results),
        "errors": errors,
        "rules": results,
    }
