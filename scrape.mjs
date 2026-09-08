// Lit le supplément carburant UPS Espagne et écrit ups-fuel.json.
//
// Pourquoi un vrai navigateur : www.ups.com est derrière une protection anti-robot
// (Akamai). curl, Python/urllib et les proxys publics se font couper la connexion.
// Seul un moteur Chromium complet obtient la page.
//
// En cas d'échec, le script sort en code 1 SANS toucher au JSON existant : mieux vaut
// une valeur périmée qu'une valeur fausse, puisqu'elle chiffre des devis.

import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const URL = 'https://www.ups.com/es/es/support/shipping-support/shipping-costs-rates/fuel-surcharges';
const OUT = 'ups-fuel.json';
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
const TRIES = 3;

// "32,00%" (format espagnol, parfois avec espace insécable) -> 32
function parsePercent(raw, label) {
  const cleaned = String(raw).replace(/[\s\u00a0\u202f]/g, '').replace('%', '').replace(',', '.');
  const value = Number(cleaned);
  if (!Number.isFinite(value)) throw new Error(`${label} : pourcentage illisible "${raw}"`);
  if (value <= 0 || value > 100) throw new Error(`${label} : pourcentage hors bornes ]0;100] -> ${value}`);
  return Math.round(value * 100) / 100;
}

// "07/09/2026" -> "2026-09-07"
function parseDate(raw) {
  const m = String(raw).trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!m) throw new Error(`date illisible "${raw}"`);
  const [, d, mo, y] = m;
  const iso = `${y}-${mo}-${d}`;
  const parsed = new Date(iso + 'T00:00:00Z');
  if (Number.isNaN(parsed.getTime())) throw new Error(`date invalide "${raw}"`);
  // Un barème daté dans un futur lointain = page mal lue.
  const limit = Date.now() + 30 * 24 * 3600 * 1000;
  if (parsed.getTime() > limit) throw new Error(`date trop lointaine "${raw}"`);
  return iso;
}

async function scrapeOnce() {
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'],
  });
  try {
    const context = await browser.newContext({
      locale: 'es-ES',
      timezoneId: 'Europe/Madrid',
      viewport: { width: 1440, height: 900 },
      userAgent: UA,
      extraHTTPHeaders: { 'Accept-Language': 'es-ES,es;q=0.9' },
    });
    // Gomme le marqueur navigator.webdriver, le signal d'automatisation le plus regardé.
    await context.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    });

    const page = await context.newPage();
    await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    // Le tableau peut être rendu côté client : on attend son en-tête, pas un délai fixe.
    await page.waitForSelector('text=Fecha de inicio', { timeout: 45000 });

    // Repérage par le TEXTE de l'en-tête, jamais par les classes CSS : UPS les régénère.
    const cells = await page.evaluate(() => {
      const tables = Array.from(document.querySelectorAll('table'));
      const target = tables.find((t) => {
        const head = t.querySelector('thead');
        return head && head.textContent.includes('Fecha de inicio');
      });
      if (!target) return null;
      const row = target.querySelector('tbody tr');
      if (!row) return null;
      return Array.from(row.querySelectorAll('td')).map((td) => td.textContent.trim());
    });

    if (!cells) throw new Error("tableau « Fecha de inicio efectiva » introuvable");
    if (cells.length < 4) throw new Error(`ligne inattendue : ${cells.length} cellules (4 attendues) -> ${JSON.stringify(cells)}`);

    return {
      source_url: URL,
      scraped_at_utc: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
      effective_date: parseDate(cells[0]),
      standard_percent: parsePercent(cells[1], 'Standard'),
      express_eu_percent: parsePercent(cells[2], 'Express UE'),
      express_non_eu_percent: parsePercent(cells[3], 'Express hors UE'),
    };
  } finally {
    await browser.close();
  }
}

let result = null;
let lastError = null;
for (let attempt = 1; attempt <= TRIES; attempt++) {
  try {
    result = await scrapeOnce();
    break;
  } catch (err) {
    lastError = err;
    console.error(`Tentative ${attempt}/${TRIES} échouée : ${err.message}`);
    if (attempt < TRIES) await new Promise((r) => setTimeout(r, attempt * 10000));
  }
}

if (!result) {
  console.error('ÉCHEC : ups-fuel.json est laissé intact.');
  console.error(lastError?.stack ?? String(lastError));
  process.exit(1);
}

console.log(`Barème du ${result.effective_date} : Standard ${result.standard_percent}% / Express UE ${result.express_eu_percent}% / Express hors UE ${result.express_non_eu_percent}%`);

const previous = existsSync(OUT) ? readFileSync(OUT, 'utf8') : '';
const next = JSON.stringify(result, null, 2) + '\n';

// scraped_at_utc change à chaque exécution : on compare sans lui pour éviter un commit
// hebdomadaire vide quand UPS n'a rien changé.
const withoutTimestamp = (raw) => {
  try {
    const { scraped_at_utc, ...rest } = JSON.parse(raw);
    return JSON.stringify(rest);
  } catch {
    return null;
  }
};
if (withoutTimestamp(previous) === withoutTimestamp(next)) {
  console.log('Barème inchangé — fichier laissé tel quel.');
  process.exit(0);
}

writeFileSync(OUT, next);
console.log(`${OUT} mis à jour.`);
