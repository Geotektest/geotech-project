-- ============================================================================
-- SCHEMA : Base de données géotechnique (BSS/InfoTerre + logs propres + risques)
-- PostgreSQL + PostGIS
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ----------------------------------------------------------------------------
-- 1. OUVRAGES BSS (import direct des exports CSV InfoTerre par département)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bss_ouvrages (
    id_bss              TEXT PRIMARY KEY,          -- ex: BSS001PBUF
    indice              TEXT UNIQUE,                -- ex: 06027X0001 (code public BSS)
    designation         TEXT,
    libelle             TEXT,
    lien_infoterre      TEXT,

    -- Localisation
    departement_code    TEXT,
    departement_nom     TEXT,
    commune_insee       TEXT,
    commune_nom         TEXT,
    lieu_dit            TEXT,
    x_lambert93         DOUBLE PRECISION,
    y_lambert93          DOUBLE PRECISION,
    geom                geometry(Point, 4326),      -- reprojeté en WGS84 pour usage général

    -- Altimétrie
    cote_sol_ngf        DOUBLE PRECISION,

    -- Caractéristiques de l'ouvrage
    nature              TEXT,                       -- FORAGE, SONDAGE, PUITS, SOURCE...
    profondeur_investigation DOUBLE PRECISION,
    profondeur_accessible    DOUBLE PRECISION,
    date_fin_travaux    DATE,

    -- Disponibilité des données géologiques (le coeur du pipeline)
    coupe_geologique_presente BOOLEAN,              -- une coupe existe (scan ou saisie)
    log_geologique_verifie    BOOLEAN,               -- coupe déjà numérisée/structurée par le BRGM
    nb_scans            INTEGER,
    nb_scans_coupe       INTEGER,
    documents_disponibles TEXT,                      -- ex: COUPE-GEOLOGIQUE,PLAN-SITUATION

    -- Statut de traitement par NOTRE pipeline d'extraction
    statut_extraction   TEXT DEFAULT 'non_requis'
                         CHECK (statut_extraction IN
                         ('non_requis','a_traiter','en_cours','extrait','echec')),

    donnees_brutes      JSONB,                       -- toutes les autres colonnes du CSV, au cas où
    date_import         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bss_geom ON bss_ouvrages USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_bss_commune ON bss_ouvrages (commune_insee);
CREATE INDEX IF NOT EXISTS idx_bss_a_traiter ON bss_ouvrages (statut_extraction)
    WHERE statut_extraction = 'a_traiter';

-- ----------------------------------------------------------------------------
-- 2. COUCHES GEOLOGIQUES (résultat structuré de l'extraction PDF/TIF)
--    Alimentée soit par notre pipeline OCR/IA sur les scans BSS,
--    soit par vos propres sondages internes (voir table boreholes_internes)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS geological_layers (
    id                  SERIAL PRIMARY KEY,
    id_bss              TEXT REFERENCES bss_ouvrages(id_bss),   -- NULL si sondage interne
    borehole_interne_id INTEGER,                                 -- voir table ci-dessous

    profondeur_debut_m  DOUBLE PRECISION NOT NULL,
    profondeur_fin_m    DOUBLE PRECISION NOT NULL,
    epaisseur_m         DOUBLE PRECISION,
    cote_debut_ngf       DOUBLE PRECISION,
    cote_fin_ngf         DOUBLE PRECISION,

    nature_terrain      TEXT,                       -- description brute (ex: "Marne argileuse compacte")
    classification_uscs  TEXT,                       -- si disponible/déductible
    observations        TEXT,                        -- venues d'eau, essais, etc.

    source_type          TEXT CHECK (source_type IN ('bss_scan','sondage_interne','autre')),
    fichier_source        TEXT,                       -- nom du PDF/TIF d'origine
    extraction_confiance  NUMERIC(3,2),                -- score de confiance de l'IA (0 à 1)
    valide_par_humain     BOOLEAN DEFAULT FALSE,        -- garde-fou avant usage "officiel"

    CHECK (profondeur_fin_m >= profondeur_debut_m)
);

CREATE INDEX IF NOT EXISTS idx_layers_bss ON geological_layers (id_bss);

-- ----------------------------------------------------------------------------
-- 3. SONDAGES INTERNES (vos propres logs de forage, hors BSS)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS boreholes_internes (
    id                  SERIAL PRIMARY KEY,
    project_id           INTEGER,                     -- lien vers projects, voir plus bas
    nom_forage           TEXT,                         -- ex: "F1"
    date_forage           DATE,
    cote_terrain_ngf       DOUBLE PRECISION,
    longitude             DOUBLE PRECISION,
    latitude               DOUBLE PRECISION,
    geom                   geometry(Point, 4326),
    profondeur_totale_m     DOUBLE PRECISION,
    fichier_source           TEXT
);

-- ----------------------------------------------------------------------------
-- 4. PROJETS (bureau d'études : un projet = un site à étudier)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id                  SERIAL PRIMARY KEY,
    nom                 TEXT NOT NULL,
    type_projet         TEXT,                          -- ex: "maison individuelle", "immeuble R+4"...
    adresse             TEXT,
    longitude           DOUBLE PRECISION,
    latitude            DOUBLE PRECISION,
    geom                geometry(Point, 4326),
    date_creation       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_projects_geom ON projects USING GIST (geom);

ALTER TABLE boreholes_internes
    ADD CONSTRAINT fk_borehole_project FOREIGN KEY (project_id) REFERENCES projects(id);

-- ----------------------------------------------------------------------------
-- 5. RISQUES (résultat brut + synthèse de l'API Géorisques pour un projet)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_reports (
    id                  SERIAL PRIMARY KEY,
    project_id           INTEGER REFERENCES projects(id),
    longitude             DOUBLE PRECISION,
    latitude               DOUBLE PRECISION,

    -- Risques naturels (extraits du JSON pour requêtage facile)
    inondation            TEXT,
    remontee_nappe        TEXT,
    seisme                TEXT,
    mouvement_terrain      TEXT,
    retrait_gonflement_argiles TEXT,
    radon                 TEXT,
    avalanche              TEXT,
    feu_foret               TEXT,

    -- Risques technologiques / anthropiques
    icpe                    TEXT,
    canalisations_matieres_dangereuses TEXT,
    pollution_sols           TEXT,
    installations_nucleaires  TEXT,

    donnees_brutes_json       JSONB,                    -- réponse complète de l'API, pour l'IA
    date_recuperation          TIMESTAMPTZ DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 6. Vue pratique : ouvrages BSS à traiter par le pipeline d'extraction
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_bss_a_extraire AS
SELECT id_bss, indice, commune_nom, nb_scans_coupe, lien_infoterre
FROM bss_ouvrages
WHERE coupe_geologique_presente = TRUE
  AND log_geologique_verifie = FALSE
  AND statut_extraction = 'a_traiter';

-- ----------------------------------------------------------------------------
-- 7. Fonction pratique : trouver les ouvrages BSS proches d'un projet
-- ----------------------------------------------------------------------------
-- Exemple d'usage :
-- SELECT indice, nature, ST_Distance(geom::geography, (SELECT geom FROM projects WHERE id=1)::geography) AS distance_m
-- FROM bss_ouvrages
-- ORDER BY geom <-> (SELECT geom FROM projects WHERE id=1)
-- LIMIT 20;
