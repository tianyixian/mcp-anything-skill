// Fixed notes workflow. No caller-provided selectors, URLs, code or browser profile.
import { createRequire } from 'node:module';
import readline from 'node:readline';
import { isAbsolute } from 'node:path';

const require = createRequire(import.meta.url);
let browser;
let context;
let page;
let runtime;
const target = new URL(process.env.BROWSER_MCP_URL);
if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password || target.hash) {
  throw new Error('Use a fixed HTTP(S) application URL without credentials or fragment');
}
const modulePath = process.env.BROWSER_MCP_PLAYWRIGHT_PATH || 'playwright-core';
if (modulePath !== 'playwright-core' && !isAbsolute(modulePath)) {
  throw new Error('Configured Playwright module path must be absolute');
}
const { chromium } = require(modulePath);

function reply(id, result, error) {
  process.stdout.write(JSON.stringify(error ? { id, error } : { id, result }) + '\n');
}

async function start() {
  if (browser) return;
  const executablePath = process.env.BROWSER_MCP_EXECUTABLE;
  if (!executablePath || !isAbsolute(executablePath)) throw new Error('Configure an absolute browser executable');
  browser = await chromium.launch({ executablePath, headless: true, timeout: 15000 });
  context = await browser.newContext({ serviceWorkers: 'block', acceptDownloads: false });
  await context.route('**/*', async route => {
    try {
      if (new URL(route.request().url()).origin !== target.origin) {
        await route.abort('blockedbyclient');
        return;
      }
      // Inspect redirects before the API request or browser can follow them.
      const response = await route.fetch({ maxRedirects: 0, timeout: 10000 });
      const location = response.headers()['location'];
      if (location && new URL(location, route.request().url()).origin !== target.origin) {
        await route.abort('blockedbyclient');
      } else await route.fulfill({ response });
    } catch { await route.abort('blockedbyclient'); }
  });
  // This workflow needs no WebSocket; do not leave a second network surface open.
  await context.routeWebSocket('**/*', socket => socket.close());
  page = await context.newPage();
  page.setDefaultTimeout(5000);
  page.setDefaultNavigationTimeout(10000);
  page.on('popup', popup => { void popup.close(); });
  await page.goto(target.href, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Notes', exact: true }).waitFor();
  runtime = { browser: browser.version(), playwright: require(modulePath + '/package.json').version };
}

async function load() {
  await start();
  await page.goto(target.href, { waitUntil: 'domcontentloaded' });
  if (new URL(page.url()).origin !== target.origin) throw new Error('Application left the configured origin');
  await page.getByRole('status').filter({ hasText: /^Ready$/ }).waitFor();
  return snapshot();
}

async function snapshot() {
  const items = page.getByRole('list', { name: 'Notes', exact: true }).getByRole('listitem');
  const count = await items.count();
  if (count > 100) throw new Error('Application exceeds the 100-note bound');
  const notes = [];
  for (let i = 0; i < count; i++) {
    const item = items.nth(i);
    const title = await item.textContent();
    const id = Number(await item.getAttribute('data-note-id'));
    if (!Number.isSafeInteger(id) || id < 1 || typeof title !== 'string' || [...title].length > 120) {
      throw new Error('Unexpected application result');
    }
    notes.push({ id, title });
  }
  return notes;
}

async function run(operation, args) {
  if (operation === 'list_notes') return { notes: await load(), reloaded: true };
  if (operation === 'create_note') {
    const title = args?.title;
    if (typeof title !== 'string' || title.trim() !== title || !title.trim() || [...title].length > 120 || /\p{C}/u.test(title)) {
      throw new Error('Title must contain 1–120 characters without outer whitespace');
    }
    const before = await load();
    if (before.length >= 100) throw new Error('Notes capacity reached');
    await page.getByLabel('Title', { exact: true }).fill(title);
    await page.getByRole('button', { name: 'Add note', exact: true }).click();
    await page.getByRole('status').filter({ hasText: /^Saved$/ }).waitFor();
    const after = await snapshot();
    const ids = new Set(before.map(note => note.id));
    const added = after.filter(note => !ids.has(note.id));
    if (after.length !== before.length + 1 || added.length !== 1 || added[0].title !== title) {
      throw new Error('Write outcome uncertain; inspect notes before retrying');
    }
    return { note: added[0], confirmed_in_page: true };
  }
  if (operation === 'runtime') { await start(); return runtime; }
  throw new Error('Unsupported operation');
}

const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
try {
  for await (const line of lines) {
    let request;
    try {
      if (Buffer.byteLength(line) > 4096) throw new Error('Request too large');
      request = JSON.parse(line);
      if (request.operation === 'shutdown') {
        await browser?.close(); browser = undefined;
        reply(request.id, { closed: true });
        break;
      }
      reply(request.id, await run(request.operation, request.arguments));
    } catch {
      // Avoid returning browser errors containing page text, URLs or private paths.
      reply(request?.id, null, 'Browser operation was not confirmed; inspect notes before retrying a write');
    }
  }
} finally {
  await browser?.close();
  lines.close();
  process.stdin.destroy();
}
