import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from enterprise_ai_ontology import Ontology, dumps, loads
from enterprise_ai_ontology.catalog import EXAMPLES, example_text, get_example, sample_records
from enterprise_ai_ontology.models import json_schema
from enterprise_ai_ontology.rules import check_record
from enterprise_ai_ontology.serialization import DefinitionError, parse

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("name", EXAMPLES)
def test_industry_roundtrip_schema_references_and_records(name):
    obj = get_example(name)
    assert obj == loads(example_text(name, "json"), "json")
    assert obj == loads(dumps(obj, "json"), "json") == loads(dumps(obj))
    Draft202012Validator(json_schema()).validate(obj.model_dump())
    assert obj.counts()["entities"] >= 5
    assert obj.counts()["relationships"] >= 5
    assert obj.counts()["actions"] >= 3
    assert obj.counts()["ai_scenarios"] >= 2
    records = json.loads(sample_records(name))
    assert check_record(obj, records["entity"], records["valid"])["valid"]
    result = check_record(obj, records["entity"], records["invalid"])
    assert not result["valid"]
    assert any(not rule["passed"] for rule in result["rules"])


def test_committed_schema_is_generated_from_models():
    assert json.loads((ROOT / "schema/ontology.schema.json").read_text()) == json_schema()
    Draft202012Validator.check_schema(json_schema())


@pytest.fixture
def definition():
    return get_example("ecommerce").model_dump()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema_version="2.0"),
        lambda d: d.update(unrecognized=True),
        lambda d: d["entities"].append(copy.deepcopy(d["entities"][0])),
        lambda d: d["entities"][0]["properties"].append(
            copy.deepcopy(d["entities"][0]["properties"][0])
        ),
        lambda d: d["entities"][0].update(primary_key="unknown"),
        lambda d: d["entities"][0]["properties"][0].update(nullable=True),
        lambda d: d["relationships"][0].update(source="Unknown"),
        lambda d: d["relationships"][0].update(cardinality="infinite"),
        lambda d: d["actions"][0].update(entity="Unknown"),
        lambda d: d["actions"][0].update(emits=["Unknown"]),
        lambda d: d["actions"][0].update(requires_rules=["ReturnRequested"]),
        lambda d: d["actions"][0].update(requires_rules=["OrderPaid", "OrderPaid"]),
        lambda d: d["rules"][0]["conditions"][0].update(property="Unknown"),
        lambda d: d["rules"][0]["conditions"][0].update(value="not-a-status"),
        lambda d: d["rules"][0]["conditions"][0].update(operator="exec"),
        lambda d: d["rules"][1]["conditions"][0].update(value="0"),
        lambda d: d["events"][0].update(entity="Unknown"),
        lambda d: d["ai_scenarios"][0].update(actions=["Unknown"]),
        lambda d: d["ai_scenarios"][0].update(entities=["Order", "Order"]),
        lambda d: d["entities"][0]["properties"][1].update(required="true"),
        lambda d: d["entities"][0]["properties"][2].update(enum_values=["a", "a"]),
    ],
)
def test_semantic_and_structural_errors_are_rejected(definition, mutation):
    mutation(definition)
    with pytest.raises(ValidationError):
        Ontology.model_validate(definition)


@pytest.mark.parametrize(
    ("text", "format"),
    [
        ('{"a":1,"a":2}', "json"),
        ("a: 1\na: 2", "yaml"),
        ("a: &value [1]\nb: *value", "yaml"),
        ('a: !!python/object/apply:os.system ["echo bad"]', "yaml"),
        ("1: value", "yaml"),
        ("a: .inf", "yaml"),
        ('{"a":NaN}', "json"),
        ('{"a":1e999}', "json"),
        ("a: !!set {b: null}", "yaml"),
        ("---\na: 1\n---\na: 2", "yaml"),
        ('{"a":9007199254740992}', "json"),
        ("[" * 50 + "0" + "]" * 50, "json"),
        ("[" * 50 + "0" + "]" * 50, "yaml"),
        ("x" * (2 * 1024 * 1024 + 1), "yaml"),
    ],
)
def test_unambiguous_bounded_nonexecutable_input(text, format):
    with pytest.raises(DefinitionError):
        parse(text, format)


def test_yaml_preserves_dates_and_yes_no_on_off():
    assert parse("date: 2026-01-01\non: yes\noff: no\nflag: true") == {
        "date": "2026-01-01",
        "on": "yes",
        "off": "no",
        "flag": True,
    }


def test_missing_optional_differs_from_explicit_null(definition):
    prop = definition["entities"][0]["properties"][-1]
    assert prop["id"] == "email" and not prop["required"]
    model = Ontology.model_validate(definition)
    assert check_record(model, "Customer", {"id": "1", "name": "Demo", "tier": "standard"})["valid"]
    assert not check_record(
        model, "Customer", {"id": "1", "name": "Demo", "tier": "standard", "email": None}
    )["valid"]
    prop["nullable"] = True
    assert check_record(
        Ontology.model_validate(definition),
        "Customer",
        {"id": "1", "name": "Demo", "tier": "standard", "email": None},
    )["valid"]
