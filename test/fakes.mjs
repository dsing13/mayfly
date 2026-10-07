// In-memory stand-ins for the Cloudflare bindings, shared by the tests and
// the local dev server.

// Cloudflare-only API used by the admin auth check.
if (!crypto.subtle.timingSafeEqual) {
  crypto.subtle.timingSafeEqual = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
}

export class FakeKV {
  constructor() { this.m = new Map(); this.writes = 0; }
  async get(k, opts) {
    const e = this.m.get(k); if (!e) return null;
    const type = typeof opts === 'string' ? opts : opts && opts.type;
    return type === 'arrayBuffer' ? e.v : (typeof e.v === 'string' ? e.v : new TextDecoder().decode(e.v));
  }
  async getWithMetadata(k, opts) {
    const e = this.m.get(k);
    return e ? { value: await this.get(k, opts), metadata: e.meta || null } : { value: null, metadata: null };
  }
  async put(k, v, opts = {}) {
    this.writes++;
    if (ArrayBuffer.isView(v)) v = v.buffer.slice(v.byteOffset, v.byteOffset + v.byteLength);
    this.m.set(k, { v, meta: opts.metadata, ttl: opts.expirationTtl });
  }
  async delete(k) { this.m.delete(k); }
  async list({ prefix = '' } = {}) {
    const keys = [...this.m.entries()].filter(([k]) => k.startsWith(prefix)).sort()
      .map(([name, e]) => (e.meta ? { name, metadata: e.meta } : { name }));
    return { keys, list_complete: true };
  }
}

// Moderation always passes; chat replies come from `replies` (tests) or
// from `script(messages)` (dev server).
export class FakeAI {
  constructor(script) { this.replies = []; this.calls = []; this.fail = null; this.script = script; }
  async run(model, input) {
    this.calls.push(model);
    if (this.fail) throw new Error(this.fail);
    if (model.includes('guard')) return { response: 'safe' };
    if (model.includes('vision')) return { response: 'SAFE' };
    const text = input.messages.at(-1).content;
    if (typeof text === 'string' && text.startsWith('You are a content moderator')) return { response: 'OK' };
    if (typeof text === 'string' && text.startsWith('From the conversation above')) return { response: '{}' };
    if (this.replies.length) return { response: this.replies.shift() };
    return { response: this.script ? this.script(input.messages) : 'What are we making a site for?' };
  }
}

export class FakeEvents { constructor() { this.points = []; } writeDataPoint(p) { this.points.push(p); } }
