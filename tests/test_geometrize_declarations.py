"""Describes unit tests for the ocsge_pv.geometrize_declarations module.

There is one test class for each tested functionnality.
See internal docstrings for more information.
Each variable prefixed by "m_" is a mock, or part of it.
Each variable prefixed by "f_" is a fixture.
"""

from copy import deepcopy
import json
from pathlib import Path
import os
import re
from unittest import TestCase, mock, skip
from unittest.mock import MagicMock, call, mock_open, patch

from jsonschema import validate, ValidationError
from psycopg import sql
import pytest

from ocsge_pv.geometrize_declarations import (
    load_configuration,
    main,
    write_output
)

try:
    OCSGE_PV_FIXTURE_DIR = Path(os.environ.get("OCSGE_PV_FIXTURE_DIR").strip()).resolve()
except:
    OCSGE_PV_FIXTURE_DIR = Path(".", "tests/fixtures").resolve()
try:
    OCSGE_PV_RESOURCE_DIR = Path(os.environ.get("OCSGE_PV_RESOURCE_DIR").strip()).resolve()
except:
    OCSGE_PV_RESOURCE_DIR = Path(".", "src/ocsge_pv/resources").resolve()

#Tests
class TestConfigurationValidationSchema(TestCase):
    """Tests the configuration validation schema itself."""
    def setUp(self):
        self.schema_path = f"{OCSGE_PV_RESOURCE_DIR}/geometrize_config.schema.json"
        self.f_config_ok_path = f"{OCSGE_PV_FIXTURE_DIR}/geometrize_config.ok.json"
        self.f_config_nok_path = f"{OCSGE_PV_FIXTURE_DIR}/geometrize_config.nok.json"
        with open(self.schema_path, "r", encoding="utf-8") as fp:
            self.schema = json.load(fp)

    def test_with_valid_config(self):
        # Preparation
        with open(self.f_config_ok_path, "r", encoding="utf-8") as fp:
            f_config_obj = json.load(fp)
        # Call to the tested function
        result = validate(f_config_obj, self.schema)
        # Assertions
        self.assertIsNone(result)

    def test_with_invalid_config(self):
        # Preparation
        with open(self.f_config_nok_path, "r", encoding="utf-8") as fp:
            f_config_obj = json.load(fp)
        # Call to the tested function (while asserting Exception)
        with self.assertRaises(ValidationError):
            validate(f_config_obj, self.schema)


class TestConfigurationLoader(TestCase):
    """Tests the configuration loader."""
    def setUp(self):
        self.env_copy = deepcopy(os.environ)
        self.env_copy["OCSGE_PV_RESOURCE_DIR"] = str(OCSGE_PV_RESOURCE_DIR)
        # Fixtures
        ## Configuration file path
        self.f_config_ok_path = Path(OCSGE_PV_FIXTURE_DIR, "geometrize_config.ok.json")
        self.f_config_nok_path = Path(OCSGE_PV_FIXTURE_DIR, "geometrize_config.nok.json")
        ## Configuration file, nominal
        self.f_config_ok_raw = ""
        with open(self.f_config_ok_path, "r", encoding="utf-8") as file:
            self.f_config_ok_raw = file.read()
        ## Configuration object, nominal before validation
        self.f_config_ok_obj = json.loads(self.f_config_ok_raw)
        ## Configuration object, nominal after complete load
        f_config_loaded_path = Path(OCSGE_PV_FIXTURE_DIR, "geometrize_config.loaded.json")
        with open(f_config_loaded_path, "r", encoding="utf-8") as file:
            f_config_loaded_raw = file.read()
        self.f_config_loaded_obj = json.loads(f_config_loaded_raw)
        ## Configuration file, invalid
        self.f_config_nok_raw = ""
        with open(self.f_config_nok_path, "r", encoding="utf-8") as file:
            self.f_config_nok_raw = file.read()
        ## Configuration object, invalid
        self.f_config_nok_obj = json.loads(self.f_config_nok_raw)

        ## Configuration file path
        self.f_config_schema_path = Path(OCSGE_PV_RESOURCE_DIR,
            "geometrize_config.schema.json")
        ## Configuration file, nominal
        self.f_config_schema_raw = ""
        with open(self.f_config_schema_path, "r", encoding="utf-8") as file:
            self.f_config_schema_raw = file.read()
        ## Configuration object, nominal
        self.f_config_schema_obj = json.loads(self.f_config_schema_raw)

    @patch("jsonschema.validate")
    @patch("builtins.open")
    def test_load_configuration_ok(self, m_open, m_validator):
        # Preparation
        m_open.side_effect = [
            mock_open(read_data=self.f_config_ok_raw).return_value,
            mock_open(read_data=self.f_config_schema_raw).return_value
        ]
        # Call to the tested function
        with patch.dict(os.environ, self.env_copy):
            result = load_configuration(self.f_config_ok_path)
        # Assertions
        m_open.assert_called()
        m_open.assert_has_calls([
            call(self.f_config_ok_path, "r", encoding="utf-8"),
            call(self.f_config_schema_path, "r", encoding="utf-8")
        ])
        m_validator.assert_called_with(self.f_config_ok_obj, self.f_config_schema_obj)
        self.assertDictEqual(result, self.f_config_loaded_obj)

    @patch("jsonschema.validate", side_effect=ValidationError("Invalid configuration."))
    @patch("builtins.open")
    def test_load_configuration_nok(self, m_open, m_validator):
        # Preparation
        m_open.side_effect = [
            mock_open(read_data=self.f_config_nok_raw).return_value,
            mock_open(read_data=self.f_config_schema_raw).return_value
        ]
        # Call to the tested function (while asserting Exception)
        with patch.dict(os.environ, self.env_copy):
            with self.assertRaises(ValidationError):
                result = load_configuration(self.f_config_nok_path)
        # Assertions
        m_open.assert_called()
        m_open.assert_has_calls([
            call(self.f_config_nok_path, "r", encoding="utf-8"),
            call(self.f_config_schema_path, "r", encoding="utf-8")
        ])
        m_validator.assert_called_with(self.f_config_nok_obj, self.f_config_schema_obj)

class TestWriter(TestCase):
    """Tests the output writing routine."""
    def setUp(self):
        f_config_loaded_path = Path(OCSGE_PV_FIXTURE_DIR, "geometrize_config.loaded.json")
        with open(f_config_loaded_path, "r", encoding="utf-8") as file:
            f_config_loaded_raw = file.read()
        self.f_configuration = json.loads(f_config_loaded_raw)
        self.m_execute = MagicMock()
        self.m_cursor = MagicMock()
        self.m_cursor.return_value.__enter__.return_value.execute = self.m_execute
        self.update_list = {}

    @patch("psycopg.connect")
    def test_ok(self, m_psycopg_connect):
        # Preparation
        f_config_loaded_path = Path(OCSGE_PV_FIXTURE_DIR, "geometrize_config.loaded.json")
        with open(f_config_loaded_path, "r", encoding="utf-8") as file:
            f_config_loaded_raw = file.read()
        f_configuration = json.loads(f_config_loaded_raw)
        m_execute = MagicMock()
        m_cursor = MagicMock()
        m_cursor.return_value.execute = m_execute
        update_list = [
            (126, "POLYGON(110 185, 115 185, 115 190, 110 190, 110 185)"),
            (453, "POLYGON(120 185, 125 185, 125 190, 120 190, 120 185)"),
            (1984, "POLYGON(130 195, 135 195, 135 190, 130 190, 130 195)"),
        ]
        m_psycopg_connect.return_value.__enter__.return_value.cursor = m_cursor
        # Call to the tested function
        write_output(f_configuration["main_database"], update_list, "fid")
        # Assertions
        m_psycopg_connect.assert_any_call(f_configuration["main_database"]["_pg_string"],
            autocommit=True)
        m_cursor.assert_called_once_with()
        m_execute.assert_called()
        sql_update_count = 0
        pattern = (
            f'UPDATE "{f_configuration["main_database"]["schema"]}".'
            + f'"{f_configuration["main_database"]["table"]}"'
            + ' SET "geom" = ST_GeomFromText\\(%s\\) WHERE "fid" = %s')
        for call_entry in m_execute.call_args_list:
            if (type(call_entry[0][0]) == type(sql.Composed(""))
                    and re.match(pattern, call_entry[0][0].as_string())):
                sql_update_count += 1
        self.assertEqual(sql_update_count, 3)





