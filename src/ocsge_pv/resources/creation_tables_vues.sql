-- Minimal requirements for tables used in this project
-- Include the definition of the view for web services

-- Declarations as extracted and archived from the source web service
-- Some columns are used only for filtering exports
CREATE TABLE IF NOT EXISTS "raw_dossier" (
    "id_dossier" bigint PRIMARY KEY,
    "porteur" bool,
    "siret_port" char(14),
    "ref_urba" text,
    "type_proj" text,
    "surf_socle" decimal(17, 4),
    "etat" text,
    "puiss_max" int,
    "date_depot" date,
    "date_deliv" date,
    "date_insta" date,
    "duree_exp" int,
    "adresse" text,
    "num_parcelles" text,
    "surf_occup" decimal(17, 4),
    "surf_terr" decimal(17, 4),
    "localisat" text,
    "sol_nature" text,
    "sol_detail" text,
    "usage_terr" text,
    "type_agri" text,
    "agri_ini" text,
    "agri_resid" text,
    "ancrage" text,
    "cloture" text,
    "revetement" text,
    "haut_pann" decimal(6, 3),
    "espacement" decimal(8, 3),
    "nat_pieux" bool,
    "transit" bool,
    "agrivolt" bool,
    "ex_date" bool,
    "ex_agriv" bool,
    "ex_techniq" bool,
    "creation" timestamp (0) with time zone,
    "geom" geometry(GEOMETRYCOLLECTION,2154),
    "dern_modif" timestamp (0) with time zone,
    "archive" bool,
    "supprime" bool
);

-- Declarations as used by the pairing tool
CREATE TABLE IF NOT EXISTS "declaration" (
    "id_dossier" bigint PRIMARY KEY,
    "porteur" bool,
    "siret_port" char(14),
    "ref_urba" text,
    "type_proj" text,
    "surf_socle" decimal(17, 4),
    "etat" text,
    "puiss_max" int,
    "date_depot" date,
    "date_deliv" date,
    "date_insta" date,
    "duree_exp" int,
    "adresse" text,
    "num_parcelles" text,
    "surf_occup" decimal(17, 4),
    "surf_terr" decimal(17, 4),
    "localisat" text,
    "sol_nature" text,
    "sol_detail" text,
    "usage_terr" text,
    "type_agri" text,
    "agri_ini" text,
    "agri_resid" text,
    "ancrage" text,
    "cloture" text,
    "revetement" text,
    "haut_pann" decimal(6, 3),
    "espacement" decimal(8, 3),
    "nat_pieux" bool,
    "transit" bool,
    "agrivolt" bool,
    "ex_date" bool,
    "ex_agriv" bool,
    "ex_techniq" bool,
    "creation" timestamp (0) with time zone,
    "geom" geometry(GEOMETRYCOLLECTION,2154)
);

-- Detections as used by the pairing tool
CREATE TABLE IF NOT EXISTS "detection" (
    "id_v2" bigint PRIMARY KEY,
    "long" decimal(11, 8),
    "lat" decimal(11, 8),
    "surf_parc" decimal(17, 4),
    "flottant" bool,
    "agrivolt" bool,
    "insee_com" text,
    "nom_com" text,
    "millesime" int,
    "geom" geometry(MULTIPOLYGON,2154)
);

-- Pairs as created by the pairing tool
CREATE TABLE IF NOT EXISTS "declaration_detection" (
    "declaration_id" bigint REFERENCES "declaration",
    "detection_id" bigint REFERENCES "detection"
);
CREATE UNIQUE INDEX IF NOT EXISTS "declaration_detection_idx" ON "declaration_detection" ("declaration_id", "detection_id");

-- View used as the underlying data for public diffusion
CREATE OR REPLACE VIEW "donnees_agregees" AS
    SELECT
        "detection"."id_v2" AS "id",
        "detection"."long",
        "detection"."lat",
        "detection"."surf_parc",
        "detection"."flottant",
        "detection"."agrivolt",
        "detection"."insee_com",
        "detection"."nom_com",
        "detection"."millesime",
        "declaration"."siret_port",
        "declaration"."ref_urba",
        "declaration"."type_proj",
        "declaration"."surf_socle",
        "declaration"."etat",
        "declaration"."puiss_max",
        "declaration"."date_depot",
        "declaration"."date_deliv",
        "declaration"."date_insta",
        "declaration"."duree_exp",
        "declaration"."adresse",
        "declaration"."surf_occup",
        "declaration"."surf_terr",
        "declaration"."localisat",
        "declaration"."sol_nature",
        "declaration"."sol_detail",
        "declaration"."usage_terr",
        "declaration"."type_agri",
        "declaration"."ancrage",
        "declaration"."cloture",
        "declaration"."revetement",
        "declaration"."haut_pann",
        "declaration"."espacement",
        "declaration"."nat_pieux",
        "declaration"."ex_date",
        "declaration"."ex_agriv",
        "declaration"."ex_techniq",
        "detection"."geom"
    FROM "declaration"
        INNER JOIN "declaration_detection"
        ON "declaration"."id_dossier"="declaration_detection"."declaration_id"
        RIGHT JOIN "detection"
        ON "declaration_detection"."detection_id"="detection"."id_v2"
;
