const { performance } = require('node:perf_hooks');
const { setTimeout: sleep } = require('node:timers/promises');

function redact(value) {
  return String(value).replace(/\b(wss?|https?):\/\/[^\s/]*@/gi, '$1://[redacted]@');
}

async function connectWithRetry(connect, endpoint, options = {}) {
  const now = options.now || (() => performance.now());
  const pause = options.sleep || sleep;
  const started = now();
  const deadline = started + (options.deadlineMs ?? 60000);
  let lastError = new Error('No connection attempt completed');
  while (true) {
    const remainingAttempt = deadline - now();
    if (remainingAttempt <= 0)
      break;
    try {
      return await connect(endpoint, { timeout: Math.max(1, Math.min(5000, remainingAttempt)) });
    } catch (error) {
      lastError = error;
      // Playwright rejects incompatible protocol versions with HTTP 428.
      if (/version mismatch|precondition required|HTTP[^\n]*428|unexpected server response: 428/i.test(error.message))
        break;
      const remaining = deadline - now();
      if (remaining > 0)
        await pause(Math.min(2000, remaining));
    }
  }
  throw new Error(redact(`Cannot connect to Playwright at ${endpoint} after ${Math.round(now() - started)}ms: ${lastError.message}. Inspect server health/logs, network attachment, and matching client/server versions. No local browser fallback.`));
}

module.exports = { connectWithRetry, redact };
if (require.main === module) {
  const endpoint = process.env.PW_TEST_CONNECT_WS_ENDPOINT || 'ws://playwright:3000/';
  const { createRequire } = require('node:module');
  const { resolve } = require('node:path');
  const { chromium } = createRequire(resolve('package.json'))('@playwright/test');
  connectWithRetry(chromium.connect.bind(chromium), endpoint)
    .then(async browser => {
      const timer = setTimeout(() => { console.error('Timed out closing readiness browser'); process.exit(1); }, 5000);
      try { await browser.close(); } finally { clearTimeout(timer); }
      console.log(`Playwright ready at ${redact(endpoint)}`);
    })
    .catch(error => { console.error(redact(error.message)); process.exitCode = 1; });
}
