// Checks that each clip's last frame is byte-identical to the next clip's first frame.
// Each clip gets its own page, as in a real render, and its last frame is drawn after a spread of earlier frames,
// so any drawing state that leaks from one frame into the next shows up as a mismatch.
// node check-seams.mjs --w 1280
import puppeteer from 'puppeteer-core'; import path from 'node:path'; import {pathToFileURL} from 'node:url';
const a = Object.fromEntries(process.argv.slice(2).reduce((r, v, i, x) => (v.startsWith('--') && r.push([v.slice(2), x[i + 1]]), r), []));
const PAIRS = [[1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7]];
const b = await puppeteer.launch({executablePath: process.env.CHROME, headless: true, protocolTimeout: 0, args: process.getuid?.() === 0 ? ['--no-sandbox'] : []});
async function frames(seq, which) {
  const p = await b.newPage(); p.on('pageerror', e => { console.error('PAGE', e.message); process.exit(1); });
  await p.goto(pathToFileURL(path.resolve('master.html')).href + `?render=1&seq=${seq}&w=${a.w || 1280}&fps=${a.fps || 60}`);
  await p.waitForFunction('window.__ready === true', {timeout: 0});
  const png = await p.evaluate(which => {
    const N = window.__NDRAW, list = which === 'first' ? [0] : [0, N >> 2, N >> 1, (3 * N) >> 2, N - 2, N - 1];
    let out; for (const i of list) out = window.__frame(i); return out;
  }, which);
  await p.close(); return png;
}
let ok = true;
for (const [s0, s1] of PAIRS) {
  const same = (await frames(s0, 'last')) === (await frames(s1, 'first'));
  console.log(`${s0} -> ${s1}: ${same ? 'identical' : 'DIFFERENT'}`); ok &&= same;
}
await b.close(); process.exit(ok ? 0 : 1);
