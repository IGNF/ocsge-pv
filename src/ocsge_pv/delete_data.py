"""Photovoltaic farm data deleting tool

Allow to delete specific entries in the managed tables.

The only mandatory argument is the path to a JSON configuration file.
The environment variable OCSGE_PV_RESOURCE_DIR describes the path to
<repo>/src/ocsge_pv/resources or a copy of this directory. If empty or
unset, /app/src/ocsge_pv/resources will be used instead.
See cli_arg_parser for optionnal arguments.
Documentation for the configuration file is provided:
    * annotated schema:
        src/ocsge_pv/resources/delete_data_config.schema.json
    * example: tests/fixture/delete_data_config.ok_full.json

This file contains the following functions :
    * cli_arg_parser - parse CLI arguments
    * load_configuration - return validated configuration from file
    * add_ids_from_cli - add ids from CLI arguments to configuration
    * main - main function of the script
"""

# -- IMPORTS --

import argparse
import json
import logging
import os
import traceback
from copy import deepcopy
from pathlib import Path

import jsonschema

# -- GLOBALS --

NAME = "delete_data"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s(%(funcName)s) %(levelname)s: %(message)s",
)
logging.captureWarnings(True)
logger = logging.getLogger(NAME)


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
        description=("Deletes photovoltaic data objects from database"),
    )
    parser.add_argument("path", type=Path, help="the path of the configuration file for %(prog)s")
    parser.add_argument("--detections", help="Comma separated list of detections' ids")
    parser.add_argument("--declarations", help="Comma separated list of declarations' ids")
    parser.add_argument(
        "--pairs",
        help="Comma separated list of id pairs. Each pair has the form '<detection_id>-<declaration_id>'",
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
        validation_schema_path = Path(resource_dir, "delete_data_config.schema.json")
        with open(path, encoding="utf-8") as config_file:
            config_str = config_file.read()
        source_configuration = json.loads(config_str)
        with open(validation_schema_path, encoding="utf-8") as schema_file:
            schema_str = schema_file.read()
        schema = json.loads(schema_str)
        jsonschema.validate(source_configuration, schema)
        modified_configuration = {}
        modified_configuration["main_database"] = deepcopy(source_configuration["main_database"])
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
        modified_configuration["to_delete"] = {
            "declarations": set(),
            "detections": set(),
            "pairs": [],
        }
        if (
            "to_delete" in source_configuration
            and "declarations" in source_configuration["to_delete"]
        ):
            modified_configuration["to_delete"]["declarations"] = set(
                source_configuration["to_delete"]["declarations"]
            )
        if (
            "to_delete" in source_configuration
            and "detections" in source_configuration["to_delete"]
        ):
            modified_configuration["to_delete"]["detections"] = set(
                source_configuration["to_delete"]["detections"]
            )
        if "to_delete" in source_configuration and "pairs" in source_configuration["to_delete"]:
            modified_configuration["to_delete"]["pairs"] = deepcopy(
                source_configuration["to_delete"]["pairs"]
            )
        return modified_configuration
    except Exception as exc:
        logger.error(traceback.format_exc())
        raise exc


def get_ids_from_cli(arguments: argparse.Namespace) -> dict:
    """Get ids lists froom configuration object and CLI arguments

    Args:
        arguments (argparse.Namespace): result from cli_arg_parser()

    Raises:
        Exception: unidentified error

    Returns:
        dict: extracted ids, same format as in the configuration
            {
                "declarations": set(int),
                "detections": set(int),
                "pairs": [
                    {
                        "declaration": int,
                        "detection": int,
                    },
                    ...
                ],
            }
    """
    try:
        dec_set = set()
        det_set = set()
        pair_list = []
        if arguments.pairs is not None:
            for pair_str in arguments.pairs.split(","):
                pair_split = pair_str.split("-")
                pair_obj = {
                    "detection": int(pair_split[0]),
                    "declaration": int(pair_split[1]),
                }
                if pair_obj not in pair_list:
                    pair_list.append(pair_obj)
        if arguments.declarations is not None:
            for declaration_str in arguments.declarations.split(","):
                dec_set.add(int(declaration_str))
        if arguments.detections is not None:
            for detection_str in arguments.detections.split(","):
                det_set.add(int(detection_str))
    except Exception as exc:
        logger.error(traceback.format_exc())
        raise exc
    extracted_dict = {
        "declarations": dec_set,
        "detection": det_set,
        "pairs": pair_list,
    }
    return extracted_dict


def main():
    return 0
