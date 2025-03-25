"""Describes unit tests for the ocsge_pv.import_declarations module.

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

from ocsge_pv.import_declarations import (
    format_feature,
    format_source_result,
    load_configuration,
    query_source_api,
    write_output,
    main
)

#Tests
class TestConfigurationValidationSchema(TestCase):
    """Tests the configuration validation schema itself."""
    def setUp(self):
        self.schema_path = "src/ocsge_pv/resources/import_declarations_config.schema.json"
        self.f_config_ok_path = "tests/fixtures/import_declarations_config.ok.json"
        self.f_config_nok_path = "tests/fixtures/import_declarations_config.nok.json"
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
        self.env_copy["OCSGE_PV_RESOURCE_DIR"] = os.environ["HOME"].rstrip("/") + "/ocsge-pv-resources"
        # Fixtures
        ## Configuration file path
        self.f_config_ok_path = Path("/app/tests/fixtures/import_declarations_config.ok.json")
        self.f_config_nok_path = Path("/app/tests/fixtures/import_declarations_config.nok.json")
        ## Configuration file, nominal
        self.f_config_ok_raw = ""
        with open(self.f_config_ok_path, "r", encoding="utf-8") as file:
            self.f_config_ok_raw = file.read()
        ## Configuration object, nominal before validation
        self.f_config_ok_obj = json.loads(self.f_config_ok_raw)
        ## Configuration object, nominal after complete load
        f_config_loaded_path = Path("/app/tests/fixtures/import_declarations_config.loaded.json")
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
        self.f_config_schema_path = Path(self.env_copy["OCSGE_PV_RESOURCE_DIR"],
            "import_declarations_config.schema.json")
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
        expected_result = deepcopy(self.f_config_loaded_obj)
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
        self.assertDictEqual(result, expected_result)

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
