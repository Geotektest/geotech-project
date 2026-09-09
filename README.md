# Geotech DB — Base de données géotechnique interrogeable par IA

Projet de bureau d'études visant à constituer une base de données PostgreSQL/PostGIS
regroupant :
- les données publiques de la Banque du Sous-Sol (BSS/InfoTerre, BRGM)
- les données de risques naturels et technologiques (API Géorisques)
- les sondages géotechniques internes au bureau d'études (extraits de PDF/TIF scannés)

... interrogeable ensuite par un agent IA à partir de la localisation et du type
d'un projet.

## Statut du projet

- [x] Schéma de base de données (PostgreSQL + PostGIS) — `db/schema.sql`
- [x] Import des exports CSV BSS par département — `scripts/import_bss_csv.py`
      (testé avec succès : 6726 ouvrages importés pour le département 01)
- [x] Récupération des risques via l'API Géorisques — `scripts/fetch_georisques.py`
- [ ] Pipeline d'extraction des scans BSS non numérisés (PDF/TIF → données structurées)
- [ ] Import des sondages internes du bureau d'études
- [ ] Agent IA interrogeable (localisation + type de projet → synthèse géologie/risques)

## Structure du dépôt

```
db/               schéma SQL de la base de données
scripts/          scripts Python (import, récupération de données)
data/samples/     petits exemples de données (jamais les exports complets/scans)
docs/             notes et documentation complémentaire
```

## Démarrage rapide

Voir [docs/GUIDE_DEMARRAGE.md](docs/GUIDE_DEMARRAGE.md) pour les instructions
complètes (création de la base sur Supabase, installation des dépendances,
import des données).

## Sources de données utilisées

| Source | Donnée | Accès |
|---|---|---|
| BRGM / InfoTerre | Banque du Sous-Sol (BSS) | Export CSV par département (formulaire sur infoterre.brgm.fr) |
| Géorisques (BRGM/MTE) | Risques naturels et technologiques | API REST publique, sans clé |
| Bureau d'études | Sondages internes | PDF/TIF scannés, extraction via IA |

## Licence des données

Les données BRGM/Géorisques sont publiques mais leur réutilisation doit respecter
les conditions d'utilisation de chaque producteur (mention de la source, pas
d'altération du sens). Voir les liens dans `docs/`.
