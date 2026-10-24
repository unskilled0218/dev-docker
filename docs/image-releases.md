# Image releases

- [Commands](#commands)
- [Settings and prerequisites](#settings-and-prerequisites)
- [Credentials and trust](#credentials-and-trust)
- [Publication and recovery](#publication-and-recovery)
- [Offline verification](#offline-verification)
- [Native readiness checklist](#native-readiness-checklist)
- [Reference and limits](#reference-and-limits)

## Commands

```bash
bash build-all.sh --validate
bash build-all.sh --build-only
bash build-all.sh
```

Validation needs Bash and Python 3.11+ only. It reads local settings, version, notes, and source paths without credentials, locks, temporary files, Docker, or network access. Commands work from any directory.

No arguments publishes root `VERSION` as `v<VERSION>` and `latest` for all images. Update `VERSION`, `scripts/release.json`'s notes path, and matching committed release notes together; commit and push clean `main` before publication. This repository starts at 0.1.0; README has no duplicate version source.

`--help` and `-h` show usage using Bash only. A positional tag is deprecated but accepted only when it exactly equals `v<VERSION>`, with or without `--build-only`, in either order. Mismatched tags (including explicit `latest`), duplicate tags/flags, unknown flags, and help/validation combined with other arguments are refused before external effects. There is no arbitrary-tag publication override.

## Settings and prerequisites

Review `scripts/release.json` before use. Its strict schema names this repository (`https://git.lan`, `dev/dev-docker`), login, credential/certificate paths, notes, AMD64 platform, and the ordered five-image graph. Unknown/duplicate fields, path traversal, symlink source files, changed graph order/parents, and unsupported platforms are refused. There is no runtime download or self-update of release tooling.

Images publish under `git.lan/dev`: `my-base`, `npm-non-root`, `android-dev`, `tauri-dev`, and `switchboard`. Base precedes npm, npm precedes Android, and Android precedes Tauri and Switchboard. Release children use verified parent digests, not local tags. OCI source labels identify this repository; existing package association may still need manual settings in Gitea. No automatic reassignment occurs.

Publication requires Git, curl, Docker Buildx, a reachable selected builder advertising `linux/amd64`, independent Git authentication, trusted HTTPS, and a clean, already-pushed `main`. Fetch and push origins must each identify the configured project; multiple destinations are refused. The script never pushes source. One operator must exclude all other writers across the repository and five images; a checkout lock is not a distributed lock.

Build-only uses current Dockerfiles and needs neither clean `main` nor remote Git checks. It requires the selected Buildx builder to use the `docker` driver and the same Docker endpoint/image store as local image inspection. Select a supported builder explicitly before running. Container-backed, remote, Kubernetes, unknown, or mismatched builders are refused before builds; the command never creates/switches builders or pushes as a fallback. Each parent is loaded and its local ID checked before and after building children with its local tag and `--pull=false`. A local image ID is a config digest, not a registry manifest reference; do not pass it directly as a BuildKit `FROM`. Local `image:latest` names remain available for existing Compose/Dockerfile defaults. Publication does not load local images; run build-only separately if needed. Exclude concurrent local image writers while building.

Only AMD64 is supported: Android, Watchman, and Switchboard dependencies have architecture-specific assumptions. The command installs no tools, certificates, privileged emulation, or host dependencies. Provide missing prerequisites separately.

## Credentials and trust

Credential-file precedence is nonempty `GIT_TOKEN`, then nonempty deprecated `FORGEJO_TOKEN_FILE`, then configured `token_file`. These variables contain file paths, never token values. The configured default remains `~/.config/forgejo/forgejo-token` for compatibility; you may explicitly configure `~/.config/git/token`. Username precedence is nonempty `GIT_USERNAME`, then nonempty deprecated `FORGEJO_USERNAME`, then configured `username`. Empty overrides are treated as unset.

Use a non-symlink, user-owned regular token file outside the repository, mode 0600 or 0400, containing a private repository/package-capable token. Never commit it or place it in command arguments, shell history, `.env`, build contexts, or logs. Both publication and build-only need it because the current base Dockerfile requests BuildKit secret ID `token` at `/home/container/.config/git/token`. The secret value goes to Docker login via stdin and to builds only through a private BuildKit secret file. The base setup's secret-mounted command currently only creates a directory; this release migration does not redesign that setup.

The existing certificate defaults to `/usr/local/share/ca-certificates/git.lanCA.crt`; override with `BUILD_CERT_FILE`. Its captured bytes are injected into the private build context and its hash binds release identity. Keep Git/curl/Docker HTTPS trust enabled. No TLS bypass or automatic trust installation occurs.

Publication uses a private mode-0700 temporary directory with minimal Docker auth and copied connection metadata, never inherited registry helpers/auth. Original config-local CLI plugin discovery and Buildx state paths are preserved; Docker host/context and TLS environment variables remain selected. Relative paths keep caller working-directory semantics. Normal failure/exit/signals remove only run-owned temporary files, not images or remote records. SIGKILL cannot perform cleanup; inspect leftovers privately without broad deletion.

## Publication and recovery

Publication locks `.release-operation.lock`, verifies source and target, inventories all final records and aliases, and classifies startup before any registry login or staging push. A failed/incomplete/oversized read is never permission to write. API inventories must end with a confirmed empty page; authenticated curl disables ambient config, follows no redirects, and refuses foreign registry token realms.

Fresh startup requires no requested Git tag/release and no version aliases for any image. Every `latest` is captured as its predecessor (including confirmed absence). All matching release-specific staging evidence is checked before the first build; verified parents are reused and missing members built once. Orphan/conflicting staging stops. Staging pushes are intermediate remote writes, even if final publication later fails.

Only after all five images verify does the command push one exact deterministic annotated Git tag binding commit, version, settings/helpers, notes, certificate, platform, all digests, and predecessors. It promotes version and `latest` aliases from those digests without rebuilding, then creates a notes-only Gitea release. Fresh guards check the complete alias/tag state before each write; a confirmed promotion must remain at the prepared digest. Final verification checks all records and images, then prints immutable references and the release URL.

A fully completed retry verifies without build, login, tag push, promotion, or release creation. It ignores missing/foreign staging. A fresh attempt may reuse verified staging, but tag-only, release-only, orphan version aliases (even matching ones), conflicting identity, missing bound content, foreign final aliases, or partially promoted startup require manual review. Version aliases are never adoption authority. A lost response may be reconciled only against fresh exact evidence for that invocation's own attempted write.

There is no cross-service atomic transaction or exactly-once build promise. On failure, inspect the reported phase, known digest/alias map, exact source/configuration, Git tag, release, and all image aliases. Do not blindly retry ambiguous states. Do not delete evidence, rewrite tags, force pushes, roll back aliases, change settings to force success, or expect automatic repair. Manual completion needs separate review/authorization. There is no retention, package reassignment, image deletion, or rollback stage.

## Offline verification

```bash
python3 -B -m unittest discover -s tests -v
bash -n build-all.sh
bash build-all.sh --validate
```

Tests use temporary Git repositories and stateful fake command/HTTP boundaries. They check five-image ordering, digest identities, credential isolation, compatibility, failure/retry guards, and zero unauthorized writes. Passing offline checks establishes local implementation acceptance only, not native Buildx behavior, real image toolchain correctness, or production readiness.

## Native readiness checklist

Run only with separate user authorization and existing prerequisites. This implementation does not automatically run native builds or publication. Record command versions, selected context/host, builder driver/endpoint, each result, and all skipped connection variants without exposing credentials. Failed/skipped/unavailable checks leave that setup operationally unverified.

1. Record `docker version`, `docker buildx version`, `docker context show`, sanitized connection details, and `docker buildx inspect --bootstrap`. Confirm Linux AMD64 support and Docker-driver image-store routing for build-only. Do not switch/create builders implicitly.
2. In a private temporary test setup, compare plugin discovery/version before and during the same minimal-auth isolation used by `docker_auth` in `scripts/release_data.py`. Exercise a Buildx executable available only in the original config's `cli-plugins` and any configured extra plugin directory. Verify no caller auth/helper inventory is copied. Do not log in or contact production registries.
3. Compare context, Docker endpoint, TLS connection, and builder selection before/during isolation for host-only environment selection, explicit `default`, a nondefault context, and relative connection paths. Record which variants were actually exercised; do not infer untested TLS or remote behavior from a fake test.
4. Use a private temporary context and unique local image names to build a minimal parent with a unique marker, load it using the supported Docker driver, inspect its ID, then build a child using the checked local tag as `BASE_IMAGE` and `--pull=false`. Verify the parent ID is unchanged before/after the child build, the child's filesystem contains that marker rather than a stale parent marker, and the child parent label records that ID. Use no production tags or pushes; only remove the exact test-owned files/images after inspection and authorization.
5. With a separately selected container-backed builder, verify build-only refuses before any build. Restore any explicitly changed selection yourself; the script must not switch it. Record the actionable refusal.

A passing smoke checklist does not authorize or certify real publication. Actual five-image builds and production publishing need separate approval. Mutable downloaded setup scripts/packages mean source/digest identity is not reproducible bytes or runtime proof.

## Reference and limits

The local release code adapts [container-release-template](https://git.lan/dev/container-release-template) 0.4.0, inspected at commit `1d051b36888fd64d9bfcd49e8e09f504943b6a1a`. It extends the identity to five images and distinguishes post-promotion alias expectations. It preserves config-local plugin search paths instead of copying the reference's documented plugin-discovery omission. Neither change has native readiness proof until the checklist passes.

Each HTTPS/manifest body is bounded at 4 MiB; config/token bodies at 1 MiB; headers, notes, and annotations at 64 KiB; Git advertisements at 16 MiB. Inventories share 1,002-page, 100,000-item, 64 MiB, and 600-second budgets. Reads time out after 60 seconds and builds after 7,200 seconds. Process output is bounded while receiving, not truncated into valid evidence. No raw command stderr or authenticated response body is relayed. These bounds do not limit Docker storage use or arbitrary Git pack storage.
