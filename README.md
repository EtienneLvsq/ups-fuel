# ups-fuel

Publie le **supplément carburant UPS Espagne** sous forme de JSON, pour l'application T26.

UPS met son barème à jour chaque lundi sur
[cette page](https://www.ups.com/es/es/support/shipping-support/shipping-costs-rates/fuel-surcharges).
Ce dépôt lit la première ligne du tableau « Historial de recargo por combustible de 90 días »
et en publie le contenu ici :

```
https://raw.githubusercontent.com/EtienneLvsq/ups-fuel/main/ups-fuel.json
```

```json
{
  "source_url": "...",
  "scraped_at_utc": "2026-09-08T06:03:11Z",
  "effective_date": "2026-09-07",
  "standard_percent": 32,
  "express_eu_percent": 48,
  "express_non_eu_percent": 48
}
```

`standard_percent` alimente le service UPS Standard de T26, `express_eu_percent` les services
Express Saver et Express.

## Pourquoi Playwright et pas `curl`

`www.ups.com` est protégé par Akamai : `curl` (HTTP/1.1 comme HTTP/2), Python/urllib et les
proxys publics se font couper la connexion sans réponse. Seul un moteur Chromium complet
obtient la page — d'où Playwright.

## Garanties

- En cas d'échec de lecture ou de valeur aberrante, le job **échoue** et `ups-fuel.json` reste
  tel quel. Une valeur périmée est préférable à une valeur fausse : elle chiffre des devis.
- Aucun commit n'est créé quand le barème n'a pas bougé.
- Ce dépôt est public pour que T26 puisse lire le JSON sans jeton d'accès. Il ne contient que
  des pourcentages déjà publiés par UPS.
