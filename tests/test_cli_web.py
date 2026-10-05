import json
import subprocess
import sys
import threading
from http.client import HTTPConnection

import pytest

from enterprise_ai_ontology.catalog import get_example
from enterprise_ai_ontology.cli import initialize
from enterprise_ai_ontology.render import render_html
from enterprise_ai_ontology.server import make_server


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "enterprise_ai_ontology", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_cli_complete_workflow_and_exit_codes(tmp_path):
    target = tmp_path / "project"
    assert cli("init", "ecommerce", "--output", target).returncode == 0
    ontology = target / "ontology.yaml"
    assert json.loads(cli("validate", ontology, "--json").stdout)["valid"]
    valid = cli("check", ontology, "--entity", "Order", "--record", target / "record.valid.json")
    invalid = cli(
        "check", ontology, "--entity", "Order", "--record", target / "record.invalid.json"
    )
    assert valid.returncode == 0 and json.loads(valid.stdout)["valid"]
    assert invalid.returncode == 2 and not json.loads(invalid.stdout)["valid"]
    converted = tmp_path / "converted.json"
    assert cli("convert", ontology, "--output", converted).returncode == 0
    assert json.loads(converted.read_text())["id"] == "ecommerce"
    original = converted.read_bytes()
    assert cli("convert", ontology, "--output", converted).returncode == 1
    assert converted.read_bytes() == original
    assert cli("init", "recruitment", "--output", target).returncode == 1
    output = tmp_path / "report.html"
    assert cli("render", ontology, "--output", output).returncode == 0
    assert output.exists()
    assert len(json.loads(cli("examples").stdout)) == 5
    assert json.loads(cli("schema").stdout)["$schema"].endswith("2020-12/schema")
    assert cli("--version").stdout.strip() == "0.1.0"


def test_cli_failure_is_machine_readable(tmp_path):
    invalid = tmp_path / "bad.yaml"
    invalid.write_text("unknown: true")
    result = cli("validate", invalid, "--json")
    assert result.returncode == 1 and not json.loads(result.stdout)["valid"]
    assert "Traceback" not in result.stderr


def test_init_refuses_existing_and_symlink(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileExistsError):
        initialize("ecommerce", empty)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "does-not-exist")
    with pytest.raises(FileExistsError):
        initialize("ecommerce", link)


def test_offline_html_is_self_contained_and_escapes_script_injection():
    obj = get_example("ecommerce").model_copy(deep=True)
    obj.description = '</script><script>alert("xss")</script> & <img src=x> __NONCE__'
    page = render_html(obj)
    assert obj.description not in page
    assert "\\u003c/script\\u003e" in page
    assert "__NONCE__" in page  # User content must not be interpreted as template syntax.
    assert "<script src=" not in page and 'href="/assets/' not in page
    assert page.index("/* No remote libraries") > page.index("<body>")


@pytest.fixture
def server():
    http = make_server(port=0)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield http.server_address[1]
    http.shutdown()
    http.server_close()
    thread.join(timeout=2)


def request(port, path, data=None, headers=None, raw=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    payload = raw if raw is not None else json.dumps(data) if data is not None else None
    conn.request(
        "POST" if payload is not None else "GET",
        path,
        body=payload,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    result = conn.getresponse()
    body = result.read().decode()
    status = result.status
    content_type = result.getheader("Content-Type")
    response_headers = dict(result.getheaders())
    conn.close()
    return (
        status,
        json.loads(body) if content_type.startswith("application/json") else body,
        response_headers,
    )


def test_workbench_load_validate_render_check(server):
    status, page, headers = request(server, "/")
    assert status == 200 and "ONTOLOGY_BOOTSTRAP" in page
    assert "frame-ancestors" in headers["Content-Security-Policy"]
    assert request(server, "/assets/app.js")[0] == 200
    examples = request(server, "/api/examples")[1]
    assert len(examples) == 5
    body = request(server, "/api/examples/recruitment")[1]
    payload = dict(text=body["yaml"], format="yaml")
    assert request(server, "/api/validate", payload)[1]["counts"]["entities"] == 6
    status, html, _ = request(server, "/api/render", payload)
    assert status == 200 and "<script src=" not in html
    status, result, _ = request(
        server,
        "/api/check",
        {
            **payload,
            "entity": "Application",
            "record_text": '{"id":"a","stage":"screening","consent_confirmed":true,"reviewed":true}',
        },
    )
    assert status == 200 and result["valid"]
    status, result, _ = request(
        server,
        "/api/check",
        {**payload, "entity": "Application", "record_text": '{"id":"a","id":"b"}'},
    )
    assert status == 400 and "Duplicate key" in result["error"]
    assert request(server, "/api/health")[1]["status"] == "ok"
    assert request(server, "/api/schema")[0] == 200


@pytest.mark.parametrize(
    ("path", "data", "headers", "expected"),
    [
        ("/api/validate", {"text": "invalid"}, {}, 400),
        ("/api/validate", {"text": 123}, {}, 400),
        ("/api/validate", {"text": "x"}, {"Content-Type": "text/plain"}, 415),
        ("/api/validate", {"text": "x"}, {"Origin": "https://untrusted.example"}, 403),
        ("/", None, {"Host": "untrusted.example"}, 403),
        ("/api/examples/../../etc/passwd", None, {}, 404),
        ("/../../etc/passwd", None, {}, 404),
    ],
)
def test_workbench_rejects_invalid_or_external_requests(server, path, data, headers, expected):
    assert request(server, path, data, headers)[0] == expected


def test_server_does_not_expose_network_without_auth():
    with pytest.raises(ValueError):
        make_server("0.0.0.0", 0)
