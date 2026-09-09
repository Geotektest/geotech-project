#!/usr/bin/env python3
"""
Importe un export CSV BSS/InfoTerre (par département) dans la base PostgreSQL.

Usage :
    python3 import_bss_csv.py bss_export_01.csv

Prérequis :
    pip install psycopg2-binary pyproj pandas --break-system-packages
    Variables d'environnement (ou modifie DB_CONFIG ci-dessous) :
        PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
"""
import sys
import os
import csv
import json
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values
from pyproj import Transformer

# ----------------------------------------------------------------------------
# Configuration de connexion (adapte ou utilise les variables d'environnement)
# ----------------------------------------------------------------------------
DB_CONFIG = dict(
    host=os.environ.get("PGHOST", "localhost"),
    port=os.environ.get("PGPORT", "5432"),
    dbname=os.environ.get("PGDATABASE", "geotech_db"),
    user=os.environ.get("PGUSER", "postgres"),
    password=os.environ.get("PGPASSWORD", "postgres"),
)

# Lambert-93 (EPSG:2154) -> WGS84 (EPSG:4326), utilisé pour les colonnes x_ref06/y_ref06
TRANSFORMER = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)


def parse_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def parse_date(value):
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_bool_presence(value):
    """Convertit 'Presente'/'Absente' ou 'Present'/'Absent' en booléen."""
    if not value:
        return None
    return value.strip().lower().startswith("pres")


def row_to_record(row):
    x = parse_float(row.get("x_ref06"))
    y = parse_float(row.get("y_ref06"))
    lon, lat = (None, None)
    if x is not None and y is not None:
        try:
            lon, lat = TRANSFORMER.transform(x, y)
        except Exception:
            lon, lat = (None, None)

    coupe_presente = parse_bool_presence(row.get("coupe_geologique"))
    log_verifie = parse_bool_presence(row.get("log_geol_verifie"))

    # Statut de traitement : à traiter par notre pipeline seulement si
    # une coupe existe mais n'est pas encore numérisée par le BRGM.
    if coupe_presente and not log_verifie:
        statut = "a_traiter"
    else:
        statut = "non_requis"

    # Colonnes déjà extraites explicitement, ne pas les dupliquer dans le JSON brut
    colonnes_extraites = {
        "id_bss", "indice", "designation", "libelle", "lien_infoterre",
        "lex_num_departement", "lex_nom_departement", "lex_insee_commune",
        "lex_nom_commune", "lieu_dit", "x_ref06", "y_ref06", "z_sol",
        "lex_nature", "prof_investigation", "prof_accessible",
        "date_fin_travaux", "coupe_geologique", "log_geol_verifie",
        "nb_scans", "nb_scans_coupe", "lex_documents",
    }
    reste = {k: v for k, v in row.items() if k not in colonnes_extraites and v}

    return (
        row.get("id_bss") or row.get("ID_BSS"),
        row.get("indice"),
        row.get("designation"),
        row.get("libelle") or None,
        row.get("lien_infoterre"),
        row.get("lex_num_departement"),
        row.get("lex_nom_departement"),
        row.get("lex_insee_commune"),
        row.get("lex_nom_commune"),
        row.get("lieu_dit"),
        x, y,
        lon, lat,  # utilisés pour construire la géométrie
        parse_float(row.get("z_sol")),
        row.get("lex_nature") or None,
        parse_float(row.get("prof_investigation")),
        parse_float(row.get("prof_accessible")),
        parse_date(row.get("date_fin_travaux")),
        coupe_presente,
        log_verifie,
        int(row["nb_scans"]) if row.get("nb_scans") else None,
        int(row["nb_scans_coupe"]) if row.get("nb_scans_coupe") else None,
        row.get("lex_documents") or None,
        statut,
        json.dumps(reste, ensure_ascii=False),
    )


INSERT_SQL = """
INSERT INTO bss_ouvrages (
    id_bss, indice, designation, libelle, lien_infoterre,
    departement_code, departement_nom, commune_insee, commune_nom, lieu_dit,
    x_lambert93, y_lambert93, geom,
    cote_sol_ngf, nature, profondeur_investigation, profondeur_accessible,
    date_fin_travaux, coupe_geologique_presente, log_geologique_verifie,
    nb_scans, nb_scans_coupe, documents_disponibles, statut_extraction,
    donnees_brutes
)
VALUES %s
ON CONFLICT (id_bss) DO UPDATE SET
    coupe_geologique_presente = EXCLUDED.coupe_geologique_presente,
    log_geologique_verifie = EXCLUDED.log_geologique_verifie,
    statut_extraction = CASE
        WHEN bss_ouvrages.statut_extraction IN ('extrait','en_cours') THEN bss_ouvrages.statut_extraction
        ELSE EXCLUDED.statut_extraction
    END,
    donnees_brutes = EXCLUDED.donnees_brutes,
    date_import = now();
"""

TEMPLATE = """(
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326),
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s,
    %s
)"""


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 import_bss_csv.py <fichier.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    print(f"Lecture de {csv_path}...")

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        records = [row_to_record(row) for row in reader]

    print(f"{len(records)} ouvrages lus. Connexion à PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            execute_values(cur, INSERT_SQL, records, template=TEMPLATE, page_size=500)
        conn.commit()
        print(f"Import terminé : {len(records)} ouvrages insérés/mis à jour.")

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM bss_ouvrages WHERE statut_extraction = 'a_traiter';")
            n_a_traiter = cur.fetchone()[0]
        print(f"→ {n_a_traiter} ouvrages ont une coupe géologique non numérisée : "
              f"à traiter par le pipeline d'extraction PDF/TIF.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
