- [Scope](#scope)
- [Implementation plan](#implementation-plan)
  - [Summary](#summary)
  - [1. Capture both certificate inputs](#1-capture-both-certificate-inputs)
  - [2. Include and trust both certificates](#2-include-and-trust-both-certificates)
  - [3. Add regression tests and update documentation](#3-add-regression-tests-and-update-documentation)
- [Acceptance criteria](#acceptance-criteria)
- [Risks and decisions](#risks-and-decisions)

## Scope

Add `ntfy.lanCA.crt` alongside `git.lanCA.crt` in the base image and the automated build context. Preserve build-only and publication safeguards. Do not change unrelated images, host trust, package association, or notification configuration.

## Implementation plan

### Summary

The current Dockerfile copies only the Git certificate. `scripts/release_data.py` captures that certificate, hashes it for release identity, rechecks it before publication writes, and copies it into a private build context. Extend that path to include a separately supplied ntfy certificate.

### 1. Capture both certificate inputs

- Add `ntfy_certificate_file` to `scripts/release.json`, defaulting to `/usr/local/share/ca-certificates/ntfy.lanCA.crt`, and update the strict configuration field validation in `settings()`.
- Keep `certificate_file` and `BUILD_CERT_FILE` unchanged for Git. Add the nonempty environment override `BUILD_NTFY_CERT_FILE` for ntfy; treat an empty override as unset and preserve existing caller-relative path semantics.
- In `init()`, require both inputs to exist and contain nonempty bytes, using the existing bounded reader. Capture them as separate private files before builder operations, credentials, login, or builds. Report which certificate input is missing or invalid without printing certificate contents.
- Compute `certificate_hash` from a deterministic, unambiguous encoding of both destination filenames and their individual SHA-256 hashes. Retain the existing identity field and OCI label names, but make their value bind both certificate inputs.
- Share the certificate selection and fingerprint logic between `init()` and `unchanged()` so publication guards reject changes to either source. Keep snapshots based on captured bytes, not later reads of the original paths.
- Keep `--validate` independent of external certificate files; it should validate configuration without requiring either certificate to exist.

### 2. Include and trust both certificates

- Extend `snapshot()` to copy the captured ntfy certificate into the private context as `ntfy.lanCA.crt`, alongside `git.lanCA.crt`, for both local builds and publication.
- Add an explicit `COPY ntfy.lanCA.crt /usr/local/share/ca-certificates/ntfy.lanCA.crt` beside the existing Git certificate copy in `Dockerfile/base.Dockerfile`.
- Keep both copies before the existing `update-ca-certificates` invocation. Preserve the remaining image setup and BuildKit secret handling.

### 3. Add regression tests and update documentation

- Update `ReleaseFixture` in `tests/test_build_all.py` with a distinct ntfy certificate file and `BUILD_NTFY_CERT_FILE`; never depend on certificates installed on the test host.
- Update `tests/fake_release_ports.py` to assert the exact context inventory includes both certificates, each with its own expected bytes, and still excludes credentials.
- Cover successful build-only and publication flows, read-only completed retries, default/override/empty-override selection, and `--validate` with both certificate inputs absent.
- Test missing, empty, and oversized ntfy inputs refusing before builds or publication writes. Keep existing Git certificate failure coverage and private-file cleanup assertions.
- Add focused tests proving a change to either certificate changes the combined fingerprint, publication guards reject either changed input, and snapshots retain captured bytes if an original input changes later.
- Add a Dockerfile contract assertion that both certificate copies precede `update-ca-certificates`; fake Docker alone does not execute trust installation.
- Update `docs/image-releases.md` with both default paths, both overrides, the requirement to provide both files, the combined release fingerprint, and the distinction between image trust and host trust. Document both context filenames for manual builds.
- Run `python3 -B -m unittest discover -s tests -v`, `bash -n build-all.sh`, and `bash build-all.sh --validate`. Do not publish images or run networked Docker builds as part of offline verification.

## Acceptance criteria

- The base Dockerfile copies both CA files into `/usr/local/share/ca-certificates/` before updating image trust.
- Both automated build modes supply the exact captured bytes of both certificates in their private contexts.
- Git's existing input setting remains supported; ntfy has its own documented default and override.
- Missing, empty, or oversized required certificates stop before builds or publication mutations; validation still works without external certificates.
- Both certificate inputs affect release identity, and publication guards reject changes to either input.
- Regression tests and offline validation pass without Docker, real credentials, network access, or host-installed test certificates.
- No host trust installation, TLS bypass, notification changes, or remote publication occurs.

## Risks and decisions

- A Dockerfile-only change would fail because the automated private context currently contains only `git.lanCA.crt`; the snapshot path must change with it.
- Both certificates are required for actual builds. The user must provide the ntfy certificate separately; do not download, fabricate, or commit CA files.
- The combined certificate fingerprint changes release identity. Existing completed releases and staged images with the old identity must not be adopted or rewritten; preserve current conflict refusals and use a new release version for later publication.
- Offline tests prove context contents and Dockerfile ordering, not actual CA validity or live HTTPS connectivity. A native image build and ntfy trust check require separate authorization and valid supplied certificates.
