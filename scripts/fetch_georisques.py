#!/usr/bin/env python3
"""
Récupère le rapport de risques (naturels + technologiques) via l'API publique
Géorisques pour un projet, et l'enregistre dans la base PostgreSQL.

API utilisée : https://www.georisques.gouv.fr/api/v1/resultats_rapport_risque
(gratuite, sans clé, limite 1000 requêtes/min)

Usage :
    python3 fetch_georisques.py --project-id 1 --lon 4.8357 --lat 45.7640
"""
import argparse
import json
import os

import psycopg2
import requests

DB_CONFIG = dict(
    host=os.environ.get("PGHOST", "localhost"),
    port=os.environ.get("PGPORT", "5432"),
    dbname=os.environ.get("PGDATABASE", "geotech_db"),
    user=os.environ.get("PGUSER", "postgres"),
    password=os.environ.get("PGPASSWORD", "postgres"),
)

API_URL = "https://www.georisques.gouv.fr/api/v1/resultats_rapport_risque"


def fetch_risk_report(lon, lat):
    resp = requests.get(API_URL, params={"latlon": f"{lon},{lat}"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def statut(bloc):
    """Extrait un libellé lisible depuis un sous-objet risque de l'API."""
    if not bloc:
        return None
    return bloc.get("libelleStatutAdresse") or bloc.get("libelleStatutCommune")


def save_report(project_id, lon, lat, data):
    naturels = data.get("risquesNaturels", {})
    techno = data.get("risquesTechnologiques", {})

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO risk_reports (
                    project_id, longitude, latitude,
                    inondation, remontee_nappe, seisme, mouvement_terrain,
                    retrait_gonflement_argiles, radon, avalanche, feu_foret,
                    icpe, canalisations_matieres_dangereuses, pollution_sols,
                    installations_nucleaires, donnees_brutes_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                project_id, lon, lat,
                statut(naturels.get("inondation")),
                statut(naturels.get("remonteeNappe")),
                statut(naturels.get("seisme")),
                statut(naturels.get("mouvementTerrain")),
                statut(naturels.get("retraitGonflementArgile")),
                statut(naturels.get("radon")),
                statut(naturels.get("avalanche")),
                statut(naturels.get("feuForet")),
                statut(techno.get("icpe")),
                statut(techno.get("canalisationsMatieresDangereuses")),
                statut(techno.get("pollutionSols")),
                statut(techno.get("nucleaire")),
                json.dumps(data, ensure_ascii=False),
            ))
        conn.commit()
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--lat", type=float, required=True)
    args = parser.parse_args()

    print(f"Interrogation de l'API Géorisques pour ({args.lon}, {args.lat})...")
    data = fetch_risk_report(args.lon, args.lat)
    save_report(args.project_id, args.lon, args.lat, data)

    print("\nRésumé des risques identifiés :")
    for categorie, risques in [("Naturels", data.get("risquesNaturels", {})),
                                ("Technologiques", data.get("risquesTechnologiques", {}))]:
        print(f"\n  {categorie} :")
        for key, val in risques.items():
            if val.get("present"):
                print(f"    - {val['libelle']} : {statut(val)}")


if __name__ == "__main__":
    main()
