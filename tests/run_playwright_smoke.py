"""Opt-in Docker integration checks. Never joins the real development network.

Run after building a client image: python3 tests/run_playwright_smoke.py --client-image IMAGE
Requires Docker Compose and network access for server/client package downloads.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]


def command(*args, timeout=180, check=True):
  result = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
  if check and result.returncode:
    raise RuntimeError(f"Command failed ({args[0]}): {result.stdout}\n{result.stderr}")
  return result


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--client-image", required=True)
  args = parser.parse_args()
  prefix = "task8-" + uuid.uuid4().hex[:10]
  network = prefix + "-network"
  health = (ROOT / "scripts/playwright-healthcheck.cjs").read_text() + "\nprobe().catch(() => process.exit(1));"
  server = json.loads(command("docker", "compose", "-f", str(ROOT / "compose/playwright-compose.yml"),
                              "config", "--format", "json").stdout)
  server["name"] = prefix + "-server"
  server["networks"]["development"]["name"] = network
  browser = server["services"]["playwright"]
  browser.pop("volumes", None)
  browser["healthcheck"]["test"] = ["CMD", "node", "-e", health.replace("$", "$$")]
  original_start = browser["command"]
  # Healthcheck source is inlined only for smoke tests on remote Docker daemons.
  browser["command"] = ["sh", "-c", "sleep 15; exec " + shlex.join(original_start)]
  configs = []
  with tempfile.TemporaryDirectory(prefix=prefix + "-", dir="/tmp/opencode") as temporary:
    directory = Path(temporary)

    def compose(config, *arguments, check=True, timeout=180):
      path = directory / (config["name"] + ".json")
      path.write_text(json.dumps(config))
      return command("docker", "compose", "-f", str(path), *arguments, check=check, timeout=timeout)

    def container(config, service):
      return compose(config, "ps", "-aq", service).stdout.strip()

    def execute(config, script, check=True, timeout=120):
      return compose(config, "exec", "-T", "client", "node", "-e", script, check=check, timeout=timeout)

    def make_client(suffix, attached=True):
      config = {"name": prefix + "-" + suffix, "services": {"client": {
        "image": args.client_image, "entrypoint": ["sleep"], "command": ["infinity"],
        "user": "1000:1000", "working_dir": "/home/container",
        "environment": {"PW_TEST_CONNECT_WS_ENDPOINT": "ws://playwright:3000/"},
      }}}
      if attached:
        config["networks"] = {"development": {"external": True, "name": network}}
        config["services"]["client"]["networks"] = ["development"]
      configs.append(config)
      compose(config, "up", "-d")
      command("docker", "cp", str(ROOT / "scripts"), container(config, "client") + ":/tmp/task8-scripts")
      return config

    configs.append(server)
    try:
      compose(server, "up", "-d")
      first = make_client("first")
      second = make_client("second")
      execute(first, "if (require('fs').existsSync('/home/container/.cache/ms-playwright')) throw new Error('Client unexpectedly contains local browsers');")
      wait_script = """
        const { chromium } = require('playwright');
        const { connectWithRetry } = require('/tmp/task8-scripts/playwright-connect.cjs');
        connectWithRetry(chromium.connect.bind(chromium), process.env.PW_TEST_CONNECT_WS_ENDPOINT)
          .then(browser => browser.close()).catch(error => { console.error(error.message); process.exitCode = 1; });
      """
      execute(first, wait_script)
      compose(server, "up", "-d", "--wait", "--wait-timeout", "120")
      execute(second, wait_script)
      compose(first, "exec", "-T", "client", "node", "/tmp/task8-scripts/playwright-connect.cjs")
      print("PASS: delayed start, healthy server, and two independent clients", flush=True)
      command("docker", "exec", container(server, "playwright"), "node", "-e", r"""
        const fs = require('fs');
        (async () => {
          for (let attempt = 0; attempt < 20; attempt++) {
            const sockets = ['/proc/net/tcp', '/proc/net/tcp6'].flatMap(path => fs.readFileSync(path, 'utf8').trim().split('\n').slice(1));
            if (!sockets.some(line => { const parts = line.trim().split(/\s+/); return parts[1].endsWith(':0BB8') && parts[3] === '01'; })) return;
            await new Promise(resolve => setTimeout(resolve, 100));
          }
          throw new Error('Readiness connections remained established');
        })().catch(error => { console.error(error.message); process.exitCode = 1; });
      """)

      # Serve local content inside the second client, without host ports/mounts.
      command("docker", "exec", "-d", container(second, "client"), "node", "-e",
              "require('http').createServer((q,r)=>r.end('<title>remote-browser-ok</title>')).listen(8080,'0.0.0.0')")
      target = container(second, "client")
      command("docker", "network", "disconnect", network, target)
      command("docker", "network", "connect", "--alias", "task8-target", network, target)
      browsers = """
        const pw = require('playwright');
        (async () => {
          for (const engine of ['chromium', 'firefox', 'webkit']) {
            const browser = await pw[engine].connect(process.env.PW_TEST_CONNECT_WS_ENDPOINT, { timeout: 5000 });
            try {
              const page = await browser.newPage();
              await page.goto('http://task8-target:8080', { timeout: 10000 });
              if (await page.title() !== 'remote-browser-ok') throw new Error('wrong target page');
              console.log('PASS remote ' + engine);
            } finally { await browser.close(); }
          }
        })().catch(error => { console.error(error.message); process.exitCode = 1; });
      """
      print(execute(first, browsers).stdout, flush=True)
      test_source = "const { test, expect } = require('@playwright/test'); test('remote endpoint', async ({page}) => { await page.goto('http://task8-target:8080'); await expect(page).toHaveTitle('remote-browser-ok'); });"
      setup = "require('fs').writeFileSync('/tmp/task8.spec.js', " + json.dumps(test_source) + ");"
      execute(first, setup)
      # Keep package resolution in /home/container while discovering the temporary test.
      command("docker", "exec", container(first, "client"), "sh", "-ec",
              "cp /tmp/task8.spec.js /home/container/task8.spec.js; ./node_modules/.bin/playwright test task8.spec.js --workers=1 --timeout=15000", timeout=90)
      print("PASS: Playwright Test endpoint environment variable", flush=True)
      detached = make_client("detached", attached=False)
      execute(detached, "require('dns').lookup('playwright', error => process.exit(error ? 0 : 1))")
      print("PASS: unattached client cannot resolve the browser service", flush=True)

      # Verify a known incompatible minor version, installed only in a disposable container.
      command("docker", "exec", container(first, "client"), "sh", "-ec",
              "mkdir /tmp/task8-incompatible; cd /tmp/task8-incompatible; PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --save-exact playwright@1.63.0", timeout=180)
      incompatible = wait_script.replace("require('playwright')", "require('/tmp/task8-incompatible/node_modules/playwright')")
      mismatch = execute(first, incompatible, check=False, timeout=20)
      if mismatch.returncode == 0 or not any(value in mismatch.stderr.lower() for value in ("428", "version mismatch", "precondition required")):
        raise AssertionError("Incompatible-client failure was not a version rejection: " + mismatch.stderr)
      print("PASS: incompatible 1.63.0 client rejected by 1.64.1 server\n" + mismatch.stderr, flush=True)

      compose(server, "stop", "playwright")
      failed = execute(first, wait_script, check=False, timeout=75)
      if failed.returncode == 0 or "No local browser fallback" not in failed.stderr:
        raise AssertionError("Unavailable-server failure was not bounded/diagnostic: " + failed.stderr)
      print("PASS: unavailable server fails within client deadline\n" + failed.stderr, flush=True)
      browser["command"] = ["sh", "-c", "echo 'synthetic package/start failure' >&2; exit 1"]
      failure_start = time.monotonic()
      failed_start = compose(server, "up", "-d", "--wait", "--wait-timeout", "120", check=False)
      if failed_start.returncode == 0 or time.monotonic() - failure_start > 125:
        raise AssertionError("Failed server startup did not fail within its budget")
      print("PASS: synthetic package/start failure stops startup", flush=True)
    finally:
      for config in reversed(configs):
        result = compose(config, "down", "--remove-orphans", check=False)
        if result.returncode:
          print("Cleanup requires inspection for " + config["name"] + ": " + result.stderr, flush=True)


if __name__ == "__main__":
  main()
