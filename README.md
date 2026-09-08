# ups-fuel

Publie le **supplément carburant UPS Espagne** sous forme de JSON, pour l'application T26.

UPS met son barème à jour chaque lundi sur
[cette page](https://www.ups.com/es/es/support/shipping-support/shipping-costs-rates/fuel-surcharges).
Ce dépôt en relève la première ligne du tableau
« Historial de recargo por combustible de 90 días » et la publie ici :

```
https://raw.githubusercontent.com/EtienneLvsq/ups-fuel/main/ups-fuel.json
```

```json
{
  "source_url": "...",
  "scraped_at_utc": "2026-09-08T10:06:47Z",
  "effective_date": "2026-09-07",
  "standard_percent": 32.0,
  "express_eu_percent": 48.0,
  "express_non_eu_percent": 48.0
}
```

`standard_percent` alimente le service UPS Standard de T26, `express_eu_percent` les
services Express Saver et Express.

## Pourquoi la relève tourne sur le poste et non sur GitHub Actions

`www.ups.com` est protégé par Akamai. Mesuré le 08/09/2026 :

| Client | Depuis ce Mac | Depuis GitHub Actions |
|---|---|---|
| `curl` HTTP/2 | `ERR_HTTP2_PROTOCOL_ERROR` | — |
| `curl` HTTP/1.1 | timeout | — |
| Python / urllib | timeout | — |
| Playwright + Chromium | — | `ERR_HTTP2_PROTOCOL_ERROR` |
| Playwright + Google Chrome | — | `ERR_HTTP2_PROTOCOL_ERROR` |
| Google Chrome, sans HTTP/2 | — | timeout |
| **Google Chrome installé** | **OK** | — |

Seul un vrai navigateur **depuis une connexion ordinaire** obtient la page : les IP de
datacenter d'Azure (sur lesquelles tournent les runners GitHub) sont refusées quel que
soit le navigateur. La relève se fait donc en local et seul le résultat est publié ici.

## Installation de la relève automatique

```bash
cp com.t26.upsfuel.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.t26.upsfuel.plist
```

Le job s'exécute le lundi et le jeudi à 9 h 15, et rattrape au réveil si le Mac était
éteint. Journal : `refresh.log`. Relève manuelle : `./refresh.sh`.

Dépendances : aucune. Le script n'utilise que le Google Chrome installé et la
bibliothèque standard de Python 3 — ni Node, ni Playwright, ni téléchargement.

## Garanties

- En cas d'échec de lecture ou de valeur aberrante, le script **s'arrête** et
  `ups-fuel.json` reste tel quel. Une valeur périmée est préférable à une valeur fausse :
  elle chiffre des devis.
- Écriture atomique : le JSON ne peut jamais être remplacé par du vide.
- Aucun commit n'est créé quand le barème n'a pas bougé.
- Ce dépôt est public pour que T26 puisse lire le JSON sans jeton d'accès. Il ne contient
  que des pourcentages déjà publiés par UPS — aucun tarif négocié, aucune donnée client.
