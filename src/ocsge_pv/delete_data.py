"""Photovoltaic farm data deleting tool

Allow to delete specific entries in the managed tables.

The only mandatory argument is the path to a JSON configuration file.
The environment variable OCSGE_PV_RESOURCE_DIR describes the path to
<repo>/src/ocsge_pv/resources or a copy of this directory. If empty or
unset, /app/src/ocsge_pv/resources will be used instead.
See cli_arg_parser for optionnal arguments.
Documentation for the configuration file is provided:
    * annotated schema: src/ocsge_pv/resources/delete_data_config.schema.json
    * example: tests/fixture/delete_data_config.ok.json

This file contains the following functions :
    * cli_arg_parser - parse CLI arguments
    * load_configuration - returns validated configuration from file
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
        description=("Establishes links between declaration data and remote detection data"),
    )
    parser.add_argument("path", type=Path, help="the path of the configuration file for %(prog)s")
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
