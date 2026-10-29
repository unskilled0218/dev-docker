# Remote Playwright browsers

- [Remote Playwright browsers](#remote-playwright-browsers)
  - [Architecture and versions](#architecture-and-versions)
  - [Start and stop](#start-and-stop)
  - [Connect another container](#connect-another-container)
  - [Run tests and library code](#run-tests-and-library-code)
  - [Troubleshooting and trust](#troubleshooting-and-trust)
  - [Verification](#verification)

## Architecture and versions

Tests and application tools run in client containers; Chromium, Firefox, and WebKit run in the separate official `mcr.microsoft.com/playwright:v1.64.1-noble` container. Image, server package, and client packages must all use `1.64.1`. The image provides browsers and system libraries, not the server JavaScript package; the pinned `npx` startup downloads that package on a cold start and needs npm registry access. No custom browser image is built or published.

The Compose image is pinned to the verified registry digest `sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`. Update this digest together with the tag and matching package versions when upgrading.

The base remains Ubuntu and retains the external setup script. It no longer starts an OpenCode server automatically or sets a default server password; application Compose no longer publishes its host port. The npm development image now provides only `@playwright/test@1.64.1` and its client dependencies, without local browsers or browser-specific libraries. Base does not contain Node or the Playwright client: choose the npm image or install the matching package in your own project container. Existing `.launch()` workflows must migrate explicitly; the endpoint variable does not redirect arbitrary library calls or configure every MCP/tool integration.

## Start and stop

Run from the repository root. Docker Compose must support `up --wait --wait-timeout`.

```bash
docker compose -f compose/playwright-compose.yml up -d --wait --wait-timeout 120
docker compose -f compose/docker-compose.yml up -d
```

The browser project owns the explicitly named `development` bridge network. Start it before any client project. If an unrelated network already has that name, stop and resolve ownership; do not delete or silently adopt it. The browser server has no host-published port, project directory, Docker socket, or credential mounts. Its only bind mount is the read-only readiness script, so keep `scripts/playwright-healthcheck.cjs` beside this repository's Compose directory when deploying the server file.

Bind sources must exist on the Docker daemon host, not just inside the container running Compose. For a remote daemon or a mounted Docker socket, deploy the repository at a daemon-visible path or override the healthcheck script's source path explicitly. A successful `compose config` check does not prove the daemon can read that path.

Health checks complete a WebSocket handshake without launching browsers, every five seconds, with a three-second timeout, 45-second startup grace period, and 12 retries. Startup waits at most 120 seconds. If it fails, do not start clients: inspect server health and logs, fix registry/network/startup errors, and retry. Independent Compose projects cannot use cross-project `depends_on` to wait for this service. Health can change after startup; clients still need connection timeouts.

Stop all attached client projects before the server project:

```bash
docker compose -f compose/docker-compose.yml down
docker compose -f compose/playwright-compose.yml down
```

Stop other attached clients separately. Do not remove networks or containers owned by other users.

## Connect another container

Use a separate Compose project name for each independent client:

```yaml
name: example-browser-client
services:
  client:
    image: git.lan/dev/npm:latest
    command: ["sleep", "infinity"]
    environment:
      PW_TEST_CONNECT_WS_ENDPOINT: ws://playwright:3000/
    networks:
      - development
networks:
  development:
    external: true
    name: development
```

Or attach an existing container:

```bash
docker network connect development <container>
```

Use `ws://playwright:3000/` inside attached containers, not `localhost`. Client and server do not need shared project mounts. Use unique application service names/network aliases across projects to prevent ambiguous DNS.

## Run tests and library code

Inside a client project with Node installed:

```bash
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --save-dev --save-exact @playwright/test@1.64.1
export PW_TEST_CONNECT_WS_ENDPOINT=ws://playwright:3000/
node /path/to/dev-docker/scripts/playwright-connect.cjs
npx playwright test
```

Run the connection script from the directory containing your project's package dependencies. It resolves the client package from that directory, retries connections for at most 60 seconds with five-second individual connection limits and two-second retry delays, stops immediately on known version incompatibility, and closes its readiness browser before exiting. Its close operation has a separate five-second limit. Errors identify the endpoint and last failure with URL credentials redacted; there is no local browser fallback.

Configure a finite timeout for actual Playwright Test connections too:

```js
const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  use: {
    connectOptions: {
      wsEndpoint: process.env.PW_TEST_CONNECT_WS_ENDPOINT,
      timeout: 5000,
    },
    baseURL: 'http://my-application:8080',
  },
});
```

For direct library usage, install `playwright@1.64.1` with browser downloads disabled and connect explicitly. The helper returns the actual connection so library code can reuse it rather than performing an unnecessary readiness launch:

```js
const { chromium } = require('playwright');
const { connectWithRetry } = require('/path/to/dev-docker/scripts/playwright-connect.cjs');
async function main() {
  const browser = await connectWithRetry(chromium.connect.bind(chromium), 'ws://playwright:3000/');
  try {
    const page = await browser.newPage();
    await page.goto('http://my-application:8080');
    console.log(await page.title());
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
```

## Troubleshooting and trust

```bash
docker compose -f compose/playwright-compose.yml ps
docker compose -f compose/playwright-compose.yml logs --tail 50 playwright
```

A missing network means the server project has not created it. DNS errors suggest network attachment or alias problems. Connection refusal can indicate an unhealthy server or a cold package download; the startup command and client helper fail within their budgets rather than wait indefinitely. Inspect logs privately before sharing them. A version mismatch or HTTP 428 requires matching the client package to server version `1.64.1`, not changing DNS or increasing timeouts.

An abrupt restart during package download can leave a disposable server's npm cache incomplete and produce `EINTEGRITY`. Stop active browser clients before recreating only the browser service with `docker compose -f compose/playwright-compose.yml up -d --force-recreate --wait --wait-timeout 120`. This discards its container-local cache; do not disable integrity checking or delete shared host caches.

Browsers reach applications from the server container: bind your application to `0.0.0.0` and use `http://<unique-application-alias>:<port>`. Client `localhost`, local files, credentials, and certificate trust do not automatically transfer to the server. Configure explicit limited mounts for workflows that actually require server-local files. Internal HTTPS targets need browser-side CA trust; do not disable TLS verification globally.

Only attach trusted containers: any container on this network can control the browser service. It is a development/test service, not a public browser endpoint or an isolation boundary for untrusted websites. The server runs as `pwuser` with bounded shared memory, without privileged mode, extra capabilities, host IPC, or a custom sandbox override. Workloads requiring Chromium sandbox hardening need the official Playwright seccomp guidance and separate validation.

## Verification

```bash
python3 -B -m unittest discover -s tests -v
node --test tests/test_playwright.cjs
python3 tests/run_playwright_smoke.py --client-image git.lan/dev/npm:latest
docker compose -f compose/playwright-compose.yml config --quiet
docker compose -f compose/docker-compose.yml config --quiet
```

JavaScript tests use Node's built-in runner and local fake servers, without downloading Playwright or browsers. The opt-in Python smoke runner uses Docker, the built npm client image, and registry access; it verifies both client approaches, all three remote browsers, two independent client projects, application alias routing, an unattached client, delayed/failed startup, and an incompatible client. It uses unique test-owned network/project names and inlines the healthcheck source for remote Docker daemons; it does not mutate a user's running `development` network. Offline assertions alone do not prove browser runtime behavior. See the task implementation record for checks actually executed.
