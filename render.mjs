// Streams master.html frames into ffmpeg (no PNG staging on disk).
// node render.mjs --seq 1 --w 1280 --out out/seq1-preview.mp4        full clip
// node render.mjs --seq 1 --w 960 --stills 0,60,240 --out out/stills  PNG stills only
import puppeteer from 'puppeteer-core'; import {spawn} from 'node:child_process'; import {mkdirSync, writeFileSync} from 'node:fs'; import path from 'node:path'; import {pathToFileURL} from 'node:url';
const a = Object.fromEntries(process.argv.slice(2).reduce((r, v, i, x) => (v.startsWith('--') && r.push([v.slice(2), x[i + 1]]), r), []));
const url = pathToFileURL(path.resolve('master.html')).href + `?render=1&seq=${a.seq || 1}&w=${a.w || 1280}&fps=${a.fps || 60}`;
const b = await puppeteer.launch({executablePath: process.env.CHROME, headless: true, protocolTimeout: 0, args: process.getuid?.() === 0 ? ['--no-sandbox'] : []}); const p = await b.newPage();   // Chrome refuses to run as root (Linux containers) with its sandbox on
p.on('pageerror', e => { console.error('PAGE', e.message); process.exit(1); });
await p.goto(url); await p.waitForFunction('window.__ready === true', {timeout: 0});
const [N, fps] = await p.evaluate(() => [window.__NDRAW, window.__fps]);
const png = async i => Buffer.from((await p.evaluate(i => window.__frame(i), i)).split(',')[1], 'base64');
if (a.stills) { mkdirSync(a.out, {recursive: true}); for (const s of a.stills.split(',').map(Number)) writeFileSync(path.join(a.out, String(s).padStart(5, '0') + '.png'), await png(Math.min(s, N - 1))); console.log('stills ->', a.out); }
else {
  mkdirSync(path.dirname(a.out), {recursive: true});
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', a.crf || '16', '-preset', 'slow', '-movflags', '+faststart', a.out], {stdio: ['pipe', 'inherit', 'inherit']});
  for (let i = 0; i < N; i++) { if (!ff.stdin.write(await png(i))) await new Promise(r => ff.stdin.once('drain', r)); if (i % 240 === 0) console.log('frame', i, '/', N); }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); console.log('done', N, 'frames @', fps, 'fps ->', a.out);
}
await b.close();
