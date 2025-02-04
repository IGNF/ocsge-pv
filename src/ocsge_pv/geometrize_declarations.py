"""Provides an executable to add geometries to declared photovoltaic installations.
"""

# -- IMPORTS --
# standard library
from copy import deepcopy
from datetime import date, datetime
import json
import os
import re
import sys
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

# 3rd party
from osgeo import ogr, osr
import jsonschema
import psycopg
from psycopg import sql

# package

# -- GLOBALS --
ogr.UseExceptions()
osr.UseExceptions()

# -- FUNCTIONS --
def load_configuration(path: str) -> Dict:
    """Returns validated configuration from file
    
    Args:
        path (str): path to the configuration file
    
    Raises:
        jonschema.ValidationError: The configuration file does not match the validation schema

    Returns:
        Dict: the configuration object translated from the input file
    """
    validation_schema_path = "src/ocsge_pv/resources/geometrize_config.schema.json"
    with open(path, "r", encoding="utf-8") as config_file:
        config_str = config_file.read()
    source_configuration = json.loads(config_str)
    with open(validation_schema_path, "r", encoding="utf-8") as schema_file:
        schema_str = schema_file.read()
    schema = json.loads(schema_str)
    jsonschema.validate(source_configuration, schema)
    modified_configuration = deepcopy(source_configuration)
    # Declarations data (input + output)
    modified_configuration["main_database"]["_pg_string"] = (
        "host=" + modified_configuration['main_database']['host']
        + " port=" + str(modified_configuration['main_database']['port'])
        + " dbname=" + modified_configuration['main_database']['name']
        + " user=" + modified_configuration['main_database']['user']
        + " password=" + modified_configuration['main_database']['password'])
    modified_configuration["main_database"]["_pg_string"] = (
        "host=" + modified_configuration['main_database']['host']
        + " port=" + str(modified_configuration['main_database']['port'])
        + " dbname=" + modified_configuration['main_database']['name']
        + " user=" + modified_configuration['main_database']['user']
        + " password=" + modified_configuration['main_database']['password'])
    modified_configuration["main_database"]["_table_name_raw"] = (
        modified_configuration["main_database"]["schema"] + "."
        + modified_configuration["main_database"]["table"])
    modified_configuration["main_database"]["_table_name_sql"] = sql.SQL(".").join([
        modified_configuration["main_database"]["schema"],
        modified_configuration["main_database"]["table"]])
    # Cadastral data (input)
    modified_configuration["cadastre_database"]["_pg_string"] = (
        "host=" + modified_configuration["cadastre_database"]["host"]
        + " port=" + str(modified_configuration["cadastre_database"]["port"])
        + " dbname=" + modified_configuration["cadastre_database"]["name"]
        + " user=" + modified_configuration["cadastre_database"]["user"]
        + " password=" + modified_configuration["cadastre_database"]["password"])
    modified_configuration["cadastre_database"]["_table_name_raw"] = (
        modified_configuration["cadastre_database"]["schema"] + "."
        + modified_configuration["cadastre_database"]["table"])
    return modified_configuration


# -- MAIN FUNCTION --
def main(configuration_file_path: str) -> None:
    """Main routine, entrypoint for the program
        
    Args:
        configuration_file_path (str): path to the configuration file
    """
    # Read configuration
    configuration = load_configuration(configuration_file_path)
    # Connect to OGR datasources
    declaration_ogr_ds = ogr.Open(configuration["main_database"]["_pg_string"])
    cadastre_ogr_ds = ogr.Open(configuration["cadastre_database"]["_pg_string"])
    # Compute SRS and conversions
    ## Declarations layer's SRS
    declaration_ogr_layer = declaration_ogr_ds.GetLayerByName(
        configuration["main_database"]["_table_name_raw"])
    declaration_ogr_srs = declaration_ogr_layer.GetSpatialRef()
    if (declaration_ogr_srs is None):
        raise ValueError("Declarations layer's SRS not found.")
    ## Cadastre layer's SRS
    cadastre_ogr_layer = cadastre_ogr_ds.GetLayerByName(
        configuration["cadastre_database"]["_table_name_raw"])
    cadastre_ogr_srs = cadastre_ogr_layer.GetSpatialRef()
    if (cadastre_ogr_srs is None):
        raise ValueError("Cadastre layer's SRS not found.")
    ## OGR coordinates transformation, from cadastre to declarations
    ogr_ct = None
    coordinates_need_swap = False
    latlon_sr_name_list = ['WGS 84']
    if cadastre_ogr_srs != declaration_ogr_srs:
        ogr_ct = osr.CreateCoordinateTransformation(cadastre_ogr_srs, declaration_ogr_srs)
        is_cadastre_srs_latlon = (cadastre_ogr_srs.EPSGTreatsAsLatLong() 
            or cadastre_ogr_srs.GetName() in latlon_sr_name_list)
        is_declaration_srs_latlon = (declaration_ogr_srs.EPSGTreatsAsLatLong() 
            or declaration_ogr_srs.GetName() in latlon_sr_name_list)
        coordinates_need_swap = (
            (is_cadastre_srs_latlon and not is_declaration_srs_latlon)
            or (is_declaration_srs_latlon and not is_cadastre_srs_latlon)
        )
    # Georeference declarations
    declaration_updates_list = []
    for declaration_feature in declaration_ogr_layer:
        try:
            parcel_uid_list = declaration_feature.GetField("num_parcelles").split(";")
        except:
            parcel_uid_list = None
        farm_fid = declaration_feature.GetFID()
        farm_geom = declaration_feature.geometry()
        if farm_geom is None and parcel_uid_list is not None:
            new_geom = None
            temp_geom = None
            for parcel_uid in parcel_uid_list:
                cadastre_ogr_layer.SetAttributeFilter(f"idu = '{parcel_uid}'")
                if cadastre_ogr_layer.GetFeatureCount() < 1:
                    raise ValueError(f"Cadastral parcel '{parcel_uid}' was not found.")
                for parcel_feature in cadastre_ogr_layer:
                    parcel_geom = parcel_feature.geometry().Clone()
                    if cadastre_ogr_srs != declaration_ogr_srs:
                        if coordinates_need_swap:
                            parcel_geom.SwapXY()
                        parcel_geom.Transform(ogr_ct)
                    if new_geom is None:
                        new_geom = parcel_geom
                    else:
                        temp_geom = new_geom.Union(parcel_geom)
                        new_geom = temp_geom
            declaration_updates_list.append((farm_fid, new_geom.ExportToWkt()))
    # Write output
    declaration_pkey = declaration_ogr_layer.GetFIDColumn()
    with psycopg.connect(configuration["main_database"]["_pg_string"]) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            for entry in declaration_updates_list:
                # Vérification d'existence du lien
                cur.execute(
                    sql.SQL(
                        "UPDATE {table} SET {geom_key} = ST_GeomFromText(%s) WHERE {id_key} = %s"
                    ).format(
                        geom_key=sql.Identifier("geom"),
                        id_key=sql.Identifier(declaration_pkey),
                        table=configuration["main_database"]["_table_name_sql"]
                    ),
                    (
                        entry[1],
                        entry[0],
                    )
                )
            cur.execute("COMMIT")


# -- MAIN SCRIPT --
if (__name__ == "__main__"):
    try:
        main(sys.argv[1:])
        sys.exit(0)
    except Exception as exc:
        print(exc)
        sys.exit(1)
