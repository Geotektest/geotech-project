# Base de données géotechnique — Guide de démarrage

Ce dossier contient les briques testées pour construire ta base PostgreSQL/PostGIS.

## Contenu

- `schema.sql` — le schéma complet de la base (testé, fonctionne)
- `import_bss_csv.py` — importe un export CSV BSS/InfoTerre par département
  (testé sur ton fichier réel : 6726 ouvrages importés, dont 1554 identifiés
  comme "à traiter" car leur coupe géologique n'existe qu'en scan/PDF)
- `fetch_georisques.py` — récupère les risques naturels/technologiques d'un
  point via l'API publique Géorisques (code prêt, non testable depuis mon
  environnement pour des raisons de restriction réseau — à tester chez toi)
- `requirements.txt` — dépendances Python nécessaires

## Étape 1 — Créer ta base (Supabase recommandé)

1. Crée un compte gratuit sur https://supabase.com
2. Crée un nouveau projet (choisis une région Europe)
3. Dans l'onglet "Database" → active l'extension `postgis`
4. Récupère les identifiants de connexion (onglet "Connect")

## Étape 2 — Installer les outils sur ton ordinateur

```bash
pip install -r requirements.txt --break-system-packages
```

## Étape 3 — Appliquer le schéma

```bash
psql "postgresql://<user>:<password>@<host>:<port>/<database>" -f schema.sql
```

(Remplace par les identifiants donnés par Supabase, ou mets-les dans les
variables d'environnement PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD)

## Étape 4 — Importer un export BSS

```bash
python3 import_bss_csv.py bss_export_01.csv
```

Ce script :
- lit le CSV (séparateur `;`)
- convertit les coordonnées Lambert-93 en longitude/latitude (WGS84)
- insère chaque ouvrage dans PostgreSQL avec sa géométrie PostGIS
- marque automatiquement `statut_extraction = 'a_traiter'` pour tous les
  ouvrages dont la coupe géologique existe mais n'est pas encore numérisée
  (c'est cette liste qui doit passer par le pipeline OCR/IA)

## Étape 5 — Récupérer les risques pour un projet

```bash
python3 fetch_georisques.py --project-id 1 --lon 4.8357 --lat 45.7640
```

## Ce qu'il reste à construire

1. **Le pipeline d'extraction des scans BSS** — pour chaque ouvrage marqué
   `a_traiter`, télécharger son scan depuis la fiche InfoTerre
   (`lien_infoterre`) et appliquer la même extraction que celle qu'on a
   testée sur tes fichiers T416738/T416739.TIF.
2. **L'import de tes propres sondages** (table `boreholes_internes` /
   `geological_layers` avec `source_type = 'sondage_interne'`).
3. **La couche IA interrogeable** — un agent qui, à partir de la position
   d'un projet, interroge `bss_ouvrages` (ouvrages proches), `risk_reports`
   et `geological_layers`, puis synthétise une réponse en langage naturel.
