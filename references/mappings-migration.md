# Mappings Migration Notes

## Scope

Use this guide when migrating mapping namespace between Yarn and Mojang mappings in Fabric projects.

## Key Rules

- Commit or back up before migration.
- Do not edit `gradle.properties` / `build.gradle(.kts)` mappings config before running migration tools.
- Review and fix Mixins/ClassTweakers/AccessWideners after migration.

## Tool Choice

- Loom (`migrateMappings`) is semi-automated, but does not support Kotlin source migration.
- Ravel (IntelliJ plugin) supports Java, Kotlin, Mixins, Class Tweakers, and Access Wideners.

If project contains Kotlin, prefer Ravel.

## Loom Migration Workflow

1. Run migration command with target mappings.
2. By default output is `remappedSrc`; copy results back after review.
3. On Loom 1.13+, use `--overrideInputsIHaveABackup` for in-place overwrite.
4. After code migration, update Gradle mappings config.
5. Refresh Gradle and perform manual fixes.

Example (to Mojang mappings, 1.21.11):

`./gradlew migrateMappings --mappings "net.minecraft:mappings:1.21.11"`

Or in-place (backup required):

`./gradlew migrateMappings --mappings "net.minecraft:mappings:1.21.11" --overrideInputsIHaveABackup`

Additional Loom tasks (1.13+):

- `migrateClientMappings`
- `migrateClassTweakerMappings`

Useful options:

- `--input <path>` (default `src/main/java`)
- `--output <path>` (default `remappedSrc`)
- `--mappings <group:artifact:version[:classifier]>`

## Ravel Workflow

1. Install Ravel plugin in IntelliJ IDEA.
2. Start remap from Refactor menu.
3. Configure mapping files and source/destination namespaces.
4. Run remap and fix flagged `TODO(Ravel)` markers.
5. Update Gradle mappings config only after source remap finishes.

## Version Transition Guidance

- Yarn availability ends at `1.21.11` (per Fabric docs migration guidance).
- For `26.1+` (year-named, deobfuscated era), prefer Mojang-named code path and avoid introducing legacy mappings migration/remap assumptions.
- For these versions with `net.fabricmc.fabric-loom`, not all old remap-centric operations are applicable.
