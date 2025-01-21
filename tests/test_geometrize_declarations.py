"""Describes unit tests for the ocsge_pv.geometrize_declarations module.

There is one test class for each tested functionnality.
See internal docstrings for more information.
Each variable prefixed by "m_" is a mock, or part of it.
Each variable prefixed by "f_" is a fixture.
"""

import json
from unittest import TestCase, mock
from unittest.mock import MagicMock, call, mock_open, patch

from jsonschema import validate, ValidationError
import pytest
import psycopg

from ocsge_pv.geometrize_declarations import (
    load_configuration
)

# TODO Features to test :
# * ~~read configuration~~
# * connect to database
# * read photovoltaic input table
# * check if geometry is initialised
# * read cadastral input table
# * convert between spatial reference systems with axis permutation
# * convert between spatial reference systems without axis permutation
# * compute geometry
# * write in photovoltaic output table (same one as input)


#Tests
class TestConfigurationLoader(TestCase):
    def setUp(self):
        # Fixtures
        ## Configuration file path
        self.f_config_ok_path = "tests/fixtures/geometrize_config.ok.json"
        self.f_config_nok_path = "tests/fixtures/geometrize_config.nok.json"
        ## Configuration file, nominal
        self.f_config_ok_raw = ""
        with open(self.f_config_ok_path, "r", encoding="utf-8") as file:
            self.f_config_ok_raw = file.read()
        ## Configuration object, nominal
        self.f_config_ok_obj = json.loads(self.f_config_ok_raw)
        ## Configuration file, invalid
        self.f_config_nok_raw = ""
        with open(self.f_config_nok_path, "r", encoding="utf-8") as file:
            self.f_config_nok_raw = file.read()
        ## Configuration object, invalid
        self.f_config_nok_obj = json.loads(self.f_config_nok_raw)

        ## Configuration file path
        self.f_config_schema_path = "src/ocsge_pv/resources/geometrize_config.schema.json"
        ## Configuration file, nominal
        self.f_config_schema_raw = ""
        with open(self.f_config_schema_path, "r", encoding="utf-8") as file:
            self.f_config_schema_raw = file.read()
        ## Configuration object, nominal
        self.f_config_schema_obj = json.loads(self.f_config_schema_raw)

    @patch("jsonschema.validate", side_effect=validate)
    @patch("builtins.open")
    def test_load_configuration_ok(self, m_open, m_validator):
        m_open.side_effect = [
            mock_open(read_data=self.f_config_ok_raw).return_value,
            mock_open(read_data=self.f_config_schema_raw).return_value
        ]
        result = load_configuration(self.f_config_ok_path)
        m_open.assert_called()
        m_open.assert_has_calls([
            call(self.f_config_ok_path, "r", encoding="utf-8"),
            call(self.f_config_schema_path, "r", encoding="utf-8")
        ])
        m_validator.assert_called_with(self.f_config_ok_obj, schema=self.f_config_schema_obj)
        assert result == self.f_config_ok_obj

    @patch("jsonschema.validate", side_effect=validate)
    @patch("builtins.open")
    def test_load_configuration_ok(self, m_open, m_validator):
        m_open.side_effect = [
            mock_open(read_data=self.f_config_nok_raw).return_value,
            mock_open(read_data=self.f_config_schema_raw).return_value
        ]
        with self.assertRaises(ValidationError):
            result = load_configuration(self.f_config_nok_path)
        m_open.assert_called()
        m_open.assert_has_calls([
            call(self.f_config_nok_path, "r", encoding="utf-8"),
            call(self.f_config_schema_path, "r", encoding="utf-8")
        ])
        m_validator.assert_called_with(self.f_config_nok_obj, schema=self.f_config_schema_obj)

