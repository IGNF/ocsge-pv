"""Describes unit tests for the ocsge_pv.geometrize_declarations module.

There is one test class for each tested functionnality.
See internal docstrings for more information.
Each variable prefixed by "m_" is a mock, or part of it.
Each variable prefixed by "f_" is a fixture.
"""

from unittest import TestCase, mock
from unittest.mock import MagicMock, call, mock_open

import pytest
import psycopg

import ocsge_pv.geometrize_declarations as TM # tested module

# TODO Features to test :
# * read configuration
# * connect to database
# * read photovoltaic input table
# * check if geometry is initialised
# * read cadastral input table
# * convert between spatial reference systems with axis permutation
# * convert between spatial reference systems without axis permutation
# * compute geometry
# * write in photovoltaic output table (same one as input)

# Fixtures
## Configuration file path
f_config_path = "/tmp/conf/geometrize.json"
## Configuration file, nominal
f_config_ok_raw = ""
with open("./fixtures/geometrize_config_ok.json", "r", encoding="utf-8") as file:
    f_config_ok_raw = file.read()
## Configuration object, nominal
f_config_ok_obj = {
    "main_database": {
        "host": "192.168.0.1",
        "port": 5432,
        "name": "ocsge",
        "user": "data_producer",
        "password": "bip-boop-123456",
        "schema": "photovoltaic",
        "table": "declaration"
    },
    "cadastre_database": {
        "host": "localhost",
        "port": 5433,
        "name": "cadastre",
        "user": "land_surveyor",
        "password": "1arpent",
        "schema": "cadastre_data",
        "table": "parcels"
    },
    "procedure_number": 98746
}

#Tests
@mock.patch(jsonschema.validate)
@patch("builtins.open", new_callable=mock_open, read_data=f_config_ok)
def test_load_configuration_ok(m_file, m_validator):
    result = TM.load_configuration(f_config_path)
    m_file.assert_called_with(config_path, "r")
    m_validator.assert_called_with(config_path, schema_path)
    assert result == f_config_ok_obj

