"""Describes the ocsge_pv.pair_from_sources module.


"""

# -- IMPORTS --
# standard library
import argparse
from copy import deepcopy
from datetime import date, datetime
import json
import logging
import os
from pathlib import Path
import traceback
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

# 3rd party
from osgeo import ogr, osr
import jsonschema
import psycopg
from psycopg import sql

# -- GLOBALS --
NAME = "pair_from_sources"
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(name)s(%(funcName)s) %(levelname)s: %(message)s")
logging.captureWarnings(True)
logger = logging.getLogger(NAME)
ogr.UseExceptions()
osr.UseExceptions()
try:
    timezone_name = os.environ["TZ"]
    print(f"Zone horaire définie par VE : '{timezone_name}'")
except KeyError:
    timezone_name = "Europe/Paris"
    print(f"Zone horaire définie par défaut : '{timezone_name}'")
timezone_info = ZoneInfo(timezone_name)

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
            "Ensure that declarations have a geomtry based on intersected cadastral parcels"
        )
    )
    parser.add_argument("path",
        type=Path,
        help="the path of the configuration file for %(prog)s"
    )
    parser.add_argument("-v", "--verbose",
        dest="verbose",
        action="store_true",
        help="output more logs"
    )
    return parser.parse_args()

def load_configuration(path: Path) -> Dict:
    """Returns validated configuration from file
    
    Args:
        path (str): path to the configuration file
    
    Raises:
        jonschema.ValidationError: The configuration file does not match the validation schema

    Returns:
        Dict: the configuration object translated from the input file
    """
    try:
        validation_schema_path = Path(os.environ["HOME"],
            "ocsge-pv-resources/pair_config.schema.json")
        with open(path, "r", encoding="utf-8") as config_file:
            config_str = config_file.read()
        source_configuration = json.loads(config_str)
        with open(validation_schema_path, "r", encoding="utf-8") as schema_file:
            schema_str = schema_file.read()
        schema = json.loads(schema_str)
        jsonschema.validate(source_configuration, schema)
        modified_configuration = deepcopy(source_configuration)
        modified_configuration["main_database"]["_pg_string"] = (
            "host=" + modified_configuration['main_database']['host']
            + " port=" + str(modified_configuration['main_database']['port'])
            + " dbname=" + modified_configuration['main_database']['name']
            + " user=" + modified_configuration['main_database']['user']
            + " password=" + modified_configuration['main_database']['password'])
        return modified_configuration
    except Exception as exc:
        logger.error(traceback.format_exc())
        raise exc

def write_output(output_conf: Dict, out_link_list: List[Tuple]) -> None:
    """Write pairings to database, in the link table
    
    Args:
        output_conf (Dict): configuration used to access the output database
        update_list (List[Tuple]): list of (fid, geometry) of declarations to update
        declaration_pkey (str): name of the private key column for declarations
    """
    with psycopg.connect(output_conf["_pg_string"]) as conn:
        cur = conn.cursor()
        try:
            with conn.transaction():
                for link_obj in out_link_list:
                    # Vérification d'existence du lien
                    cur.execute(
                        sql.SQL(
                            "SELECT * FROM {table} WHERE {decl_key} = %s AND {dete_key} = %s"
                        ).format(
                            table=sql.Identifier(output_conf["schema"],
                                output_conf["tables"]["links"]),
                            decl_key=sql.Identifier(out_link_declar_fkey),
                            dete_key=sql.Identifier(out_link_detect_fkey)
                        ),
                        (
                            link_obj[out_link_declar_fkey],
                            link_obj[out_link_detect_fkey]
                        )
                    )
                    result = cur.fetchone()
                    # Ajout si inexistant
                    if result is None:
                        cur.execute(
                            sql.SQL(
                                "INSERT INTO {table} ({decl_key}, {dete_key}) VALUES (%s, %s)"
                            ).format(
                                table=sql.Identifier(output_conf["schema"],
                                    output_conf["tables"]["links"]),
                                decl_key=sql.Identifier(out_link_declar_fkey),
                                dete_key=sql.Identifier(out_link_detect_fkey)
                            ),
                            (
                                link_obj[out_link_declar_fkey],
                                link_obj[out_link_detect_fkey]
                            )
                        )
        except Exception as exc:
            logger.error(traceback.format_exc())
            conn.rollback()
            raise exc

# -- MAIN FUNCTION --
def main() -> None:
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
        if cli_args.verbose:
            logger.setLevel(logging.DEBUG)
        # Read configuration
        logger.debug("Loading configuration...")
        configuration = load_configuration(cli_args.path)
        # OGR layers and spatial references
        logger.debug("Preparing OGR entities...")
        latlon_sr_name_list = ['WGS 84']
        ogr_pg_connection = ogr.Open(("PG: " + configuration["main_database"]["_pg_string"]))
        ## Declarations layer
        declaration_table = ".".join(configuration["main_database"]["schema"],
            configuration["main_database"]["tables"]["declararations"])
        declaration_ogr_layer = ogr_pg_connection.GetLayerByName(declaration_table)
        if declaration_ogr_layer is None:
            raise Exception(f"Declaration layer '{declaration_table}' was not loaded.")
        declaration_osr_sr = declaration_ogr_layer.GetSpatialRef()
        if declaration_osr_sr is None:
            raise Exception(
                f"Spatial reference for declaration layer '{declaration_table}' was not found.")
        is_declaration_sr_latlon = (declaration_osr_sr.EPSGTreatsAsLatLong()
            or declaration_osr_sr.GetName() in latlon_sr_name_list)
        ## Detections layer
        detection_table = ".".join(configuration["main_database"]["schema"],
            configuration["main_database"]["tables"]["detections"])
        detection_ogr_layer = ogr_pg_connection.GetLayerByName(detection_table)
        if detection_ogr_layer is None:
            raise Exception(f"Detection layer '{detection_table}' was not loaded.")
        detection_osr_sr = detection_ogr_layer.GetSpatialRef()
        if detection_osr_sr is None:
            raise Exception(
                f"Spatial reference for detection layer '{detection_table}' was not found.")
        is_detection_sr_latlon = (detection_osr_sr.EPSGTreatsAsLatLong()
            or detection_osr_sr.GetName() in latlon_sr_name_list)
        ## Pairing layer
        pairing_table = ".".join(configuration["main_database"]["schema"],
            configuration["main_database"]["tables"]["links"])
        pairing_ogr_layer = ogr_pg_connection.GetLayerByName(pairing_table)
        if pairing_ogr_layer is None:
            raise Exception(f"Pairing layer '{pairing_table}' was not loaded.")
        ## Coordinates transformations
        coordinates_transformation = None
        need_coordinates_swap = False # True if the two spatial references use a different axis order
        if detection_osr_sr != declaration_osr_sr:
            coordinates_transformation = osr.CoordinateTransformation(
                declaration_osr_sr, detection_osr_sr)
            need_coordinates_swap = (
                (is_detection_sr_latlon and not is_declaration_sr_latlon)
                or (is_declaration_sr_latlon and not is_detection_sr_latlon)
            )
        # Data fetching
        logger.debug("Fetching source data...")
        ## Declarations (with non-null geometries and installation dates)
        declaration_dict = {}
        for farm_feature in declaration_ogr_layer:
            farm_id = farm_feature.GetFID()
            if (farm_feature.geometry() is not None 
                    and farm_feature.GetField('date_insta') is not None):
                iso_installation_date = farm_feature.GetField('date_insta').replace("/", "-")
                declaration_dict[farm_id] = {
                    "installation_date": date.fromisoformat(iso_installation_date),
                    "geom": farm_feature.geometry().Clone(),
                }
                if coordinates_transformation is not None:
                    new_geom = declaration_dict[farm_id]["geom"].Clone()
                    if need_coordinates_swap:
                        new_geom.SwapXY()
                    new_geom.Transform(coordinates_transformation)
                    declaration_dict[farm_id]["geom"] = new_geom.Clone()
        ## Detections
        detection_dict = {}
        for farm_feature in detection_ogr_layer:
            farm_id = farm_feature.GetFID()
            detection_dict[farm_id] = {
                "millesime": farm_feature.GetField("millesime"),
            }
            detection_dict[farm_id]["geom"] = farm_feature.geometry().Clone()
        ogr_pg_connection = None
        # Pairing
        logger.debug("Computing pairs...")
        out_link_list = []
        for detection_id in detection_dict.keys():
            for declaration_id in declaration_dict.keys():
                if declaration_dict[declaration_id]["geom"] is not None:
                    # Spatial intersection
                    geom_intersect_bool = detection_dict[detection_id]["geom"].Intersects(
                        declaration_dict[declaration_id]["geom"]
                    )
                    # Temporal intersection
                    install_year = declaration_dict[declaration_id]["installation_date"].year
                    detection_year = int(detection_dict[detection_id]["millesime"])
                    time_intersect_bool = (detection_year >= install_year)
                    # Conclusion
                    is_pair = geom_intersect_bool and time_intersect_bool
                    if is_pair:
                        link_obj = {}
                        link_obj[out_link_declar_fkey] = declaration_id
                        link_obj[out_link_detect_fkey] = detection_id
                        out_link_list.append(link_obj)
        logger.debug("Writing pairs in database...")
        write_output(configuration["main_database"], out_link_list)
        logger.info("End of declarations' pairing with detections.")
        return 0
    except Exception as exc:
        logger.error(traceback.format_exc())
        return 1


# -- MAIN SCRIPT --
if (__name__ == "__main__"):
    exit_code = main()
    sys.exit(exit_code)