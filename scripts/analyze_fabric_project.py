#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import tomllib  # py311+
except Exception:  # pragma: no cover
    tomllib = None


LOOM_PLUGIN_IDS = (
    "fabric-loom",
    "net.fabricmc.fabric-loom",
    "net.fabricmc.fabric-loom-remap",
)

EXCLUDE_DIRS = {".git", ".gradle", "build", ".idea", ".kotlin"}
GRADLE_FILE_NAMES = {"build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"}
MC_VERSION_RE = re.compile(r"^(?:1\.\d+(?:\.\d+)?(?:[-+].*)?|\d{2}\.\d+(?:[-+].*)?)$")
FABRIC_META_GAME_URL = "https://meta.fabricmc.net/v2/versions/game"
FABRIC_META_LOADER_URL = "https://meta.fabricmc.net/v2/versions/loader"
FABRIC_META_YARN_URL = "https://meta.fabricmc.net/v2/versions/yarn"
FABRIC_API_METADATA_URL = "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/maven-metadata.xml"


def iter_files(root: Path, file_predicate):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if file_predicate(p):
            yield p


def parse_gradle_properties(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        m = re.match(r"^([^:=\s]+)\s*[:=]\s*(.*)$", line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def _resolve_toml_version(entry, versions: dict) -> str | None:
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return None
    if "version" in entry:
        v = entry["version"]
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            ref = v.get("ref")
            if isinstance(ref, str):
                vv = versions.get(ref)
                return vv if isinstance(vv, str) else None
    ref = entry.get("version.ref")
    if isinstance(ref, str):
        vv = versions.get(ref)
        return vv if isinstance(vv, str) else None
    nested = entry.get("version_ref")
    if isinstance(nested, str):
        vv = versions.get(nested)
        return vv if isinstance(vv, str) else None
    return None


def parse_versions_toml(path: Path) -> dict:
    data = {"versions": {}, "plugins": {}, "libraries": {}}
    text = path.read_text(encoding="utf-8", errors="ignore")
    if tomllib is not None:
        try:
            obj = tomllib.loads(text)
        except Exception:
            obj = {}
    else:
        obj = {}

    if not obj:
        return parse_versions_toml_fallback(text)

    versions = obj.get("versions", {})
    if isinstance(versions, dict):
        for k, v in versions.items():
            if isinstance(v, str):
                data["versions"][k] = v

    plugins = obj.get("plugins", {})
    if isinstance(plugins, dict):
        for k, v in plugins.items():
            if isinstance(v, dict):
                pid = v.get("id")
                if isinstance(pid, str):
                    data["plugins"][k] = {"id": pid, "version": _resolve_toml_version(v, data["versions"])}

    libraries = obj.get("libraries", {})
    if isinstance(libraries, dict):
        for k, v in libraries.items():
            if isinstance(v, dict):
                module = v.get("module")
                if isinstance(module, str):
                    data["libraries"][k] = {"module": module, "version": _resolve_toml_version(v, data["versions"])}
    return data


def parse_versions_toml_fallback(text: str) -> dict:
    data = {"versions": {}, "plugins": {}, "libraries": {}}
    section = None

    def parse_inline_table(raw: str) -> dict[str, str]:
        out = {}
        body = raw.strip()
        if body.startswith("{") and body.endswith("}"):
            body = body[1:-1]
        for piece in body.split(","):
            part = piece.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            out[k] = v
        return out

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        sec = re.match(r"^\[([^\]]+)\]$", line)
        if sec:
            section = sec.group(1).strip()
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if section == "versions":
            m = re.match(r"""^["']?([^"']+)["']?$""", value)
            if m:
                data["versions"][key] = m.group(1)
        elif section == "plugins" and value.startswith("{"):
            inline = parse_inline_table(value)
            pid = inline.get("id")
            if pid:
                ref = inline.get("version.ref")
                ver = inline.get("version")
                if ref and ref in data["versions"]:
                    ver = data["versions"][ref]
                data["plugins"][key] = {"id": pid, "version": ver}
        elif section == "libraries" and value.startswith("{"):
            inline = parse_inline_table(value)
            module = inline.get("module")
            if not module:
                group = inline.get("group")
                name = inline.get("name")
                if group and name:
                    module = f"{group}:{name}"
            if module:
                ref = inline.get("version.ref")
                ver = inline.get("version")
                if ref and ref in data["versions"]:
                    ver = data["versions"][ref]
                data["libraries"][key] = {"module": module, "version": ver}
    return data


def fetch_json(url: str, timeout_sec: float) -> list | dict:
    req = urllib.request.Request(url, headers={"User-Agent": "fabric-mod-dev-skill/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def fetch_text(url: str, timeout_sec: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fabric-mod-dev-skill/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_loader_versions(payload) -> list[str]:
    out = []
    seen = set()
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                if isinstance(item.get("version"), str):
                    v = item["version"]
                    if v not in seen:
                        seen.add(v)
                        out.append(v)
                loader = item.get("loader")
                if isinstance(loader, dict) and isinstance(loader.get("version"), str):
                    v = loader["version"]
                    if v not in seen:
                        seen.add(v)
                        out.append(v)
    return out


def parse_game_versions(payload) -> list[str]:
    out = []
    seen = set()
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("version"), str):
                v = item["version"]
                if v not in seen:
                    seen.add(v)
                    out.append(v)
    return out


def parse_yarn_versions(payload, minecraft_version: str | None) -> list[str]:
    out = []
    seen = set()
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            yver = item.get("version")
            if not isinstance(yver, str):
                continue
            gver = item.get("gameVersion")
            if minecraft_version and isinstance(gver, str) and gver != minecraft_version:
                continue
            if yver not in seen:
                seen.add(yver)
                out.append(yver)
    return out


def parse_fabric_api_versions(xml_text: str, minecraft_version: str | None) -> list[str]:
    out = []
    seen = set()
    root = ET.fromstring(xml_text)
    nodes = root.findall(".//versioning/versions/version")
    for node in reversed(nodes):
        if node.text:
            v = node.text.strip()
            if not v:
                continue
            if minecraft_version:
                if f"+{minecraft_version}" in v:
                    if v not in seen:
                        seen.add(v)
                        out.append(v)
            else:
                if v not in seen:
                    seen.add(v)
                    out.append(v)
    return out


def detect_mapping_mode(gradle_texts: list[str], coord_hits: list[dict], toml_libraries: list[dict]) -> str:
    has_yarn_coord = any(item.get("module") == "net.fabricmc:yarn" for item in coord_hits)
    has_yarn_toml = any(str(item.get("module", "")).strip() == "net.fabricmc:yarn" for item in toml_libraries)
    has_yarn_call = any(re.search(r"\byarn\s*\(", text) for text in gradle_texts)
    has_official_call = any("officialMojangMappings(" in text for text in gradle_texts)

    if has_yarn_coord or has_yarn_toml or has_yarn_call:
        return "yarn"
    if has_official_call:
        return "official"
    return "unknown"


def resolve_remote_versions(
    minecraft_version: str | None,
    need_yarn: bool,
    timeout_sec: float,
    limit: int,
) -> dict:
    remote = {
        "minecraft": {"url": FABRIC_META_GAME_URL, "versions": [], "error": None},
        "loader": {"url": FABRIC_META_LOADER_URL, "versions": [], "error": None},
        "yarn": {"url": FABRIC_META_YARN_URL, "versions": [], "error": None, "skipped": not need_yarn},
        "fabric_api": {"url": FABRIC_API_METADATA_URL, "versions": [], "error": None},
    }

    try:
        payload = fetch_json(FABRIC_META_GAME_URL, timeout_sec)
        remote["minecraft"]["versions"] = parse_game_versions(payload)[:limit]
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        remote["minecraft"]["error"] = str(e)

    try:
        payload = fetch_json(FABRIC_META_LOADER_URL, timeout_sec)
        remote["loader"]["versions"] = parse_loader_versions(payload)[:limit]
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        remote["loader"]["error"] = str(e)

    if need_yarn:
        try:
            payload = fetch_json(FABRIC_META_YARN_URL, timeout_sec)
            remote["yarn"]["versions"] = parse_yarn_versions(payload, minecraft_version)[:limit]
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            remote["yarn"]["error"] = str(e)

    try:
        xml_text = fetch_text(FABRIC_API_METADATA_URL, timeout_sec)
        remote["fabric_api"]["versions"] = parse_fabric_api_versions(xml_text, minecraft_version)[:limit]
    except (urllib.error.URLError, TimeoutError, ValueError, ET.ParseError) as e:
        remote["fabric_api"]["error"] = str(e)

    return remote


def analyze(root: Path, resolve_remote: bool = False, timeout_sec: float = 10.0, remote_limit: int = 30) -> dict:
    gradle_files = sorted(
        iter_files(root, lambda p: p.name in GRADLE_FILE_NAMES),
        key=lambda p: str(p),
    )
    properties_files = sorted(
        iter_files(root, lambda p: p.name == "gradle.properties"),
        key=lambda p: str(p),
    )
    toml_files = sorted(
        iter_files(root, lambda p: p.suffix == ".toml" and ("versions" in p.name or p.name == "libs.versions.toml")),
        key=lambda p: str(p),
    )

    loom_hits = []
    gradle_declared = []
    coord_hits = []
    gradle_texts = []
    for gf in gradle_files:
        text = gf.read_text(encoding="utf-8", errors="ignore")
        gradle_texts.append(text)
        for pid in LOOM_PLUGIN_IDS:
            if pid in text:
                loom_hits.append({"file": str(gf), "plugin": pid})

        for m in re.finditer(
            r"""(?im)^\s*(?:val|var)?\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["']([^"']+)["']""",
            text,
        ):
            key = m.group(1).strip()
            val = m.group(2).strip()
            if any(t in key.lower() for t in ("minecraft", "fabric", "yarn", "loader")):
                gradle_declared.append({"file": str(gf), "key": key, "value": val})

        for m in re.finditer(
            r"""["'](net\.minecraft:minecraft|net\.fabricmc:yarn|net\.fabricmc:fabric-loader|net\.fabricmc\.fabric-api:fabric-api):([^"']+)["']""",
            text,
        ):
            coord_hits.append({"file": str(gf), "module": m.group(1), "version": m.group(2).strip()})

    property_hits = []
    for pf in properties_files:
        props = parse_gradle_properties(pf)
        for k, v in props.items():
            if any(t in k.lower() for t in ("minecraft", "fabric", "yarn", "loader")):
                property_hits.append({"file": str(pf), "key": k, "value": v})

    toml_hits = []
    toml_plugins = []
    toml_libraries = []
    plugin_alias_to_id = {}
    version_key_to_value = {}
    for tf in toml_files:
        parsed = parse_versions_toml(tf)
        for k, v in parsed["versions"].items():
            version_key_to_value[k] = v
            if any(t in k.lower() for t in ("minecraft", "fabric", "yarn", "loader")):
                toml_hits.append({"file": str(tf), "key": k, "value": v})
        for k, v in parsed["plugins"].items():
            plugin_alias_to_id[k] = v.get("id")
            toml_plugins.append({"file": str(tf), "alias": k, **v})
        for k, v in parsed["libraries"].items():
            toml_libraries.append({"file": str(tf), "alias": k, **v})

    alias_hits = []
    for gf, text in zip(gradle_files, gradle_texts):
        for m in re.finditer(r"""alias\s*\(\s*libs\.plugins\.([A-Za-z0-9_.-]+)\s*\)""", text):
            alias_path = m.group(1)
            candidates = {alias_path, alias_path.replace(".", "-"), alias_path.replace(".", "_")}
            matched = None
            for c in candidates:
                pid = plugin_alias_to_id.get(c)
                if pid:
                    matched = (c, pid)
                    break
            if matched:
                alias_hits.append(
                    {"file": str(gf), "alias_path": alias_path, "alias_key": matched[0], "plugin": matched[1]}
                )
                if matched[1] in LOOM_PLUGIN_IDS:
                    loom_hits.append({"file": str(gf), "plugin": matched[1]})

        for m in re.finditer(r"""libs\.versions\.([A-Za-z0-9_.-]+)""", text):
            key_path = m.group(1)
            candidates = {key_path, key_path.replace(".", "-"), key_path.replace(".", "_")}
            for c in candidates:
                v = version_key_to_value.get(c)
                if isinstance(v, str):
                    toml_hits.append({"file": str(gf), "key": c, "value": v})
                    break

    candidate_versions = []
    for item in property_hits:
        key = str(item.get("key", "")).lower()
        value = item.get("value")
        if "minecraft" in key and isinstance(value, str) and MC_VERSION_RE.match(value):
            candidate_versions.append(value)
    for item in gradle_declared:
        key = str(item.get("key", "")).lower()
        value = item.get("value")
        if "minecraft" in key and isinstance(value, str) and MC_VERSION_RE.match(value):
            candidate_versions.append(value)
    for item in toml_hits:
        key = str(item.get("key", "")).lower()
        value = item.get("value")
        if "minecraft" in key and isinstance(value, str) and MC_VERSION_RE.match(value):
            candidate_versions.append(value)
    for item in coord_hits:
        module = item.get("module")
        value = item.get("version")
        if module == "net.minecraft:minecraft" and isinstance(value, str) and MC_VERSION_RE.match(value):
            candidate_versions.append(value)

    mapping_mode = detect_mapping_mode(gradle_texts, coord_hits, toml_libraries)
    primary_loom_plugin = None
    if loom_hits:
        primary_loom_plugin = sorted({x["plugin"] for x in loom_hits})[0]
    yarn_required = mapping_mode == "yarn"
    if mapping_mode != "yarn" and primary_loom_plugin == "net.fabricmc.fabric-loom":
        yarn_required = False

    result = {
        "project_root": str(root),
        "gradle_files": [str(p) for p in gradle_files],
        "gradle_properties_files": [str(p) for p in properties_files],
        "versions_toml_files": [str(p) for p in toml_files],
        "loom_plugin_hits": [
            {"file": f, "plugin": p} for f, p in sorted({(x["file"], x["plugin"]) for x in loom_hits})
        ],
        "loom_plugin_found": bool(loom_hits),
        "properties_versions": property_hits,
        "gradle_declared_versions": gradle_declared,
        "dependency_coordinates": coord_hits,
        "toml_versions": toml_hits,
        "toml_plugins": toml_plugins,
        "toml_libraries": toml_libraries,
        "gradle_plugin_alias_hits": alias_hits,
        "mapping_mode": mapping_mode,
        "yarn_required": yarn_required,
        "primary_loom_plugin": primary_loom_plugin,
        "minecraft_version_candidates": sorted(set(candidate_versions)),
    }
    if resolve_remote:
        preferred_minecraft_version = result["minecraft_version_candidates"][0] if result["minecraft_version_candidates"] else None
        result["remote_versions"] = resolve_remote_versions(
            preferred_minecraft_version, yarn_required, timeout_sec=timeout_sec, limit=remote_limit
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Gradle Fabric project and resolve version/dependency hints.")
    parser.add_argument("--project-root", default=".", help="Path to project root.")
    parser.add_argument("--require-loom", action="store_true", help="Return exit code 2 if Loom plugin is not found.")
    parser.add_argument("--resolve-remote", action="store_true", help="Fetch versions from Fabric Meta and Fabric API metadata.")
    parser.add_argument("--remote-timeout", type=float, default=10.0, help="Remote request timeout in seconds.")
    parser.add_argument("--remote-limit", type=int, default=30, help="Maximum versions to keep for each remote source.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    result = analyze(
        root,
        resolve_remote=args.resolve_remote,
        timeout_sec=args.remote_timeout,
        remote_limit=max(1, args.remote_limit),
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Project: {result['project_root']}")
        print(f"Gradle files: {len(result['gradle_files'])}")
        if result["loom_plugin_found"]:
            print("Fabric Loom plugin: found")
            for hit in result["loom_plugin_hits"]:
                print(f"- {hit['file']} [{hit['plugin']}]")
        else:
            print("Fabric Loom plugin: not found")
        print(f"Mapping mode: {result['mapping_mode']} (yarn_required={result['yarn_required']})")
        if result["minecraft_version_candidates"]:
            print("Minecraft version candidates:")
            for v in result["minecraft_version_candidates"]:
                print(f"- {v}")
        if args.resolve_remote and "remote_versions" in result:
            print("Remote sources fetched: fabric-meta game/loader/yarn and fabric-api metadata")

    if not result["gradle_files"]:
        return 3
    if args.require_loom and not result["loom_plugin_found"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
