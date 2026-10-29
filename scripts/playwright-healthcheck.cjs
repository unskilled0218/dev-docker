const http = require('node:http');
const crypto = require('node:crypto');

// A handshake without Playwright initialization does not launch a browser.
function probe(endpoint = 'http://127.0.0.1:3000/', timeout = 2000) {
  return new Promise((resolve, reject) => {
    const key = crypto.randomBytes(16).toString('base64');
    const expected = crypto.createHash('sha1')
      .update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
    const request = http.get(endpoint, { headers: {
      Connection: 'Upgrade', Upgrade: 'websocket',
      'Sec-WebSocket-Version': '13', 'Sec-WebSocket-Key': key,
    } });
    const timer = setTimeout(() => request.destroy(new Error('WebSocket readiness timed out')), timeout);
    request.on('upgrade', (response, socket) => {
      clearTimeout(timer);
      socket.destroy();
      if (response.statusCode === 101 && response.headers['sec-websocket-accept'] === expected)
        resolve();
      else
        reject(new Error('Invalid WebSocket readiness handshake'));
    });
    request.on('response', response => {
      clearTimeout(timer);
      response.destroy();
      reject(new Error(`WebSocket readiness returned HTTP ${response.statusCode}`));
    });
    request.on('error', error => {
      clearTimeout(timer);
      reject(error);
    });
  });
}

module.exports = { probe };
if (require.main === module)
  probe().catch(error => { console.error(error.message); process.exitCode = 1; });
