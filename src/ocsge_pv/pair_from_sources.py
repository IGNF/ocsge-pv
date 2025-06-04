"""Photovoltaic farm data pairing tool

Establishes links between declaration data and remote detection data
when they match a same photovoltaic installation.

The only mandatory argument is the path to a JSON configuration file.
The environment variable OCSGE_PV_RESOURCE_DIR describes the path to
<repo>/src/ocsge_pv/resources or a copy of this directory. If empty or
unset, /app/src/ocsge_pv/resources will be used instead.
See cli_arg_parser for optionnal arguments.
Documentation for the configuration file is provided:
    * annotated schema: src/ocsge_pv/resources/pair_config.schema.json
    * example: tests/fixture/pair_config.ok.json

This file contains the following functions :
    * cli_arg_parser - parse CLI arguments
    * delete_before_matching - delete old conflicting declarations
    * delete_after_matching - delete conflicting pairs after matching
    * load_configuration - returns validated configuration from file
    * insert_new - write new pairs to output data table
    * main - main function of the script
"""

# -- IMPORTS --

import argparse
import json
import logging
import os
import re
import sys
import traceback
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import jsonschema
import psycopg
from osgeo import ogr, osr
from psycopg import sql

# -- GLOBALS --

NAME = "pair_from_sources"
TRACE = 5
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s(%(funcName)s) %(levelname)s: %(message)s",
)
logging.addLevelName(TRACE, "TRACE")
logging.captureWarnings(True)
logger = logging.getLogger(NAME)
ogr.UseExceptions()
osr.UseExceptions()


# -- FUNCTIONS --


def cli_arg_parser() -> argparse.Namespace:
    """Parse CLI arguments

    Args:
        * sys.argv (implicit) - CLI arguments

    Returns:
        argparse.Namespace: processed arguments
    """
    parser = argparse.ArgumentParser(
        prog=NAME,
        description=(
            "Establishes links between declaration data and remote detection data"
        ),
    )
    parser.add_argument(
        "path", type=Path, help="the path of the configuration file for %(prog)s"
    )
    parser.add_argument(
        "-v", "--verbose", dest="verbose", action="store_true", help="output more logs"
    )
    parser.add_argument(
        "-vv",
        "--very_verbose",
        dest="very_verbose",
        action="store_true",
        help="output even more logs",
    )
    return parser.parse_args()


def delete_before_matching(output_conf: dict, id_set: set[dict]) -> None:
    """Delete older conflicting declarations from the link table

    Delete the targeted declarations and their associated pairs

    Args:
        output_conf (dict): output database information
        id_set (set[int]): set of targeted declarations' identifiers
    """
    deleted_dec_count = 0
    deleted_pair_count = 0
    with psycopg.connect(output_conf["_pg_string"]) as conn:
        cur = conn.cursor()
        try:
            with conn.transaction():
                for fid in id_set:
                    logger.log(
                        TRACE, f"Deleting pairs associated with declaration {fid}."
                    )
                    cur.execute(
                        sql.SQL(
                            "DELETE FROM {table} WHERE {dec_key} = {dec_value}"
                        ).format(
                            table=sql.Identifier(
                                output_conf["schema"],
                                output_conf["tables"]["links"],
                            ),
                            dec_key=sql.Identifier("declaration_id"),
                            dec_value=sql.Placeholder("dec_value"),
                        ),
                        {"dec_value": fid},
                    )
                    pair_message = cur.statusmessage
                    pair_count_match = re.match(r"DELETE +([0-9]+)", pair_message)
                    pair_count_str = pair_count_match.group(1)
                    pair_count_int = int(pair_count_str)
                    deleted_pair_count += pair_count_int
                    logger.log(TRACE, f"Deleting declaration {fid}.")
                    cur.execute(
                        sql.SQL(
                            "DELETE FROM {table} WHERE {dec_key} = {dec_value}"
                        ).format(
                            table=sql.Identifier(
                                output_conf["schema"],
                                output_conf["tables"]["declarations"],
                            ),
                            dec_key=sql.Identifier("id_dossier"),
                            dec_value=sql.Placeholder("dec_value"),
                        ),
                        {"dec_value": fid},
                    )
                    deleted_dec_count += 1
        except Exception as exc:
            logger.error(traceback.format_exc())
            conn.rollback()
            raise exc
    logger.debug(f"{deleted_dec_count} declarations deleted from database.")
    logger.debug(f"{deleted_pair_count} linked pairs deleted from database.")


def delete_after_matching(output_conf: dict, link_set: set[tuple]) -> None:
    """Delete older conflicting pairs from the link table

    Args:
        output_conf (dict): output database information
        link_set (set[tuple]): set of pairs to delete, in the form
            (declaration_id: int, detection_id: int)
    """
    deleted_pairs_count = 0
    with psycopg.connect(output_conf["_pg_string"]) as conn:
        cur = conn.cursor()
        try:
            with conn.transaction():
                for link_tuple in link_set:
                    logger.log(TRACE, f"Deleting pair {link_tuple}.")
                    cur.execute(
                        sql.SQL(
                            "DELETE FROM {table} WHERE {dec_key} = %s AND {det_key} = %s"
                        ).format(
                            table=sql.Identifier(
                                output_conf["schema"],
                                output_conf["tables"]["links"],
                            ),
                            dec_key=sql.Identifier("declaration_id"),
                            det_key=sql.Identifier("detection_id"),
                        ),
                        link_tuple,
                    )
                    message = cur.statusmessage
                    count_match = re.match(r"DELETE +([0-9]+)", message)
                    count_str = count_match.group(1)
                    count_int = int(count_str)
                    deleted_pairs_count += count_int
        except Exception as exc:
            logger.error(traceback.format_exc())
            conn.rollback()
            raise exc
    logger.debug(f"{deleted_pairs_count} pairs deleted from database.")


def insert_new(output_conf: dict, link_set: set[tuple]) -> None:
    """Insert new pairs in the link table

    Args:
        output_conf (dict): output database information
        link_set (set[tuple]): set of pairs to insert, in the form
            (declaration_id: int, detection_id: int)
    """
    new_pairs_count = 0
    with psycopg.connect(output_conf["_pg_string"]) as conn:
        cur = conn.cursor()
        try:
            with conn.transaction():
                for link_tuple in link_set:
                    logger.log(TRACE, f"Inserting pair {link_tuple}.")
                    cur.execute(
                        sql.SQL(
                            "INSERT INTO {table} ({dec_key}, {det_key}) VALUES (%s, %s)"
                        ).format(
                            table=sql.Identifier(
                                output_conf["schema"],
                                output_conf["tables"]["links"],
                            ),
                            dec_key=sql.Identifier("declaration_id"),
                            det_key=sql.Identifier("detection_id"),
                        ),
                        link_tuple,
                    )
                    new_pairs_count += 1
        except Exception as exc:
            logger.error(traceback.format_exc())
            conn.rollback()
            raise exc
    logger.debug(f"{new_pairs_count} new pairs inserted in database.")


def load_configuration(path: Path) -> dict:
    """Returns validated configuration from file

    Args:
        path (str): path to the configuration file

    Raises:
        jonschema.ValidationError: The configuration file does not
            match the validation schema

    Returns:
        Dict: the configuration object translated from the input file
    """
    try:
        resource_dir = os.environ.get("OCSGE_PV_RESOURCE_DIR")
        if resource_dir is None or resource_dir.strip() == "":
            resource_dir = "/app/src/ocsge_pv/resources"
        validation_schema_path = Path(resource_dir, "pair_config.schema.json")
        with open(path, encoding="utf-8") as config_file:
            config_str = config_file.read()
        source_configuration = json.loads(config_str)
        with open(validation_schema_path, encoding="utf-8") as schema_file:
            schema_str = schema_file.read()
        schema = json.loads(schema_str)
        jsonschema.validate(source_configuration, schema)
        modified_configuration = deepcopy(source_configuration)
        modified_configuration["main_database"]["_pg_string"] = (
            "host="
            + modified_configuration["main_database"]["host"]
            + " port="
            + str(modified_configuration["main_database"]["port"])
            + " dbname="
            + modified_configuration["main_database"]["name"]
            + " user="
            + modified_configuration["main_database"]["user"]
            + " password="
            + modified_configuration["main_database"]["password"]
        )
        return modified_configuration
    except Exception as exc:
        logger.error(traceback.format_exc())
        raise exc


# -- PROCESSING FUNCTIONS --


def check_declared_parcels(data_layer: ogr.Layer) -> set[int]:
    """Check for duplicate parcels in declarations

    When multiple declarations, for the same installation date,
    have at least one common selected parcel, only the most recent
    declaration is deemed correct. The rest is discarded, and thus
    marked for deletion.

    Args:
        data_layer (ogr.Layer): declarations data layer

    Returns:
        set: id sequence for declarations to delete
    """
    # Create a parcels dict with a more useful structure
    parcels_dict = {}
    for feature in data_layer:
        feature_id = feature.GetFID()
        parcels_list = feature.GetField("num_parcelles").split(";")
        feature_year = feature.GetFieldAsDateTime("date_insta")[0]
        feature_creation_date = feature.GetField("creation").replace("/", "-")
        for parcel_idu in parcels_list:
            if parcel_idu not in parcels_dict:
                parcels_dict[parcel_idu] = {}
            if feature_year not in parcels_dict[parcel_idu]:
                parcels_dict[parcel_idu][feature_year] = {}
            parcels_dict[parcel_idu][feature_year][feature_creation_date] = feature_id
    # Create and fill the set of id to delete
    deletion_set = set()
    for idu in list(parcels_dict):
        for year in list(parcels_dict[idu]):
            # Check declarations for a specific parcel and installation year
            # Find the most recent declaration in this setting
            last_creation = None
            for creation_iso in list(parcels_dict[idu][year]):
                creation_object = datetime.fromisoformat(creation_iso)
                if last_creation is None or last_creation < creation_object:
                    last_creation = creation_object
            # Mark any older declaration for deletion
            for creation_iso in list(parcels_dict[idu][year]):
                creation_object = datetime.fromisoformat(creation_iso)
                detection_id = parcels_dict[idu][year][creation_iso]
                if creation_object < last_creation:
                    deletion_set.add(detection_id)
    return deletion_set


def match_dec_to_det(
    dec_layer: ogr.Layer,
    det_layer: ogr.Layer,
    link_layer: ogr.Layer,
    transform: osr.CoordinateTransformation,
    need_swap: bool,
) -> dict[set[dict]]:
    """Declarations VS detections matching function

    Args:
        dec_layer (ogr.Layer): declarations OGR layer
        det_layer (ogr.Layer): detections OGR layer
        link_layer (ogr.Layer): pairings OGR layer
        transform (osr.CoordinateTransformation): OSR coordinates
            transformation from declaration to detection
        need_swap (bool): axis swapping need in this transformation

    Returns:
        dict: pairs to create or delete
            {
                "new": set(
                    (declaration_fid: int, detection_fid: int),
                    ...
                ),
                "del": set(
                    (declaration_fid: int, detection_fid: int),
                    ...
                )
            }
    """
    result = {"new": set(), "del": set()}
    for det_feature in det_layer:
        linked_dec_dict = {}
        old_linked_dec_set = set()
        det_fid = det_feature.GetFID()
        det_geom = det_feature.GetGeometryRef().Clone()
        link_layer.SetAttributeFilter(f"detection_id = {det_fid}")
        for link_feature in link_layer:
            dec_fid = link_feature.GetField("declaration_id")
            dec_feature = dec_layer.GetFeature(dec_fid)
            if dec_feature is None:
                logger.warning(
                    f"Link between detection {det_fid} and missing declaration {dec_fid} will be deleted."
                )
                link_tuple = (dec_fid, det_fid)
                result["del"].add(link_tuple)
            else:
                creation_iso = dec_feature.GetField("creation").replace("/", "-")
                installation_iso = dec_feature.GetField("date_insta").replace("/", "-")
                linked_dec_dict[dec_fid] = {
                    "creation": datetime.fromisoformat(creation_iso),
                    "installation": datetime.fromisoformat(installation_iso),
                }
            old_linked_dec_set.add(dec_fid)
        for dec_feature in dec_layer:
            dec_year = dec_feature.GetFieldAsDateTime("date_insta")[0]
            dec_geom = dec_feature.GetGeometryRef().Clone()
            if dec_geom is not None and det_feature.GetField("millesime") >= dec_year:
                if need_swap:
                    dec_geom.SwapXY()
                if transform is not None:
                    dec_geom.Transform(transform)
                if det_geom.Intersects(dec_geom):
                    creation_iso = dec_feature.GetField("creation").replace("/", "-")
                    installation_iso = dec_feature.GetField("date_insta").replace(
                        "/", "-"
                    )
                    linked_dec_dict[dec_feature.GetFID()] = {
                        "creation": datetime.fromisoformat(creation_iso),
                        "installation": datetime.fromisoformat(installation_iso),
                    }
        latest_fid = None
        for dec_fid in list(linked_dec_dict):
            dec_feature = dec_layer.GetFeature(dec_fid)
            creation_iso = dec_feature.GetField("creation").replace("/", "-")
            creation_dt = datetime.fromisoformat(creation_iso)
            installation_iso = dec_feature.GetField("date_insta").replace("/", "-")
            installation_dt = datetime.fromisoformat(installation_iso)
            if linked_dec_dict[dec_fid] is None:
                linked_dec_dict[dec_fid] = {
                    "creation": creation_dt,
                    "installation": installation_dt,
                }
            if (
                latest_fid is None
                or linked_dec_dict[latest_fid]["creation"] < creation_dt
            ):
                latest_fid = dec_fid
        for dec_fid in list(linked_dec_dict):
            # (declaration_fid, detection_fid) tuple
            link_tuple = (dec_fid, det_fid)
            if dec_fid != latest_fid:
                result["del"].add(link_tuple)
            elif dec_fid not in old_linked_dec_set:
                result["new"].add(link_tuple)
        link_layer.SetAttributeFilter(None)
    return result


# -- MAIN FUNCTION --


def main() -> int:
    """Main routine, entrypoint for the program

    Args:
        path (str): path to the configuration file
            (implicit, contained in sys.argv[])

    Returns:
        int: shell exit code of the execution
    """
    try:
        logger.info("Start of declarations' pairing with detections.")
        cli_args = cli_arg_parser()
        log_level_description = "normal"
        if cli_args.very_verbose:
            logger.setLevel(logging.getLevelName("TRACE"))
            log_level_description = "very verbose"
        elif cli_args.verbose:
            logger.setLevel(logging.DEBUG)
            log_level_description = "verbose"
        logger.info(
            f"Logging level: '{logger.getEffectiveLevel()}' ({log_level_description})"
        )
        # Read configuration
        logger.info("Loading configuration...")
        configuration = load_configuration(cli_args.path)
        # OGR layers and spatial references
        logger.info("Preparing OGR entities...")
        latlon_sr_name_list = ["WGS 84"]
        ogr_pg_connection = ogr.Open(
            "PG: " + configuration["main_database"]["_pg_string"]
        )
        ## Declarations layer
        declaration_table = ".".join(
            (
                configuration["main_database"]["schema"],
                configuration["main_database"]["tables"]["declarations"],
            )
        )
        declaration_ogr_layer = ogr_pg_connection.GetLayerByName(declaration_table)
        if declaration_ogr_layer is None:
            raise Exception(f"Declaration layer '{declaration_table}' was not loaded.")
        logger.log(
            TRACE,
            f"FID column for declaration layer: '{declaration_ogr_layer.GetFIDColumn()}'",
        )
        declaration_osr_sr = declaration_ogr_layer.GetSpatialRef()
        if declaration_osr_sr is None:
            raise Exception(
                f"Spatial reference for declaration layer '{declaration_table}' was not found."
            )
        is_declaration_sr_latlon = (
            declaration_osr_sr.EPSGTreatsAsLatLong()
            or declaration_osr_sr.GetName() in latlon_sr_name_list
        )
        logger.debug(f"Declarations layer's SRS: {declaration_osr_sr.GetName()}")
        ## Detections layer
        detection_table = ".".join(
            (
                configuration["main_database"]["schema"],
                configuration["main_database"]["tables"]["detections"],
            )
        )
        detection_ogr_layer = ogr_pg_connection.GetLayerByName(detection_table)
        if detection_ogr_layer is None:
            raise Exception(f"Detection layer '{detection_table}' was not loaded.")
        logger.log(
            TRACE,
            f"FID column for detection layer: '{detection_ogr_layer.GetFIDColumn()}'",
        )
        detection_osr_sr = detection_ogr_layer.GetSpatialRef()
        if detection_osr_sr is None:
            raise Exception(
                f"Spatial reference for detection layer '{detection_table}' was not found."
            )
        is_detection_sr_latlon = (
            detection_osr_sr.EPSGTreatsAsLatLong()
            or detection_osr_sr.GetName() in latlon_sr_name_list
        )
        logger.debug(f"Detections layer's SRS: {detection_osr_sr.GetName()}")
        ## Pairing layer
        pairing_table = ".".join(
            (
                configuration["main_database"]["schema"],
                configuration["main_database"]["tables"]["links"],
            )
        )
        pairing_ogr_layer = ogr_pg_connection.GetLayerByName(pairing_table)
        if pairing_ogr_layer is None:
            raise Exception(f"Pairing layer '{pairing_table}' was not loaded.")
        ## Coordinates transformations
        coordinates_transformation = None
        need_coordinates_swap = (
            False  # True if the two spatial references use a different axis order
        )
        if detection_osr_sr != declaration_osr_sr:
            logger.debug("Coordinates transformation is necessary.")
            coordinates_transformation = osr.CoordinateTransformation(
                declaration_osr_sr, detection_osr_sr
            )
            need_coordinates_swap = (
                is_detection_sr_latlon and not is_declaration_sr_latlon
            ) or (is_declaration_sr_latlon and not is_detection_sr_latlon)
            if need_coordinates_swap:
                logger.debug(
                    "Axis order swapping is necessary for this transformation."
                )
        # Check for duplicates in declarations
        logger.info("Checking for conflicting declarations...")
        dupe_dec_set = check_declared_parcels(declaration_ogr_layer)
        logger.info("Deleting conflicting declarations from database...")
        delete_before_matching(configuration["main_database"], dupe_dec_set)
        # Pairing
        logger.info("Matching pairs...")
        match_dict = match_dec_to_det(
            declaration_ogr_layer,
            detection_ogr_layer,
            pairing_ogr_layer,
            coordinates_transformation,
            need_coordinates_swap,
        )
        logger.info("Writing new pairs in database...")
        insert_new(configuration["main_database"], match_dict["new"])
        logger.info("Deleting conflicting pairs from database...")
        delete_after_matching(configuration["main_database"], match_dict["del"])
        logger.info("End of declarations' pairing with detections.")
        return 0
    except Exception:
        logger.error(traceback.format_exc())
        return 1


# -- MAIN SCRIPT --


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
