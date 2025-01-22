"""Provides an executable to add geometries to declared photovoltaic installations.
"""

# -- IMPORTS --

# standard library
from datetime import date, datetime
import json
import os
import re
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
def load_configuration(path: str) -> object:
    """Returns validated configuration from file
    
    Args:
        path (str): path to the configuration file
    
    Raises:
        jonschema.ValidationError: The configuration file does not match the validation schema

    Returns:
        object: the configuration object translated from the input file
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

# -- MAIN SCRIPT --
