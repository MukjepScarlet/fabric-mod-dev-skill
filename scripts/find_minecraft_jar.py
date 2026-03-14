#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def priority(path: Path) -> int:
    s = str(path)
    if "minecraft-merged-" in s:
        return 0
    if "minecraft-client-" in s:
        return 1
    if "minecraft-server-" in s:
        return 2
    return 9


def main() -> int:
    parser = argparse.ArgumentParser(description="Find Minecraft jars from Fabric Loom cache.")
    parser.add_argument("--project-root", default=".", help="Path to project root.")
    parser.add_argument("--version", help="Filter by version segment in path, such as 1.21.11 or 26.1-snapshot-10.")
    parser.add_argument("--limit", type=int, default=0, help="Max number of results to print. 0 means unlimited.")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    mc_root = root / ".gradle" / "loom-cache" / "minecraftMaven" / "net" / "minecraft"
    if not mc_root.exists():
        print(f"Minecraft Loom cache root not found: {mc_root}", file=sys.stderr)
        return 2

    jars = []
    for p in mc_root.rglob("*.jar"):
        s = str(p)
        if "minecraft-merged-" not in s and "minecraft-client-" not in s and "minecraft-server-" not in s:
            continue
        if args.version:
            needle = f"{args.version}".replace("/", "\\")
            if needle not in s:
                continue
        jars.append(p)

    jars.sort(key=lambda p: (priority(p), str(p)))
    if args.limit > 0:
        jars = jars[: args.limit]

    if not jars:
        if args.version:
            print(f"No Minecraft jars found for version '{args.version}' under {mc_root}")
        else:
            print(f"No Minecraft jars found under {mc_root}")
        return 1

    for p in jars:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
