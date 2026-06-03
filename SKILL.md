---
name: fabric-mod-dev
description: Develop, modify, and debug Minecraft Fabric mods in Gradle projects that use Fabric Loom (`fabric-loom`, `net.fabricmc.fabric-loom`, or `net.fabricmc.fabric-loom-remap`). Use when tasks involve Fabric mod entrypoints, mixins, Minecraft version upgrades (including 1.21.x and post-1.21 year-prefixed versions like 26.1), Gradle build setup, or reading vanilla Minecraft code from Loom cache jars.
---

# Fabric Mod Dev

Use this skill to execute Fabric tasks with a stable workflow and avoid re-discovering Loom details.

## Quick Start

1. Confirm the project is Gradle and uses Loom plugin.
2. Confirm target Minecraft version and mapping/toolchain compatibility.
3. Implement or modify Fabric mod code (entrypoints, mixins, registries, rendering, networking).
4. If behavior depends on vanilla internals, inspect the Minecraft jar from Loom cache before editing.
5. Run Gradle checks and fix compile/runtime issues.

## Script Paths
- Treat bundled `scripts/` paths as relative to this skill directory, not the target project root.
- When invoking bundled Python scripts on macOS, try `python3` first; fall back to `python` only if `python3` is unavailable.

## Project Validation

Run `python scripts/analyze_fabric_project.py --project-root <root> --require-loom --resolve-remote --json` from project root first.

- Require `build.gradle`, `build.gradle.kts`, or `settings.gradle(.kts)`.
- Require Loom plugin id in build scripts:
  - `fabric-loom`
  - `net.fabricmc.fabric-loom`
  - `net.fabricmc.fabric-loom-remap`

Note: `net.fabricmc.fabric-loom-remap` is same as `fabric-loom` for obfuscated versions (1.21.x and below), but does not support year-prefixed versions (26.1 and above). The difference is that `net.fabricmc.fabric-loom` does not apply remapping to Minecraft jars for any version, while `fabric-loom` and `net.fabricmc.fabric-loom-remap` apply remapping for 1.21.x and below but not for year-prefixed versions.

If Loom plugin is missing, stop Fabric-specific edits and ask for project setup confirmation.

## Version Rules

- Treat `1.21.x` as standard semantic Minecraft versions.
- Treat post-1.21 versions with year-prefix naming (for example `26.1`) as valid Minecraft versions.
- Read version from `gradle.properties`, `*.gradle(.kts)`, and `*.versions.toml`.
- For robust version resolution, fetch remote versions from:
  - `https://meta.fabricmc.net/v2/versions/game`
  - `https://meta.fabricmc.net/v2/versions/loader`
  - `https://meta.fabricmc.net/v2/versions/yarn` (only when Yarn is required)
  - `https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/maven-metadata.xml`
- Keep mappings and loader versions aligned with the selected Minecraft version.

Yarn is optional:
- If project does not use Yarn mapping (for example uses `officialMojangMappings()`), skip Yarn dependency/version requirements.
- If Loom plugin is `net.fabricmc.fabric-loom` and project has no explicit Yarn mapping usage, skip Yarn dependency/version requirements.

## Migration Notes (Year-Named Versions)

For year-named versions (after `1.21.11`, for example `26.1`):

- Use plugin id `net.fabricmc.fabric-loom`.
- Do not configure any explicit mappings in `dependencies` (no Yarn and no `officialMojangMappings()` block).
- Treat codebase assumptions as equivalent to old `officialMojangMappings()` naming expectations.
- Do not assume all legacy remap-related operations still apply under `net.fabricmc.fabric-loom` for these versions, because Minecraft jars are no longer obfuscated.

Dependency style migration in `dependencies`:

- Migrate old Loom-specific `mod*` configurations to normal Gradle jar configurations.
- Use matching non-mod configuration where possible:
  - `modApi` -> `api`
  - `modImplementation` -> `implementation`
  - `modCompileOnly` -> `compileOnly`
  - `modRuntimeOnly` -> `runtimeOnly`

For version detection patterns and fallback order, read `references/versioning.md`.
For same-mapping-family Minecraft version upgrades (for example Yarn-to-Yarn or official-to-official), read `references/version-upgrade.md`.
For mapping namespace migration workflow, read `references/mappings-migration.md`.

## Vanilla Code Inspection

When a task needs original game logic, locate Loom cache jars with:

`python scripts/find_minecraft_jar.py --project-root <root> [--version <version>]`

Optional: run `./gradlew genSources` (or `./gradlew.bat genSources` on Windows) to generate/decompile Minecraft sources jar via Loom.
- This task can apply project `accessWidener` configuration when present (validated by `validateAccessWidener` in this project run).
- This task is not required; reading classes directly from Minecraft jars is still valid.

Use this cache root pattern:

`.gradle/loom-cache/minecraftMaven/net/minecraft/minecraft-client|server|merged-$hash/$version/`

Prioritize these package prefixes while tracing behavior:

- `com.mojang.blaze3d`
- `net.minecraft`

For lookup details and examples, read `references/minecraft-source-inspection.md`.

## Implementation Guidelines

- Keep edits minimal and version-compatible with the project target.
- Prefer existing patterns already used in the mod (registries, event wiring, mixin style).
- When touching mixins, verify target class/member signatures against the resolved Minecraft jar.
- For rendering or UI issues, inspect both:
  - `com.mojang.blaze3d.*` for low-level rendering paths
  - `net.minecraft.client.*` for client behavior
- For game logic issues, inspect `net.minecraft.*` server/common packages first.

## Validation Commands

- `./gradlew compileKotlin` when the task exists in Java/Kotlin mixed projects.
- `./gradlew compileJava --continue --console=plain`
- `./gradlew validateAccessWidener` when the task exists.
- `./gradlew classes` or `./gradlew build`
- `./gradlew test` when tests exist.
- Project-specific run tasks such as `runClient` or `runServer` only after compile/AW validation passes or when the user explicitly asks for runtime validation.

Run only the smallest command set needed to verify the change.
