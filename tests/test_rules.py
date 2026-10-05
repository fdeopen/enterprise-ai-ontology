import pytest
from pydantic import ValidationError

from enterprise_ai_ontology import Ontology
from enterprise_ai_ontology.rules import check_record


def model(kind="number", operator="gt", expected=0, **property_options):
    prop = dict(id="value", label="值", description="待校验字段", type=kind, **property_options)
    data = dict(
        id="Test",
        name="测试",
        industry="测试",
        description="规则测试",
        entities=[
            dict(
                id="Item",
                label="对象",
                description="测试对象",
                primary_key="id",
                properties=[
                    dict(id="id", label="标识", description="主键", type="string", required=True),
                    prop,
                ],
            )
        ],
        rules=[
            dict(
                id="Check",
                label="检查",
                description="测试规则",
                entity="Item",
                conditions=[dict(property="value", operator=operator, value=expected)],
                message="业务断言",
            )
        ],
    )
    return Ontology.model_validate(data)


@pytest.mark.parametrize(
    ("kind", "operator", "expected", "passes", "fails"),
    [
        ("number", "eq", 2, 2, 3),
        ("number", "ne", 2, 3, 2),
        ("number", "gt", 2, 3, 2),
        ("number", "gte", 2, 2, 1),
        ("number", "lt", 2, 1, 2),
        ("number", "lte", 2, 2, 3),
        ("number", "in", [1, 2], 2, 3),
        ("number", "not_in", [1, 2], 3, 2),
        ("string", "contains", "AI", "企业AI", "企业软件"),
        ("string_list", "contains", "AI", ["AI", "Python"], ["Python"]),
        ("number", "exists", None, 0, None),
        ("number", "absent", None, None, 0),
        ("date", "gte", "2026-01-01", "2026-01-02", "2025-12-31"),
        (
            "datetime",
            "gte",
            "2026-01-01T00:00:00Z",
            "2026-01-01T09:00:00+08:00",
            "2026-01-01T01:00:00+08:00",
        ),
    ],
)
def test_rule_operator_semantics(kind, operator, expected, passes, fails):
    ontology = model(kind, operator, expected, nullable=True)
    assert check_record(ontology, "Item", {"id": "1", "value": passes})["valid"]
    assert not check_record(ontology, "Item", {"id": "1", "value": fails})["valid"]


@pytest.mark.parametrize(
    "operator", ["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "exists"]
)
def test_missing_value_does_not_silently_pass_a_comparison(operator):
    kind = "string" if operator == "contains" else "number"
    expected = (
        "a"
        if kind == "string"
        else None
        if operator == "exists"
        else [1]
        if operator in ("in", "not_in")
        else 1
    )
    assert not check_record(model(kind, operator, expected), "Item", {"id": "1"})["valid"]


def test_any_combination_and_warning_does_not_block():
    data = model().model_dump()
    rule = data["rules"][0]
    rule["match"] = "any"
    rule["conditions"].append(dict(property="value", operator="eq", value=-1))
    assert check_record(Ontology.model_validate(data), "Item", {"id": "1", "value": -1})["valid"]
    rule["severity"] = "warning"
    result = check_record(Ontology.model_validate(data), "Item", {"id": "1", "value": -2})
    assert result["valid"] and not result["rules"][0]["passed"]


@pytest.mark.parametrize(
    ("kind", "operator", "value"),
    [
        ("string", "gt", "a"),
        ("number", "contains", "1"),
        ("number", "in", []),
        ("number", "in", "1"),
        ("number", "gt", True),
        ("integer", "gt", 1.1),
        ("number", "exists", 1),
        ("date", "eq", "2026-02-30"),
        ("date", "eq", "2026-W01-1"),
        ("datetime", "eq", "2026-01-01T00:00:00"),
    ],
)
def test_invalid_rule_literals(kind, operator, value):
    with pytest.raises(ValidationError):
        model(kind, operator, value)


def test_record_shape_blocks_rule_execution():
    obj = model("integer")
    for record in (
        {"id": "1", "value": True},
        {"id": "1", "value": 1.5},
        {"id": "1", "value": "4"},
        {"value": 3},
        {"id": "1", "value": 3, "unknown": 4},
    ):
        result = check_record(obj, "Item", record)
        assert not result["valid"] and result["errors"] and not result["rules"]
    with pytest.raises(ValueError):
        check_record(obj, "Unknown", {})
    with pytest.raises(ValueError):
        check_record(obj, "Item", [])


def test_json_equality_keeps_boolean_distinct_from_number():
    obj = model("json", "eq", {"items": [True]})
    assert check_record(obj, "Item", {"id": "1", "value": {"items": [True]}})["valid"]
    assert not check_record(obj, "Item", {"id": "1", "value": {"items": [1]}})["valid"]
