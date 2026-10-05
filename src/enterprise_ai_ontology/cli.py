import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .catalog import EXAMPLES, example_text, list_examples, sample_records
from .models import json_schema
from .render import render_html
from .rules import check_record
from .serialization import dumps, load, parse, read_text, write_new
from .server import error_message, serve


def parser():
    cli = argparse.ArgumentParser(
        prog="enterprise-ontology",
        description="Validate, explore and share lightweight enterprise ontologies.",
    )
    cli.add_argument("--version", action="version", version=__version__)
    sub = cli.add_subparsers(dest="command", required=True)
    sub.add_parser("examples", help="List the five built-in industry examples")
    init = sub.add_parser("init", help="Create an editable industry example in a NEW directory")
    init.add_argument("example", choices=EXAMPLES)
    init.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate", help="Validate structure and semantic references")
    validate.add_argument("file", type=Path)
    validate.add_argument("--json", action="store_true")
    convert = sub.add_parser("convert", help="Convert JSON/YAML without overwriting")
    convert.add_argument("file", type=Path)
    convert.add_argument("--output", type=Path, required=True)
    schema = sub.add_parser("schema", help="Write JSON Schema for DSL 1.0")
    schema.add_argument("--output", type=Path)
    render = sub.add_parser("render", help="Render a self-contained offline HTML workbench")
    render.add_argument("file", type=Path)
    render.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("check", help="Check an entity record and its business rules")
    check.add_argument("file", type=Path)
    check.add_argument("--entity", required=True)
    check.add_argument("--record", type=Path, required=True)
    web = sub.add_parser("serve", help="Start the local visual workbench")
    web.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1")
    web.add_argument("--port", type=int, default=8878)
    return cli


def emit(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))


def initialize(name: str, target: Path):
    # mkdir is exclusive, including for existing empty directories and symlinks.
    target.mkdir(parents=True, exist_ok=False)
    created = []

    def create(relative, content):
        path = target / relative
        write_new(path, content)
        created.append(path)

    try:
        records = parse(sample_records(name), "json")
        for format in ("yaml", "json"):
            create(f"ontology.{format}", example_text(name, format))
        for kind in ("valid", "invalid"):
            create(
                f"record.{kind}.json",
                json.dumps(records[kind], ensure_ascii=False, indent=2) + "\n",
            )
        create(
            "README.md",
            f"# {name}\n\n虚构行业示例，JSON/YAML 为同一模型的两种表示；修改时选择一份为主文件。\n\n```bash\nenterprise-ontology validate ontology.yaml\nenterprise-ontology check ontology.yaml --entity {records['entity']} --record record.valid.json\nenterprise-ontology check ontology.yaml --entity {records['entity']} --record record.invalid.json\nenterprise-ontology render ontology.yaml --output ontology.html\n```\n\ninvalid 记录应返回退出码 2；Action / Event 仅为声明。\n",
        )
    except Exception:
        # Only remove our known files; do not recursively remove concurrent user work.
        for path in reversed(created):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        try:
            target.rmdir()
        except OSError:
            pass
        raise


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "examples":
            emit(list_examples())
        elif args.command == "init":
            initialize(args.example, args.output)
            print(f"Created {args.output.resolve()}")
        elif args.command == "schema":
            content = json.dumps(json_schema(), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                write_new(args.output, content)
                print(args.output.resolve())
            else:
                print(content, end="")
        elif args.command == "serve":
            serve(args.host, args.port)
        else:
            ontology = load(args.file)
            if args.command == "validate":
                data = {"valid": True, "id": ontology.id, "counts": ontology.counts()}
                emit(data) if args.json else print(
                    f"Valid: {ontology.name} · {ontology.version}\n{ontology.counts()}"
                )
            elif args.command == "convert":
                write_new(args.output, dumps(ontology, args.output.suffix.lstrip(".").lower()))
                print(args.output.resolve())
            elif args.command == "render":
                write_new(args.output, render_html(ontology))
                print(args.output.resolve())
            elif args.command == "check":
                result = check_record(ontology, args.entity, parse(read_text(args.record), "json"))
                emit(result)
                return 0 if result["valid"] else 2
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        if args.command == "validate" and args.json:
            emit({"valid": False, "error": error_message(exc)})
        else:
            print(f"Error: {error_message(exc)}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
