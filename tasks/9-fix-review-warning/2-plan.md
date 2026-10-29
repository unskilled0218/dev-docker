# plan

- [plan](#plan)
  - [scope](#scope)
  - [Implementation Plan](#implementation-plan)
    - [Summary](#summary)
    - [1. Correct the regression test](#1-correct-the-regression-test)
    - [2. Correct documentation and the verification record](#2-correct-documentation-and-the-verification-record)
    - [3. Verify and record results](#3-verify-and-record-results)
  - [Acceptance Criteria](#acceptance-criteria)
  - [Risks And Decisions](#risks-and-decisions)

## scope

Address the warning in `tasks/8-use-official-images/5-code-review.md`. Preserve the intentional removal of the OpenCode server command, server password, and Compose port mapping. Do not redesign OpenCode, the Playwright service, or release tooling, and do not touch `todo.md`.

## Implementation Plan

### Summary

Update the stale regression assertion and current documentation, clarify which earlier verification applies to an older image, and run available checks against the final changes.

### 1. Correct the regression test

- Update `tests/test_playwright.py` to remove the requirement for `4096:4096`. The intended contract is that the app does not publish container port 4096, regardless of host port or Compose syntax; other ports are not prohibited by this task. Keep an offline, dependency-free check for the current Compose source and preserve the network, image, and protected-mount assertions. Add negative fixture cases for an alternative host port and long syntax so the offline check rejects both without changing the real Compose file.
- When Docker Compose is available, inspect `docker compose -f compose/docker-compose.yml config --format json` and assert that the normalized `app` service has no published port targeting 4096. Exercise the same validation against a disposable test configuration containing an alternative mapping to target 4096, and require it to fail. Never start that configuration. Report this normalized check as skipped if Compose is unavailable; the offline source check is not a complete YAML parser.
- Keep the current Dockerfile and Compose runtime behavior unchanged; do not restore the OpenCode server or port to satisfy the test.

### 2. Correct documentation and the verification record

- Correct claims that base or OpenCode behavior is unchanged in `README.md`, `docs/playwright.md`, `docs/image-releases.md`, and `docs/releases/0.1.13.md` where applicable. State precisely that the automatic server command, default server password, and host port mapping were removed; do not imply OpenCode itself or the setup script was removed.
- Update `tasks/8-use-official-images/4-implemented.md` with a clearly dated correction or annotations. Preserve historical test results but identify the revision or older images they covered, and remove any implication that they verify the final base image, authentication, or port behavior.
- Leave the previous goal, plan, and review as historical records. Record new results in this task's implementation record rather than presenting earlier runs as current verification.

### 3. Verify and record results

- Run `python3 -B -m unittest discover -s tests -p test_playwright.py -v`, then the full Python suite with sufficient time for its previously recorded roughly ten-minute runtime. Run `node --test tests/test_playwright.cjs` if Node is available, plus `bash -n build-all.sh`, `bash build-all.sh --validate`, and `git diff --check`.
- Validate both Compose configurations if Docker Compose and required inputs are available. Do not start the normal application stack or publish images.
- If prerequisites permit, build the final base and npm images without publishing and run isolated smoke checks against those newly built images. Do not claim that cached older images prove the final behavior. Avoid host credential or socket mounts and clean up only test-owned resources.
- Record commands, results, image provenance, and any unavailable prerequisites or skipped runtime checks in `tasks/9-fix-review-warning/4-implemented.md`. Do not claim a full suite or build passed if it timed out or was blocked.

## Acceptance Criteria

- The focused test passes without requiring port 4096, rejects representative alternate mappings to that target, and still checks the shared network and protected mounts. When Compose is available, normalized configuration validation confirms app container port 4096 is not published and rejects the negative fixture.
- Current documentation accurately describes the intentional OpenCode server and port removal; prior verification is clearly scoped to the images and revision actually tested.
- The final branch's available checks are recorded honestly, with blocked or skipped verification identified explicitly.
- No OpenCode server command, password, or host port is restored, and Playwright behavior is unchanged.

## Risks And Decisions

- The external setup script still installs tools; removing server startup does not establish that OpenCode is absent. Avoid claims about behavior not verified from the final image.
- Fresh builds may be blocked by unreadable certificate inputs or other prerequisites. Do not change permissions or bypass safety checks; record the blocker and request the necessary access.
- Historical plan and review documents describe decisions and observations at their respective times. Correct misleading implementation-record claims without rewriting that history.
