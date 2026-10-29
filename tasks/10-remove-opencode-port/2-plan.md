# plan

- [plan](#plan)
  - [scope](#scope)
  - [Implementation Plan](#implementation-plan)
    - [Summary](#summary)
    - [1. Remove the obsolete port checks](#1-remove-the-obsolete-port-checks)
    - [2. Update current documentation](#2-update-current-documentation)
    - [3. Verify and record](#3-verify-and-record)
  - [Acceptance Criteria](#acceptance-criteria)
  - [Risks And Decisions](#risks-and-decisions)

## scope

Remove active OpenCode port 4096-specific checks and references. Preserve unrelated uses of `4096`, historical task and release records, existing Dockerfile and Compose behavior, and `todo.md`.

## Implementation Plan

### Summary

Remove the obsolete port-specific test helper and its assertions rather than replacing them with another port policy. Keep Playwright and network regression coverage intact.

### 1. Remove the obsolete port checks

- In `tests/test_playwright.py`, remove `app_source_has_4096_port`, its call in `test_independent_clients_use_the_owned_shared_network`, and `test_port_check_rejects_alternative_mappings`.
- Retain the other assertions for image versions, Playwright server privacy, network attachment, endpoint, and protected mounts. Keep `re`, which is still used by the version and browser-install checks.
- Do not add a replacement restriction on application ports or modify `compose/docker-compose.yml` or the Dockerfiles. The previous review warning concerned the removed helper and needs no replacement port-specific test.

### 2. Update current documentation

- In `README.md`, `docs/playwright.md`, and `docs/image-releases.md`, remove references to the removed OpenCode host port while keeping accurate information about the server command and password removal and the Playwright setup.
- Preserve earlier release notes and task records as historical documents. Do not delete unrelated `4096` byte or buffer limits in tests and scripts.
- Follow the existing version and release-note convention when implementing; describe this test and documentation cleanup without implying a runtime port change.

### 3. Verify and record

- Run `python3 -B -m unittest discover -s tests -p test_playwright.py -v` and the full Python suite with enough time for its previously observed roughly ten-minute runtime. Run `bash -n build-all.sh`, `bash build-all.sh --validate`, and `git diff --check`.
- Search active source, tests, and current documentation for port 4096 references, classifying any remaining numeric matches by context. Verify unrelated buffer and token-size uses remain intact. Do not treat historical task and release notes as active configuration.
- If Docker Compose is available, validate both Compose files without starting containers. Record exact results, skipped checks, and any prerequisites in `tasks/10-remove-opencode-port/4-implemented.md`. No image build or publication is required for this test and documentation cleanup.

## Acceptance Criteria

- No active OpenCode port 4096-specific test or documentation reference remains, and no replacement application-port policy is introduced.
- Existing Playwright network, endpoint, image, and mount assertions remain and the focused tests pass.
- Dockerfile and Compose runtime behavior, unrelated numeric uses, and historical task and release records remain unchanged.
- Verification results and any limitations are recorded accurately.

## Risks And Decisions

- Removing the port check intentionally means the suite no longer prevents future use of that port. This matches the requested removal rather than asserting a new policy.
- Historical records may continue to describe earlier port behavior. They are not instructions for the current deployment.
