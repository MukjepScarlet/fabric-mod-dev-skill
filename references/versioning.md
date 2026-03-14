# Fabric Versioning Notes

## Goal

Resolve target Minecraft version for Fabric mod tasks across both classic (`1.21.x`) and year-prefixed versions (for example `26.1`).

## Detection Order

1. Run `python scripts/analyze_fabric_project.py --project-root <root> --resolve-remote --json`.
2. Read `gradle.properties` and check keys such as:
   - `minecraft_version`
   - `minecraftVersion`
3. Read `*.versions.toml` (especially `gradle/libs.versions.toml`) and resolve `versions`, plugin versions, and library `version` / `version.ref`.
4. Read `*.gradle` / `*.gradle.kts` for:
   - direct version assignments
   - dependency coordinates (`net.minecraft:minecraft`, `net.fabricmc:yarn`, `fabric-loader`, `fabric-api`)
5. If multiple modules differ, use the module directly related to the requested task.

## Remote Source Of Truth

Use these sources for robust latest-version checks:

- Game versions: `https://meta.fabricmc.net/v2/versions/game`
- Fabric Loader versions: `https://meta.fabricmc.net/v2/versions/loader`
- Yarn mapping versions: `https://meta.fabricmc.net/v2/versions/yarn`
- Fabric API versions: `https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/maven-metadata.xml`

Filter Yarn and Fabric API by resolved Minecraft version when possible.

## Yarn Requirement Rule

- Require Yarn only when the project actually uses Yarn mapping.
- If project uses Mojang official mappings and no explicit Yarn mapping, skip Yarn.
- If Loom plugin is `net.fabricmc.fabric-loom` and no explicit Yarn usage is detected, skip Yarn.

## Migration Rule For 1.21.11+

For `1.21.11+` (including year-named versions like `26.1`), enforce:

- Plugin must be `net.fabricmc.fabric-loom`.
- Remove mappings configuration from `dependencies` (do not declare Yarn or `officialMojangMappings()` there).
- Keep code naming expectations equivalent to previous official-Mojang-mapped style.
- Treat remap behavior as limited: under `net.fabricmc.fabric-loom` for these versions, not all old remap-related operations are applicable because Minecraft jars are no longer obfuscated.

Also migrate Loom mod dependency buckets to normal jar buckets:

- `modApi` -> `api`
- `modImplementation` -> `implementation`
- `modCompileOnly` -> `compileOnly`
- `modRuntimeOnly` -> `runtimeOnly`

For mapping migration procedures (Loom `migrateMappings` / Ravel), read `references/mappings-migration.md`.

## Compatibility Checks

- Ensure Fabric Loader and Yarn/official mappings are compatible with the resolved Minecraft version.
- When upgrading between minor versions, re-check mixin targets and access wideners.
- For year-prefixed versions (for example `26.1`), do not force semantic `1.x` parsing logic.
