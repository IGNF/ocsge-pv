"""Photovoltaic farm data cleaning tool

Process conflicts, duplicates, and other complex pairing cases.

The only mandatory argument is the path to a JSON configuration file.
The environment variable OCSGE_PV_RESOURCE_DIR describes the path to
<repo>/src/ocsge_pv/resources or a copy of this directory. If empty or
unset, /app/src/ocsge_pv/resources will be used instead.
See cli_arg_parser for optionnal arguments.
Documentation for the configuration file is provided:
    * annotated schema: src/ocsge_pv/resources/clean_data_config.schema.json
    * example: tests/fixture/clean_data_config.ok.json

This file contains the following functions :
    * cli_arg_parser - parse CLI arguments
    * get_declared_parcels - reference parcels used in declarations
    * get_detected_parcels - reference parcels used in detections
    * identify_to_delete - identify which entities should be deleted
    * load_configuration - return validated configuration from file
    * main - main function of the script
"""

# -- IMPORTS --

import argparse
import json
import logging
import os
import sys
import traceback
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import jsonschema
from osgeo import ogr, osr

# -- GLOBALS --

NAME = "clean_data"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s(%(funcName)s) %(levelname)s: %(message)s",
)
logging.captureWarnings(True)
logger = logging.getLogger(NAME)
ogr.UseExceptions()
osr.UseExceptions()


# -- SCRIPT LOADING FUNCTIONS --
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
    return parser.parse_args()


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
        validation_schema_path = Path(resource_dir, "clean_data_config.schema.json")
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
        modified_configuration["cadastre_database"]["_pg_string"] = (
            "host="
            + modified_configuration["cadastre_database"]["host"]
            + " port="
            + str(modified_configuration["cadastre_database"]["port"])
            + " dbname="
            + modified_configuration["cadastre_database"]["name"]
            + " user="
            + modified_configuration["cadastre_database"]["user"]
            + " password="
            + modified_configuration["cadastre_database"]["password"]
        )
        return modified_configuration
    except Exception as exc:
        logger.error(traceback.format_exc())
        raise exc


# -- PROCESSING FUNCTIONS --

def identify_to_delete(
    declaration_parcels: dict,
    detection_parcels: dict,
    declaration_layer: ogr.Layer,
    detection_layer: ogr.Layer,
    link_layer: ogr.Layer,
) -> dict:
    """Identifies which entities should be deleted

    Args:
        declaration_parcels (Dict): parcels associated to declarations
        detection_parcels (Dict): parcels associated to declarations
        declaration_layer (ogr.Layer): declarations data layer
        detection_layer (ogr.Layer): detections data layer
        link_layer (ogr.Layer): pairings data layer

    Returns:
        Dict: identifiers of entities marked for deletion
    """
    to_delete_dict = {
        "declaration": [],
        "detection": [],
        "link": [],
    }
    for idu in iter(declaration_parcels):

        print()
        # if idu in detection_parcels and len(detection_parcels[idu]) > 1:
        #     # a parcel selected in a declaration intersects several detections
        #     detection_year_list = []
        #     for detection_id in detection_parcels[idu]:
        #         detection_feature = detection_layer.GetFeature(detection_id)
        #         detection_year = detection_feature.GetField("millesime")
        #         if detection_year not in detection_year_list:
        #             detection_year_list.append(detection_year)

    return to_delete_dict


def get_declared_parcels(data_layer: ogr.Layer) -> dict:
    """References parcels used in declarations

    Output structure is as following :

    {
        <parcel's idu>: {
            <installation year>: [
                (<declaration's id>, <declaration's last update),
                ...
            ]
        }
    }

    Args:
        data_layer (ogr.Layer): declarations data layer

    Returns:
        Dict: found parcels, with associated declarations
    """
    parcels_dict = {}
    for feature in data_layer:
        feature_id = feature.GetFID()
        parcels_list = feature.GetField("num_parcelles").split(";")
        feature_year = feature.GetFieldAsDateTime("date_insta")[0]
        # feature_last_update = datetime.fromisoformat(
        #     feature.GetFieldAsISO8601DateTime("last_update"))
        feature_last_update = (
            None  # Real value is not currently available in the database model
        )
        for parcel_idu in parcels_list:
            if parcel_idu not in parcels_dict:
                parcels_dict[parcel_idu] = []
            if feature_year not in parcels_dict[parcel_idu]:
                parcels_dict[parcel_idu][feature_year] = []
            new_item = (feature_id, feature_last_update)
            parcels_dict[parcel_idu][feature_year].append(new_item)
    return parcels_dict


def get_detected_parcels(data_layer: ogr.Layer, ref_layer: ogr.Layer) -> dict:
    """References parcels used in detections

    Output structure is as following :

    {
        <parcel's idu>: {
            <detection year>: [
                (<detection's id>, <detection's last update),
                ...
            ]
        }
    }

    Args:
        data_layer (ogr.Layer): detections data layer
        ref_layer (ogr.Layer): parcels reference data layer

    Returns:
        Dict: found parcels, with associated detections
    """
    parcels_dict = {}
    for feature in data_layer:
        feature_id = feature.GetFID()
        feature_geom = feature.geometry().Clone()
        if detection_to_parcel_ogr_cr is not None:
            if parcel_to_detection_swap:
                feature_geom.SwapXY()
            feature_geom.Transform(detection_to_parcel_ogr_cr)
        feature_year = feature.GetField("millesime")
        feature_last_update = datetime.fromisoformat(
            feature.GetFieldAsISO8601DateTime("dern_modif")
        )
        ref_layer.SetSpatialFilter(feature_geom)
        # ogr.Layer.SetSpatialFilter(geom) is not precise
        # consider switching to a postgis ST_Intersects in a "WHERE" clause
        for parcel_feature in ref_layer:
            parcel_idu = parcel_feature.GetField("idu")
            if parcel_idu not in parcels_dict:
                parcels_dict[parcel_idu] = []
            if feature_year not in parcels_dict[parcel_idu]:
                parcels_dict[parcel_idu][feature_year] = []
            new_item = (feature_id, feature_last_update)
            parcels_dict[parcel_idu][feature_year].append(new_item)
    return parcels_dict


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
        logger.info("Start of data cleaning.")
        cli_args = cli_arg_parser()
        log_level_description = "normal"
        if cli_args.verbose:
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
        main_ogr_ds = ogr.Open("PG: " + configuration["main_database"]["_pg_string"])
        ref_ogr_ds = ogr.Open("PG: " + configuration["cadastre_database"]["_pg_string"])
        ## Declarations layer
        declaration_table = ".".join(
            (
                configuration["main_database"]["schema"],
                configuration["main_database"]["tables"]["declarations"],
            )
        )
        declaration_ogr_layer = main_ogr_ds.GetLayerByName(declaration_table)
        if declaration_ogr_layer is None:
            raise Exception(f"Declaration layer '{declaration_table}' was not loaded.")
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
        detection_ogr_layer = main_ogr_ds.GetLayerByName(detection_table)
        if detection_ogr_layer is None:
            raise Exception(f"Detection layer '{detection_table}' was not loaded.")
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
        pairing_ogr_layer = main_ogr_ds.GetLayerByName(pairing_table)
        if pairing_ogr_layer is None:
            raise Exception(f"Pairing layer '{pairing_table}' was not loaded.")
        ## Parcels layer
        parcel_table = ".".join(
            (
                configuration["cadastre_database"]["schema"],
                configuration["cadastre_database"]["table"],
            )
        )
        parcel_ogr_layer = ref_ogr_ds.GetLayerByName(parcel_table)
        if parcel_ogr_layer is None:
            raise Exception(f"Parcels layer '{parcel_table}' was not loaded.")
        parcel_osr_sr = parcel_ogr_layer.GetSpatialRef()
        if parcel_osr_sr is None:
            raise Exception(
                f"Spatial reference for parcels layer '{parcel_table}' was not found."
            )
        is_parcel_sr_latlon = (
            parcel_osr_sr.EPSGTreatsAsLatLong()
            or parcel_osr_sr.GetName() in latlon_sr_name_list
        )
        logger.debug(f"Detections layer's SRS: {parcel_osr_sr.GetName()}")
        ## Coordinates transformations
        declaration_to_detection_ogr_cr = None
        declaration_to_detection_swap = False  # True if CRS' axis orders are different
        if detection_osr_sr != declaration_osr_sr:
            logger.debug(
                "Coordinates transformation is needed from declarations to detections."
            )
            declaration_to_detection_ogr_cr = osr.CoordinateTransformation(
                declaration_osr_sr, detection_osr_sr
            )
            declaration_to_detection_swap = (
                is_detection_sr_latlon and not is_declaration_sr_latlon
            ) or (is_declaration_sr_latlon and not is_detection_sr_latlon)
            if declaration_to_detection_swap:
                logger.debug(
                    "Axis order swapping is necessary for this transformation."
                )
        parcel_to_detection_ogr_cr = None
        parcel_to_detection_swap = False  # True if CRS' axis orders are different
        if detection_osr_sr != parcel_osr_sr:
            logger.debug(
                "Coordinates transformation is needed from parcels to detections."
            )
            parcel_to_detection_ogr_cr = osr.CoordinateTransformation(
                parcel_osr_sr, detection_osr_sr
            )
            detection_to_parcel_ogr_cr = osr.CoordinateTransformation(
                detection_osr_sr, parcel_osr_sr
            )
            parcel_to_detection_swap = (
                is_detection_sr_latlon and not is_parcel_sr_latlon
            ) or (is_parcel_sr_latlon and not is_detection_sr_latlon)
            if parcel_to_detection_swap:
                logger.debug(
                    "Axis order swapping is necessary for this transformation."
                )
        # Data fetching
        logger.info("Fetching source data...")
        declared_parcel_dict = get_declared_parcels(declaration_ogr_layer)
        detected_parcel_dict = get_detected_parcels(
            detection_ogr_layer, parcel_ogr_layer
        )
        to_delete_dict = {
            "declaration": [],
            "detection": [],
            "link": [],
        }
        to_delete_dict = identify_to_delete(
            to_delete_dict,
            declared_parcel_dict,
            detected_parcel_dict,
            declaration_ogr_layer,
            detection_ogr_layer,
            pairing_ogr_layer,
        )
        # End
        logger.info("End of data cleaning.")
        return 0
    except Exception:
        logger.error(traceback.format_exc())
        return 1


# -- MAIN SCRIPT --

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
