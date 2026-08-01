# Minecraft Source Inspection

## Purpose

Locate and inspect vanilla Minecraft jars resolved by Fabric Loom in a Gradle project.

## Cache Path Pattern

Use the project-local Loom cache:

`.gradle/loom-cache/minecraftMaven/net/minecraft/minecraft-client|server|merged-$hash/$version/`

The version folder usually contains one or more jar files.

## Preferred Search Order

1. `minecraft-merged-*` variant if present.
2. `minecraft-client-*` for rendering/client behavior.
3. `minecraft-server-*` for dedicated-server and logic behavior.

## High-Value Package Prefixes

- `com.mojang.blaze3d`
- `net.minecraft`

Start from these prefixes when tracking rendering, UI, world logic, networking, and entity systems.

## Practical Workflow

1. Use `python scripts/find_minecraft_jar.py --project-root <root>` to list candidate jars.
2. When a sources jar exists, inspect it directly:

   ```text
   python scripts/find_minecraft_jar.py --project-root <root> --version <version> read --class net.minecraft.client.gui.Font
   python scripts/find_minecraft_jar.py --project-root <root> --version <version> search --query SignRenderer
   python scripts/find_minecraft_jar.py --project-root <root> --version <version> grep --pattern "submitText\\("
   ```

   `search` matches Java entry paths case-insensitively. `grep` accepts a Python regular expression and prints `jar!/entry:line:text`; use `--json` for structured results and `--limit` to bound output.
3. Optionally run `./gradlew genSources` (or `./gradlew.bat genSources`) to let Loom generate sources jars.
4. If `accessWidener` is configured, `genSources` can apply/validate it (for example this project executes `validateAccessWidener` before `genSources`).
5. Open/decompile the jar or generated sources with your preferred Java decompiler/IDE.
6. Confirm class/member signatures before writing or updating mixins.
7. Rebuild to verify target compatibility.

## Notes

- `genSources` is optional.
- When speed matters, read classes directly from merged/client/server jars without generating sources first.
