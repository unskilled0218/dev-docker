const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const crypto = require('node:crypto');
const { probe } = require('../scripts/playwright-healthcheck.cjs');
const { connectWithRetry, redact } = require('../scripts/playwright-connect.cjs');

async function serverFixture(t, upgrade) {
  const server = http.createServer((request, response) => response.end('not a WebSocket'));
  const sockets = new Set();
  server.on('connection', socket => {
    sockets.add(socket);
    socket.on('close', () => sockets.delete(socket));
  });
  if (upgrade)
    server.on('upgrade', upgrade);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => {
    for (const socket of sockets) socket.destroy();
    await new Promise(resolve => server.close(resolve));
  });
  return `http://127.0.0.1:${server.address().port}/`;
}

test('readiness completes and closes a valid WebSocket handshake', { timeout: 2000 }, async t => {
  let closed;
  const disconnected = new Promise(resolve => { closed = resolve; });
  const endpoint = await serverFixture(t, (request, socket) => {
    const accept = crypto.createHash('sha1').update(request.headers['sec-websocket-key'] +
      '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
    socket.on('end', () => socket.end());
    socket.on('close', closed);
    socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
  });
  await probe(endpoint, 500);
  await disconnected;
});

test('an HTTP response alone is not readiness', async t => {
  await assert.rejects(probe(await serverFixture(t), 500), /HTTP 200/);
});

test('an invalid WebSocket accept key is not readiness', async t => {
  const endpoint = await serverFixture(t, (request, socket) => {
    socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: invalid\r\n\r\n');
  });
  await assert.rejects(probe(endpoint, 500), /Invalid WebSocket/);
});

test('a stalled handshake fails within its own timeout', async t => {
  const endpoint = await serverFixture(t, () => {});
  await assert.rejects(probe(endpoint, 30), /timed out/);
});

test('a refused connection fails without waiting for the full deadline', async () => {
  const server = http.createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const endpoint = `http://127.0.0.1:${server.address().port}/`;
  await new Promise(resolve => server.close(resolve));
  await assert.rejects(probe(endpoint, 500), /ECONNREFUSED/);
});

test('a delayed server is retried and the successful browser is returned', async () => {
  let time = 0;
  let attempts = 0;
  const browser = { close: async () => {} };
  const result = await connectWithRetry(async (endpoint, options) => {
    assert.equal(endpoint, 'ws://playwright:3000/');
    assert.equal(options.timeout, 5000);
    if (++attempts < 3) throw new Error('ECONNREFUSED');
    return browser;
  }, 'ws://playwright:3000/', { now: () => time, sleep: async ms => { time += ms; } });
  assert.equal(result, browser);
  assert.equal(attempts, 3);
  assert.equal(time, 4000);
});

test('an unavailable server consumes a bounded deadline and redacts credentials', async () => {
  let time = 0;
  const endpoint = 'ws://user:secret@playwright:3000/';
  await assert.rejects(connectWithRetry(async (url, options) => {
    assert.ok(options.timeout > 0 && options.timeout <= 5000);
    time += options.timeout;
    throw new Error(`failed ${url}`);
  }, endpoint, { now: () => time, sleep: async ms => { time += ms; }, deadlineMs: 8000 }), error => {
    assert.equal(time, 8000);
    assert.match(error.message, /after 8000ms/);
    assert.match(error.message, /health\/logs/);
    assert.match(error.message, /No local browser fallback/);
    assert.ok(!error.message.includes('secret'));
    return true;
  });
});

test('a version mismatch fails immediately instead of retrying', async () => {
  let attempts = 0;
  await assert.rejects(connectWithRetry(async () => {
    attempts++;
    throw new Error('WebSocket error: Unexpected server response: 428');
  }, 'ws://playwright:3000/', { sleep: async () => assert.fail('must not retry') }), /matching client\/server versions/);
  assert.equal(attempts, 1);
});

test('an exhausted deadline never starts a zero-timeout connection', async () => {
  await assert.rejects(connectWithRetry(async () => assert.fail('must not connect'),
    'ws://playwright:3000/', { deadlineMs: 0 }), /No connection attempt completed/);
});

test('credential redaction preserves endpoints without leaking userinfo', () => {
  assert.equal(redact('ws://a:b@server/ https://x:y@host/'),
    'ws://[redacted]@server/ https://[redacted]@host/');
});
