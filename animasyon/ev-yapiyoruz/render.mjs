// Renders scene/ frames with headless Chromium.
// node render.mjs --out frames [--from 0 --to 900] [--workers 4] [--times 1.0,4.5] [--scale 0.5]
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require('playwright'); } catch { playwright = require('/opt/node22/lib/node_modules/playwright'); }

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const tl = JSON.parse(fs.readFileSync(path.join(ROOT, 'timeline.json'), 'utf8'));
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? a.concat([[v.slice(2), arr[i + 1]]]) : a), []));
const out = path.resolve(args.out || 'frames');
fs.mkdirSync(out, { recursive: true });
const scale = +(args.scale || 1);
const w = Math.round(tl.width * scale), h = Math.round(tl.height * scale);
const total = Math.round(tl.duration * tl.fps);

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, r));
const url = `http://127.0.0.1:${server.address().port}/scene/index.html?w=${w}&h=${h}`;

let jobs;
if (args.times) jobs = args.times.split(',').map(s => ({ t: +s, name: `t_${(+s).toFixed(2)}.jpg` }));
else {
  const from = +(args.from || 0), to = +(args.to || total);
  jobs = [];
  for (let f = from; f < to; f++) jobs.push({ t: f / tl.fps, name: `f_${String(f).padStart(4, '0')}.jpg` });
}
jobs = jobs.filter(j => args.force || !fs.existsSync(path.join(out, j.name)));

const browser = await playwright.chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const workers = Math.max(1, +(args.workers || 1));
let next = 0, done = 0;
const t0 = Date.now();
await Promise.all(Array.from({ length: workers }, async () => {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  page.on('pageerror', e => console.error('pageerror', e.message));
  page.on('console', m => { if (m.type() === 'error') console.error('console', m.text()); });
  await page.goto(url);
  await page.evaluate(() => window.ready);
  while (next < jobs.length) {
    const j = jobs[next++];
    const data = await page.evaluate(t => window.renderAt(t), j.t);
    fs.writeFileSync(path.join(out, j.name), Buffer.from(data.split(',')[1], 'base64'));
    if (++done % 30 === 0 || done === jobs.length) console.log(`${done}/${jobs.length}  ${((Date.now() - t0) / done).toFixed(0)} ms/frame`);
  }
  await page.close();
}));
await browser.close();
server.close();
