"""Shareable self-contained HTML using the same workbench as the local server."""

import json
from importlib.resources import files

from .models import Ontology
from .serialization import dumps


def asset(name: str) -> str:
    if name not in ("index.html", "app.js", "style.css"):
        raise ValueError("Unknown asset")
    return files("enterprise_ai_ontology").joinpath("static", name).read_text(encoding="utf-8")


def script_json(data) -> str:
    return (
        json.dumps(data, ensure_ascii=False, allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_html(ontology: Ontology, *, offline: bool = True, nonce: str = "") -> str:
    bootstrap = {
        "mode": "offline" if offline else "server",
        "ontology": ontology.model_dump(mode="json"),
        "yaml": dumps(ontology),
    }
    page = (
        asset("index.html")
        .replace("__NONCE__", nonce)
        .replace("__BOOTSTRAP__", script_json(bootstrap))
    )
    if offline:
        page = page.replace(
            '<link rel="stylesheet" href="/assets/style.css">',
            "<style>" + asset("style.css") + "</style>",
        )
        page = page.replace(
            '<script src="/assets/app.js" defer></script>',
            "",
        )
        page = page.replace("</body>", "<script>" + asset("app.js") + "</script></body>")
    return page
