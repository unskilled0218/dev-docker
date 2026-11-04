- [Scope](#scope)
- [Implementation plan](#implementation-plan)
  - [1. Add the certificate input](#1-add-the-certificate-input)
  - [2. Install the certificate in the image](#2-install-the-certificate-in-the-image)
  - [3. Extend regression tests](#3-extend-regression-tests)
  - [4. Update documentation and verify](#4-update-documentation-and-verify)
- [Acceptance criteria](#acceptance-criteria)
- [Risks and decisions](#risks-and-decisions)

## Scope

Add `penpot.lanCA.crt` alongside the Git and ntfy certificates in automated build contexts and base image trust. Preserve existing certificate handling and release safeguards. Do not change host trust, unrelated images, or publication behavior.

## Implementation plan

### 1. Add the certificate input

- Add `penpot_certificate_file` to `scripts/release.json`, defaulting to `/usr/local/share/ca-certificates/penpot.lanCA.crt`.
- Add that field to the strict configuration field set in `scripts/release_data.py`.
- Extend `CERTIFICATES` with `("penpot.lanCA.crt", "penpot_certificate_file", "BUILD_PENPOT_CERT_FILE")`.
- Reuse the existing loops for input capture, fingerprinting, change guards, and local/publication snapshots. Do not add a separate certificate pipeline.
- Preserve nonempty override precedence, empty-override fallback, home expansion, relative-path behavior, the 1 MiB limit, sanitized errors, and rejection before external operations. Keep `--validate` independent of certificate availability.

### 2. Install the certificate in the image

- Add `COPY penpot.lanCA.crt /usr/local/share/ca-certificates/penpot.lanCA.crt` beside the existing certificate copies in `Dockerfile/base.Dockerfile`, before `update-ca-certificates`.
- Keep Git and ntfy copies unchanged. The npm image inherits the updated base trust without a separate copy.

### 3. Extend regression tests

- Add a distinct Penpot certificate fixture and `BUILD_PENPOT_CERT_FILE` to `tests/test_build_all.py`; extend setup and certificate-removal cases so tests never depend on installed host certificates.
- Extend default-path, individual and combined overrides, empty overrides, home expansion, relative paths, and sanitized read-error tests to cover Penpot while preserving Git and ntfy coverage.
- Extend invalid-input tests for both build modes to reject missing, empty, oversized, and unreadable Penpot inputs before external calls or credential loading; use mocked permission errors where needed.
- Extend fingerprint tests to bind all three filenames and contents, preserve order independence, and reject content changes and name swaps. Extend change-guard tests to each certificate.
- Extend local and publication snapshot tests to assert all three captured byte sequences, even after source files change.
- Update Dockerfile ordering assertions and rename tests that refer to only two certificates.
- Update `tests/fake_release_ports.py` to require the Penpot fixture bytes and the exact context inventory containing the Dockerfile directory, all three certificate files, and the installer scripts directory.
- Retain validation-without-certificates tests and existing publication, cleanup, and secret-isolation tests.

### 4. Update documentation and verify

- Update the certificate summary in `README.md` and the context/trust descriptions in `docs/image-releases.md` from two certificates to three.
- Document the Penpot default path, `BUILD_PENPOT_CERT_FILE`, all three manual-build context filenames, and the fingerprint change. Keep host trust and image trust distinct.
- Run `python3 -m unittest discover -s tests` and `bash build-all.sh --validate` during implementation. Record failures or unavailable prerequisites without bypassing checks.
- If a real build is performed during implementation, use `bash build-all.sh --build-only` with valid certificate inputs and existing credentials. Verify the installed Penpot file and trusted HTTPS access inside the resulting image; do not publish images as part of verification.
- Leave version updates, release notes, and implementation result recording to the implementation workflow.

## Acceptance criteria

- Both automated build modes capture and supply `penpot.lanCA.crt` with the same input rules as the existing certificates.
- All three certificate copies precede `update-ca-certificates`; npm inherits the resulting image trust.
- Penpot input changes affect the release fingerprint and trigger existing publication guards. Snapshots use captured bytes.
- Invalid Penpot inputs fail safely before external operations; offline validation succeeds without any certificate files.
- Tests and documentation cover all three certificates. No certificate files, credentials, TLS bypasses, host trust changes, or publication writes are introduced.

## Risks and decisions

- The new required input makes builds fail until callers provide a valid Penpot CA file. Do not download or commit certificates automatically.
- Adding a third certificate changes the aggregate release fingerprint. Use a new release version through the implementation workflow; never adopt or rewrite previous release evidence.
- Current-container access to `https://penpot.lan` already succeeds, but that does not prove a rebuilt image contains the requested certificate. Use fixture assertions and, when available, image-level verification.
- Existing input validation checks availability and size, not certificate syntax. Preserve that contract; valid CA contents remain the caller's responsibility.
