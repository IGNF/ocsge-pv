"""Provides an executable to add geometries to declared photovoltaic installations.
"""

# -- IMPORTS --
# standard library
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
    configuration = json.loads(config_str)
    with open(validation_schema_path, "r", encoding="utf-8") as schema_file:
        schema_str = schema_file.read()
    schema = json.loads(schema_str)
    jsonschema.validate(configuration, schema)
    return configuration


# -- MAIN FUNCTION --
def main(configuration_file_path: str) -> None:
    """Main routine, entrypoint for the program
        
    Args:
        configuration_file_path (str): path to the configuration file
    """
    configuration = load_configuration(configuration_file_path)
    main_db_connection_string=("host=" + configuration['main_database']['host']
        + " port=" + str(configuration['main_database']['port'])
        + " dbname=" + configuration['main_database']['name']
        + " user=" + configuration['main_database']['user']
        + " password=" + configuration['main_database']['password'])
    with psycopg.connect(main_db_connection_string) as conn:
        with conn.cursor() as cur:
            print()


# -- MAIN SCRIPT --
if (__name__ == "__main__"):
    try:
        main(sys.argv[1:])
        sys.exit(0)
    except Exception as exc:
        print(exc)
        sys.exit(1)
