"""Describes unit tests for the ocsge_pv.geometrize_declarations module.

There is one test class for each tested functionnality.
See internal docstrings for more information.
Each variable prefixed by "m_" is a mock, or part of it.
Each variable prefixed by "f_" is a fixture.
"""

import json
from unittest import TestCase, mock, skip
from unittest.mock import Mock, MagicMock, call, mock_open, patch

from jsonschema import validate, ValidationError
import pytest

from ocsge_pv.geometrize_declarations import (
    load_configuration,
    main
)



#Tests
class TestConfigurationValidationSchema(TestCase):
    """Tests the configuration validation schema itself."""
    def setUp(self):
        self.schema_path = "src/ocsge_pv/resources/geometrize_config.schema.json"
        self.f_config_ok_path = "tests/fixtures/geometrize_config.ok.json"
        self.f_config_nok_path = "tests/fixtures/geometrize_config.nok.json"
        with open(self.schema_path, "r", encoding="utf-8") as fp:
            self.schema = json.load(fp)

    def test_with_valid_config(self):
        with open(self.f_config_ok_path, "r", encoding="utf-8") as fp:
            f_config_obj = json.load(fp)
        result = validate(f_config_obj, self.schema)
        self.assertIsNone(result)

    def test_with_invalid_config(self):
        with open(self.f_config_nok_path, "r", encoding="utf-8") as fp:
            f_config_obj = json.load(fp)
        with self.assertRaises(ValidationError):
            validate(f_config_obj, self.schema)


class TestConfigurationLoader(TestCase):
    """Tests the configuration loader."""
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

    @patch("jsonschema.validate")
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
        m_validator.assert_called_with(self.f_config_ok_obj, self.f_config_schema_obj)
        assert result == self.f_config_ok_obj

    @patch("jsonschema.validate", side_effect=ValidationError("Invalid configuration."))
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
        m_validator.assert_called_with(self.f_config_nok_obj, self.f_config_schema_obj)

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

class TestMain(TestCase):
    """Tests the main routine, entrypoint for the executable."""
    def setUp(self):
        self.m_execute = MagicMock()
        self.m_cursor = MagicMock(name="psycopg.Cursor")
        self.m_cursor.__enter__.return_value.execute = self.m_execute

    @patch("psycopg.connect")
    @patch("ocsge_pv.geometrize_declarations.load_configuration")
    def test_ok(self, m_loader, m_psycopg_connect):
        m_psycopg_connect.return_value.__enter__.return_value.cursor = self.m_cursor
        f_config_path = "tests/fixtures/geometrize_config.ok.json"
        with open(f_config_path, "r", encoding="utf-8") as fp:
            f_configuration = json.load(fp)
        m_loader.return_value = f_configuration
        main(f_config_path)
        m_loader.assert_called_once_with(f_config_path)
        main_db_connection_string=("host=" + f_configuration['main_database']['host']
            + " port=" + str(f_configuration['main_database']['port'])
            + " dbname=" + f_configuration['main_database']['name']
            + " user=" + f_configuration['main_database']['user']
            + " password=" + f_configuration['main_database']['password'])
        m_psycopg_connect.assert_has_calls([
            call(main_db_connection_string)
        ])
        self.m_cursor.assert_called()





