#!/usr/bin/env python3
"""Relève le supplément carburant UPS depuis le poste local et met à jour ups-fuel.json.

Sert de solution de repli quand GitHub Actions se fait refuser par la protection
anti-robot d'UPS (ERR_HTTP2_PROTOCOL_ERROR depuis les IP de datacenter) : depuis une
connexion ordinaire, le Google Chrome installé sur la machine obtient la page.

N'utilise que Chrome et la bibliothèque standard : ni Node, ni Playwright, ni
téléchargement de navigateur.

En cas d'échec, sort en code 1 SANS toucher au JSON existant : une valeur périmée
est préférable à une valeur fausse, puisqu'elle chiffre des devis.
"""

import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

URL = "https://www.ups.com/es/es/support/shipping-support/shipping-costs-rates/fuel-surcharges"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ups-fuel.json")
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]
MARKER = "Fecha de inicio"
DEADLINE_S = 90
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


def find_chrome():
    for path in CHROME_CANDIDATES:
        if path and os.path.exists(path):
            return path
    raise SystemExit("Aucun navigateur Chrome/Chromium trouvé sur cette machine.")


def dump_dom():
    """Chrome écrit le DOM sur la sortie standard, mais ne rend pas toujours la main :
    on lit dans un fichier et on l'arrête dès que le tableau est apparu."""
    chrome = find_chrome()
    tmpdir = tempfile.mkdtemp(prefix="ups-fuel-")
    dom_path = os.path.join(tmpdir, "dom.html")
    try:
        with open(dom_path, "wb") as out, open(os.devnull, "wb") as err:
            proc = subprocess.Popen(
                [
                    chrome, "--headless=new", "--disable-gpu",
                    "--no-first-run", "--no-default-browser-check",
                    "--virtual-time-budget=30000", "--lang=es-ES",
                    # Sans cette ligne, Chrome annonce « HeadlessChrome » dans son
                    # User-Agent et UPS sert une page sans le tableau.
                    "--user-agent=" + USER_AGENT,
                    "--user-data-dir=" + os.path.join(tmpdir, "profile"),
                    "--dump-dom", URL,
                ],
                stdout=out, stderr=err, start_new_session=True,
            )
            # Chrome écrit le DOM complet puis ne rend pas toujours la main : on attend
            # un document ENTIER (marqueur présent et </html> final) avant de l'arrêter.
            # Se contenter du marqueur couperait l'écriture en cours et tronquerait le DOM.
            deadline = time.time() + DEADLINE_S
            while time.time() < deadline:
                if proc.poll() is not None:
                    break
                try:
                    with open(dom_path, encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                    if MARKER in content and content.rstrip().endswith("</html>"):
                        break
                except OSError:
                    pass
                time.sleep(0.5)

            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait(timeout=10)

        with open(dom_path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def parse_percent(raw, label):
    cleaned = re.sub(r"[\s  ]", "", str(raw)).replace("%", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        raise SystemExit(f"{label} : pourcentage illisible \"{raw}\"")
    if not 0 < value <= 100:
        raise SystemExit(f"{label} : pourcentage hors bornes ]0;100] -> {value}")
    return round(value, 2)


def parse_date(raw):
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", str(raw).strip())
    if not m:
        raise SystemExit(f"date illisible \"{raw}\"")
    d, mo, y = m.groups()
    iso = f"{y}-{mo}-{d}"
    try:
        parsed = datetime.strptime(iso, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(f"date invalide \"{raw}\"")
    if (parsed - datetime.now()).days > 30:
        raise SystemExit(f"date trop lointaine \"{raw}\"")
    return iso


def extract(dom):
    # Repérage par le TEXTE de l'en-tête, jamais par les classes CSS : UPS les régénère.
    for table in re.findall(r"<table\b.*?</table>", dom, re.S | re.I):
        head = re.search(r"<thead\b.*?</thead>", table, re.S | re.I)
        if not head or MARKER not in head.group(0):
            continue
        body = re.search(r"<tbody\b.*?</tbody>", table, re.S | re.I)
        if not body:
            continue
        row = re.search(r"<tr\b.*?</tr>", body.group(0), re.S | re.I)
        if not row:
            continue
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
            for c in re.findall(r"<td\b[^>]*>(.*?)</td>", row.group(0), re.S | re.I)
        ]
        if len(cells) >= 4:
            return cells
        raise SystemExit(f"ligne inattendue : {len(cells)} cellules (4 attendues) -> {cells}")
    raise SystemExit("tableau « Fecha de inicio efectiva » introuvable")


def main():
    dom = dump_dom()
    if MARKER not in dom:
        raise SystemExit(
            "La page n'a pas été obtenue (protection anti-robot ou réseau). "
            f"{len(dom)} octets reçus. ups-fuel.json est laissé intact."
        )

    cells = extract(dom)
    result = {
        "source_url": URL,
        "scraped_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "effective_date": parse_date(cells[0]),
        "standard_percent": parse_percent(cells[1], "Standard"),
        "express_eu_percent": parse_percent(cells[2], "Express UE"),
        "express_non_eu_percent": parse_percent(cells[3], "Express hors UE"),
    }

    print(
        f"Barème du {result['effective_date']} : "
        f"Standard {result['standard_percent']}% / "
        f"Express UE {result['express_eu_percent']}% / "
        f"Express hors UE {result['express_non_eu_percent']}%"
    )

    # scraped_at_utc change à chaque exécution : on compare sans lui pour ne pas
    # créer un commit hebdomadaire vide quand UPS n'a rien changé.
    def without_timestamp(text):
        try:
            data = json.loads(text)
            data.pop("scraped_at_utc", None)
            return json.dumps(data, sort_keys=True)
        except (ValueError, AttributeError):
            return None

    previous = ""
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            previous = fh.read()

    nxt = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if without_timestamp(previous) == without_timestamp(nxt):
        print("Barème inchangé — fichier laissé tel quel.")
        return 0

    # Écriture atomique : le JSON précédent ne peut jamais être remplacé par du vide.
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(nxt)
    os.replace(tmp, OUT)
    print(f"{os.path.basename(OUT)} mis à jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
