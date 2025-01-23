"""Describes unit tests for the ocsge_pv.geometrize_declarations module.

There is one test class for each tested functionnality.
See internal docstrings for more information.
Each variable prefixed by "m_" is a mock, or part of it.
Each variable prefixed by "f_" is a fixture.
"""

import json
from unittest import TestCase, mock
from unittest.mock import Mock, call, mock_open, patch

from jsonschema import validate, ValidationError
import pytest

from ocsge_pv.geometrize_declarations import (
    execute_request,
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
class TestConfigurationValidationSchema(TestCase):
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

class TestExecuteRequest(TestCase):
    def setUp(self):
        with open(self.f_config_ok_path, "r", encoding="utf-8") as fp:
            self.configuration = json.load(fp)
            self.m_execute = Mock()
            self.m_cursor = Mock(name="psycopg.Cursor", spec=["execute"])
            self.m_cursor.execute = m_execute
            self.m_connection = Mock(name="psycopg.Connection", spec=["cursor"])
            self.m_connection.cursor = Mock(return_value=m_cursor)

    @patch("psycopg.connect")
    def execute_request(self, m_psycopg_connect):
        m_psycopg_connect.return_value = self.m_connection
        expected = [
            (11569, "940670000D0013;940670000D0014;940670000D0015;940670000D0016;940670000D0017;940670000D0018"),
            (12684, "940670000D0050")    
        ]
        self.m_execute.return_value = expected
        request = ("SELECT id_dossier, num_parcelles"
            +"FROM parcs_photovoltaiques.declaration"
            +"WHERE geom IS NULL;")
        result = execute_request(self.configuration, request)
        self.assertIsNotNone(result)
        self.assertEqual(expected, result)
        m_psycopg_connect.assert_called_once()
        self.m_cursor.assert_called_once()
        self.m_execute.assert_called_once()



