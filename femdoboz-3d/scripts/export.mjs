import { createRequire } from 'module';
const require = createRequire('/opt/node22/lib/node_modules/');
let pw; try { pw = require('playwright'); } catch { pw = require('/root/node-tools/node_modules/playwright'); }
const [,, url, outDir, ...ids] = process.argv;
const browser = await pw.chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, acceptDownloads: true });
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.type(), m.text().slice(0, 300)); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto(url);
await page.waitForFunction(() => /gomb/.test(document.getElementById('status')?.textContent || ''), null, { timeout: 180000 });
console.log('status:', await page.textContent('#status'));
console.log('finishes:', await page.$$eval('#opts .opt', (bs) => bs.map((b) => b.dataset.id).join(',')));
for (const id of ids) {
  await page.click(`#opts .opt[data-id="${id}"]`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${outDir}/${id}.png` });
  const [dl] = await Promise.all([
    page.waitForEvent('download', { timeout: 300000 }),
    page.evaluate(() => document.querySelector('three-d-stage')._exportGlb()),
  ]);
  await dl.saveAs(`${outDir}/${id}.glb`);
  console.log('exported', id);
}
await browser.close();
