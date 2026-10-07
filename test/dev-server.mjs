// Local dev server: the real worker with in-memory KV and a scripted Nova.
//   npm run dev   ->  http://localhost:8787  (landing)  and  /start  (chat)
// Pages and images are re-read from site/ on every request, so edits show up
// on reload. The scripted Nova asks a few fixed questions, then finishes the
// order once you send an email address. Nothing leaves your machine.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import worker from '../worker/mayfly-router.js';
import { FakeKV, FakeAI, FakeEvents } from './fakes.mjs';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const PORT = Number(process.env.PORT || 8787);

const QUESTIONS = [
  'Nice. When is it, and where?',
  'Got it. Can you add a photo or two? Use the camera button.',
  'How long should the page stay up: 1 day free, 2 days for $1, 7 days for $1.50, 30 days for $5, or a year for $50?',
  'Last thing: what email should I send the link to?',
];
function script(messages) {
  const userTurns = messages.filter(m => m.role === 'user' && !String(m.content).startsWith('[system')).length;
  const last = String(messages.filter(m => m.role === 'user' && !String(m.content).startsWith('[system')).at(-1)?.content || '');
  const email = last.match(/[^@\s]+@[^@\s]+\.[^@\s]+/);
  if (email) {
    return JSON.stringify({ done: true, theme: 'sell', tier: 'week', email: email[0], photos: 'none',
      fields: { items: 'Dresser $120, bikes $35', location: '2214 Morningside Dr', contact: '704-555-0198' },
      details: 'A three-household yard sale on Saturday morning with furniture and bikes.', tone: 'friendly' });
  }
  return QUESTIONS[Math.min(userTurns - 1, QUESTIONS.length - 1)];
}

const env = { SITES: new FakeKV(), AI: new FakeAI(script), EVENTS: new FakeEvents(), ADMIN_TOKEN: 'dev-token' };

async function syncSite() {
  await env.SITES.put('page:_landing', fs.readFileSync(path.join(ROOT, 'site/index.html'), 'utf8'));
  await env.SITES.put('page:_start', fs.readFileSync(path.join(ROOT, 'site/start.html'), 'utf8'));
  const dir = path.join(ROOT, 'site/img');
  if (fs.existsSync(dir)) {
    for (const f of fs.readdirSync(dir)) {
      const ct = f.endsWith('.webp') ? 'image/webp' : f.endsWith('.png') ? 'image/png' : 'image/jpeg';
      await env.SITES.put('img:mayfly/' + f, fs.readFileSync(path.join(dir, f)), { metadata: { ct, exp: 0 } });
    }
  }
}

http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && !req.url.startsWith('/api/')) await syncSite();
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const body = chunks.length ? Buffer.concat(chunks) : undefined;
    const request = new Request('http://localhost' + req.url, {
      method: req.method,
      headers: { ...req.headers, 'cf-connecting-ip': '127.0.0.1' },
      body: ['GET', 'HEAD'].includes(req.method) ? undefined : body,
    });
    const r = await worker.fetch(request, env);
    const headers = Object.fromEntries(r.headers);
    delete headers['strict-transport-security'];
    res.writeHead(r.status, headers);
    res.end(Buffer.from(await r.arrayBuffer()));
    const ev = env.EVENTS.points.at(-1);
    if (ev) console.log('event:', ev.blobs[0], ev.blobs[1] || '', ev.blobs[9] || '');
    env.EVENTS.points.length = 0;
  } catch (e) {
    console.error(e);
    res.writeHead(500); res.end('dev server error');
  }
}).listen(PORT, '127.0.0.1', () => console.log(`Mayfly dev server on http://localhost:${PORT}`));
