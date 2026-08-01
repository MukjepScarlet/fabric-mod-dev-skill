#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def priority(path: Path) -> int:
    path_string = str(path)
    if "minecraft-merged-" in path_string:
        return 0
    if "minecraft-client-" in path_string:
        return 1
    if "minecraft-server-" in path_string:
        return 2
    return 9


def minecraft_cache_root(project_root: str) -> Path:
    return Path(project_root).resolve() / ".gradle" / "loom-cache" / "minecraftMaven" / "net" / "minecraft"


def find_jars(mc_root: Path, version: str | None) -> list[Path]:
    jars = []
    for path in mc_root.rglob("*.jar"):
        path_string = str(path)
        if "minecraft-merged-" not in path_string and "minecraft-client-" not in path_string and "minecraft-server-" not in path_string:
            continue
        if version and version not in path.parts:
            continue
        jars.append(path)
    return sorted(jars, key=lambda path: (priority(path), str(path)))


def find_source_jars(mc_root: Path, version: str | None) -> list[Path]:
    return [path for path in find_jars(mc_root, version) if path.name.endswith("-sources.jar")]


def emit_paths(paths: list[Path], as_json: bool) -> None:
    if as_json:
        print(json.dumps([str(path) for path in paths], indent=2))
    else:
        for path in paths:
            print(path)


def source_entry(class_name: str) -> str:
    if class_name.endswith(".java"):
        return class_name.replace("\\", "/")
    return f"{class_name.replace('.', '/')}.java"


def require_source_jars(mc_root: Path, version: str | None) -> list[Path] | None:
    source_jars = find_source_jars(mc_root, version)
    if source_jars:
        return source_jars
    scope = f" for version '{version}'" if version else ""
    print(f"No Minecraft sources jars found{scope} under {mc_root}.", file=sys.stderr)
    print("Run the project's genSources task to generate source jars, then retry.", file=sys.stderr)
    return None


def add_output_arguments(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    default = argparse.SUPPRESS if suppress_defaults else 0
    parser.add_argument("--limit", type=int, default=default, help="Max results to print. 0 means unlimited.")
    default = argparse.SUPPRESS if suppress_defaults else False
    parser.add_argument("--json", action="store_true", default=default, help="Emit structured JSON where supported.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Find and inspect Minecraft jars from Fabric Loom cache.")
    parser.add_argument("--project-root", default=".", help="Path to project root.")
    parser.add_argument("--version", help="Filter by version segment in path, such as 1.21.11 or 26.1-snapshot-10.")
    add_output_arguments(parser)
    subparsers = parser.add_subparsers(dest="command")
    find_parser = subparsers.add_parser("find", help="List Minecraft jars (the default action).")
    add_output_arguments(find_parser, suppress_defaults=True)

    read_parser = subparsers.add_parser("read", help="Print a Java source entry from a sources jar.")
    add_output_arguments(read_parser, suppress_defaults=True)
    read_parser.add_argument("--class", dest="class_name", required=True, help="Fully qualified class name or .java entry path.")

    search_parser = subparsers.add_parser("search", help="List Java source entries whose path contains a query.")
    add_output_arguments(search_parser, suppress_defaults=True)
    search_parser.add_argument("--query", required=True, help="Case-insensitive substring to find in source entry paths.")

    grep_parser = subparsers.add_parser("grep", help="Search Java source contents using a Python regular expression.")
    add_output_arguments(grep_parser, suppress_defaults=True)
    grep_parser.add_argument("--pattern", required=True, help="Regular expression to find in source files.")
    grep_parser.add_argument("--ignore-case", action="store_true", help="Match the pattern case-insensitively.")
    args = parser.parse_args()

    mc_root = minecraft_cache_root(args.project_root)
    if not mc_root.exists():
        print(f"Minecraft Loom cache root not found: {mc_root}", file=sys.stderr)
        return 2

    if args.command in (None, "find"):
        jars = find_jars(mc_root, args.version)
        if args.limit > 0:
            jars = jars[: args.limit]
        if not jars:
            scope = f" for version '{args.version}'" if args.version else ""
            print(f"No Minecraft jars found{scope} under {mc_root}")
            return 1
        emit_paths(jars, args.json)
        return 0

    source_jars = require_source_jars(mc_root, args.version)
    if source_jars is None:
        return 1

    if args.command == "read":
        entry = source_entry(args.class_name)
        for jar in source_jars:
            try:
                with ZipFile(jar) as archive:
                    if entry in archive.namelist():
                        print(archive.read(entry).decode("utf-8"), end="")
                        return 0
            except BadZipFile:
                continue
        print(f"Source entry not found: {entry}", file=sys.stderr)
        return 1

    if args.command == "search":
        query = args.query.casefold()
        results = []
        for jar in source_jars:
            with ZipFile(jar) as archive:
                for entry in archive.namelist():
                    if entry.endswith(".java") and query in entry.casefold():
                        results.append(f"{jar}!/{entry}")
        if args.limit > 0:
            results = results[: args.limit]
        if not results:
            print(f"No Java source entries matched '{args.query}'.")
            return 1
        print(json.dumps(results, indent=2) if args.json else "\n".join(results))
        return 0

    try:
        pattern = re.compile(args.pattern, re.IGNORECASE if args.ignore_case else 0)
    except re.error as error:
        print(f"Invalid regular expression: {error}", file=sys.stderr)
        return 2

    matches = []
    for jar in source_jars:
        with ZipFile(jar) as archive:
            for entry in archive.namelist():
                if not entry.endswith(".java"):
                    continue
                for line_number, line in enumerate(archive.read(entry).decode("utf-8").splitlines(), start=1):
                    if pattern.search(line):
                        matches.append({"jar": str(jar), "entry": entry, "line": line_number, "text": line})
                        if args.limit > 0 and len(matches) >= args.limit:
                            break
                if args.limit > 0 and len(matches) >= args.limit:
                    break
        if args.limit > 0 and len(matches) >= args.limit:
            break
    if not matches:
        print(f"No Java source lines matched '{args.pattern}'.")
        return 1
    if args.json:
        print(json.dumps(matches, indent=2))
    else:
        for match in matches:
            print(f"{match['jar']}!/{match['entry']}:{match['line']}:{match['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
