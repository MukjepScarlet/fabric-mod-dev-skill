# Minecraft Version Upgrade Workflow

## Scope

Use this workflow for Fabric project upgrades where the old and target Minecraft versions stay in the same mapping family, for example:

- Yarn `1.21.4` -> Yarn `1.21.5`
- Mojang official `1.21.4` -> Mojang official `1.21.5`
- Year-named, deobfuscated versions such as `26.1.2` -> `26.2`

If the mapping namespace changes, use `references/mappings-migration.md` instead.

## Workflow

1. Check the working tree and prefer a branch or clean checkpoint before editing.
2. Confirm current and target Minecraft versions, Loom plugin id, mapping family, Java toolchain, Fabric Loader, Fabric API, and important mod dependency versions.
3. Confirm this is a same-mapping-family version upgrade. Do not use `migrateMappings` or Ravel unless the mapping namespace changes.
4. Locate old-version Minecraft jars/sources with `scripts/find_minecraft_jar.py`; run `genSources` only when sources are missing or decompiled source is needed.
5. Update Minecraft/Fabric/mod dependencies to the target version and refresh Gradle.
6. Locate target-version Minecraft jars/sources; run target `genSources` when needed.
7. Prepare searchable old and target vanilla sources. Prefer `rg`; if unavailable, use platform defaults such as `grep -R`, `findstr`, or IDE search.
8. If `compileKotlin` exists, run it first. Then run `compileJava --continue --console=plain`.
9. Run `validateAccessWidener` when present.
10. Run `classes` or `build` only after the smaller compile/AW tasks give useful signal.
11. Group errors by root cause, inspect old vanilla usage first, then inspect the equivalent target-version vanilla usage.
12. Apply straightforward equivalent fixes directly.
13. For non-equivalent behavior migrations, skip them at first, keep them documented, and return after the straightforward layer is verified.
14. Ask the user before changes that affect architecture, behavior semantics, protocol/storage compatibility, or large rendering rewrites.
15. Run `runClient` or `runServer` only after compile/AW validation passes, or when the user explicitly approves runtime validation.

## Error Groups

- Dependency resolution: Fabric Loader, Fabric API modules, and third-party mods unavailable or not on the correct configuration.
- Mapping/name drift within the same family: class, method, field, descriptor, or package changes.
- Vanilla API signature changes: constructor, parameter, return type, or overload changes.
- Vanilla structure changes: class removed, split, merged, or converted away from block entity/entity/data-holder patterns.
- Rendering/client API changes: Blaze3D, block model rendering, GUI rendering, text rendering, and renderer-specific internals.
- Networking/registry/data changes: payload, registry, data component, recipe, tag, or sync API changes.
- Mixin changes: target class/member descriptors, injection points, locals, cancellability, and implementation package moves.
- Access widener changes: missing class/member, renamed descriptor, or visibility no longer needed.
- Runtime-only issues: entrypoints, mod metadata, mixin apply failures, missing resources, and client/server startup failures.

## Practical Rules

- Treat compile classpath problems separately from source migration. If a class exists in a resolved cache jar but compilation cannot import it, inspect Gradle configurations and dependency buckets first.
- For Java/Kotlin mixed projects, do not assume `compileJava` is enough; run `compileKotlin` when available.
- For removed vanilla block entities, check whether the block still exists as `BlockState` and migrate searches from block-entity iteration to block-state/range scanning when appropriate.
- For third-party mod APIs compiled against removed vanilla classes, prefer upgrading the dependency. Code-side fixes cannot repair an incompatible dependency ABI.
- When copying or partially reimplementing vanilla logic, add a concise Javadoc/KDoc `@see` using fully qualified vanilla class/member names.
- When an IDE Mixin plugin or MCP inspection is available, use it for mixin target validation. Gradle compilation may miss unresolved `@At`, local capture, ordinal, and descriptor issues.
- If both old and target vanilla sources are available, use them to identify the semantic migration point; do not rely only on matching names.
- Treat commit-per-mixin or commit-per-related-group as useful hygiene, especially during large migrations, but follow the user's requested commit strategy.
