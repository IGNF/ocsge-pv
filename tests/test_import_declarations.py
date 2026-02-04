"""Describes unit tests for the ocsge_pv.import_declarations module.

There is one test class for each tested functionnality.
See internal docstrings for more information.
Each variable prefixed by "m_" is a mock, or part of it.
Each variable prefixed by "f_" is a fixture.
"""

import json
import os
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, call, mock_open, patch

from jsonschema import ValidationError, validate

from ocsge_pv.import_declarations import load_configuration, query_source_api

try:
    OCSGE_PV_FIXTURE_DIR = Path(os.environ.get("OCSGE_PV_FIXTURE_DIR").strip()).resolve()
except:
    OCSGE_PV_FIXTURE_DIR = Path(".", "tests/fixtures").resolve()
try:
    OCSGE_PV_RESOURCE_DIR = Path(os.environ.get("OCSGE_PV_RESOURCE_DIR").strip()).resolve()
except:
    OCSGE_PV_RESOURCE_DIR = Path(".", "src/ocsge_pv/resources").resolve()

TESTED_MODULE = "ocsge_pv.import_declarations"


# Tests
class TestConfigurationValidationSchema(TestCase):
    """Tests the configuration validation schema itself."""

    def setUp(self):
        self.schema_path = f"{OCSGE_PV_RESOURCE_DIR}/import_declarations_config.schema.json"
        self.f_config_ok_path = f"{OCSGE_PV_FIXTURE_DIR}/import_declarations_config.ok.json"
        self.f_config_nok_path = f"{OCSGE_PV_FIXTURE_DIR}/import_declarations_config.nok.json"
        with open(self.schema_path, encoding="utf-8") as fp:
            self.schema = json.load(fp)

    def test_with_valid_config(self):
        # Preparation
        with open(self.f_config_ok_path, encoding="utf-8") as fp:
            f_config_obj = json.load(fp)
        # Call to the tested function
        result = validate(f_config_obj, self.schema)
        # Assertions
        self.assertIsNone(result)

    def test_with_invalid_config(self):
        # Preparation
        with open(self.f_config_nok_path, encoding="utf-8") as fp:
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
        self.f_config_ok_path = Path(OCSGE_PV_FIXTURE_DIR, "import_declarations_config.ok.json")
        self.f_config_nok_path = Path(OCSGE_PV_FIXTURE_DIR, "import_declarations_config.nok.json")
        ## Configuration file, nominal
        self.f_config_ok_raw = ""
        with open(self.f_config_ok_path, encoding="utf-8") as file:
            self.f_config_ok_raw = file.read()
        ## Configuration object, nominal before validation
        self.f_config_ok_obj = json.loads(self.f_config_ok_raw)
        ## Configuration object, nominal after complete load
        f_config_loaded_path = Path(OCSGE_PV_FIXTURE_DIR, "import_declarations_config.loaded.json")
        with open(f_config_loaded_path, encoding="utf-8") as file:
            f_config_loaded_raw = file.read()
        self.f_config_loaded_obj = json.loads(f_config_loaded_raw)
        ## Configuration file, invalid
        self.f_config_nok_raw = ""
        with open(self.f_config_nok_path, encoding="utf-8") as file:
            self.f_config_nok_raw = file.read()
        ## Configuration object, invalid
        self.f_config_nok_obj = json.loads(self.f_config_nok_raw)

        ## Validation schema file path
        self.f_config_schema_path = Path(
            OCSGE_PV_RESOURCE_DIR, "import_declarations_config.schema.json"
        )
        ## Validation schema file, nominal
        self.f_config_schema_raw = ""
        with open(self.f_config_schema_path, encoding="utf-8") as file:
            self.f_config_schema_raw = file.read()
        ## Validation schema object, nominal
        self.f_config_schema_obj = json.loads(self.f_config_schema_raw)

    @patch("jsonschema.validate")
    @patch("builtins.open")
    def test_load_configuration_ok(self, m_open, m_validator):
        # Preparation
        m_open.side_effect = [
            mock_open(read_data=self.f_config_ok_raw).return_value,
            mock_open(read_data=self.f_config_schema_raw).return_value,
        ]
        expected_result = deepcopy(self.f_config_loaded_obj)
        # Call to the tested function
        with patch.dict(os.environ, self.env_copy):
            result = load_configuration(self.f_config_ok_path)
        # Assertions
        m_open.assert_called()
        m_open.assert_has_calls(
            [
                call(self.f_config_ok_path, encoding="utf-8"),
                call(self.f_config_schema_path, encoding="utf-8"),
            ]
        )
        m_validator.assert_called_with(self.f_config_ok_obj, self.f_config_schema_obj)
        self.assertDictEqual(result, expected_result)

    @patch("jsonschema.validate", side_effect=ValidationError("Invalid configuration."))
    @patch("builtins.open")
    def test_load_configuration_nok(self, m_open, m_validator):
        # Preparation
        m_open.side_effect = [
            mock_open(read_data=self.f_config_nok_raw).return_value,
            mock_open(read_data=self.f_config_schema_raw).return_value,
        ]
        # Call to the tested function (while asserting Exception)
        with patch.dict(os.environ, self.env_copy):
            with self.assertRaises(ValidationError):
                result = load_configuration(self.f_config_nok_path)
        # Assertions
        m_open.assert_called()
        m_open.assert_has_calls(
            [
                call(self.f_config_nok_path, encoding="utf-8"),
                call(self.f_config_schema_path, encoding="utf-8"),
            ]
        )
        m_validator.assert_called_with(self.f_config_nok_obj, self.f_config_schema_obj)


class TestSourceAPIQuery(TestCase):
    """Test module function query_source_api."""

    def setUp(self):
        self.env_copy = deepcopy(os.environ)
        self.env_copy["OCSGE_PV_RESOURCE_DIR"] = str(OCSGE_PV_RESOURCE_DIR)
        self.env_copy["OCSGE_PV_RESOURCE_DIR"] = str(OCSGE_PV_RESOURCE_DIR)
        # Fixtures
        ## Configuration file path
        self.f_config_ok_path = Path(OCSGE_PV_FIXTURE_DIR, "import_declarations_config.ok.json")
        self.f_config_nok_path = Path(OCSGE_PV_FIXTURE_DIR, "import_declarations_config.nok.json")
        ## Configuration file, nominal
        self.f_config_ok_raw = ""
        with open(self.f_config_ok_path, encoding="utf-8") as file:
            self.f_config_ok_raw = file.read()
        ## Configuration object, nominal before validation
        self.f_config_ok_obj = json.loads(self.f_config_ok_raw)
        ## Configuration object, nominal after complete load
        f_config_loaded_path = Path(OCSGE_PV_FIXTURE_DIR, "import_declarations_config.loaded.json")
        with open(f_config_loaded_path, encoding="utf-8") as file:
            f_config_loaded_raw = file.read()
        self.f_config_loaded_obj = json.loads(f_config_loaded_raw)

    @patch(f"{TESTED_MODULE}.gql")
    @patch(f"{TESTED_MODULE}.AIOHTTPTransport")
    def test_dossiers_monopage_ok(self, m_transport, m_gql):
        """Response with only active dossiers, only one page."""
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_base.ok.json"), encoding="utf-8"
        ) as file:
            api_response_base_str = file.read()
        api_response_base = json.loads(api_response_base_str)
        return_list = []
        expected = deepcopy(api_response_base)
        # Common part call / First call
        return_list.append(api_response_base)
        # Dossiers calls
        ## First page call / Second call
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_dossiers_mono.ok.json"), encoding="utf-8"
        ) as file:
            dossiers_str = file.read()
        expected["demarche"]["dossiers"] = json.loads(dossiers_str)
        second_response = deepcopy(api_response_base)
        second_response["demarche"]["dossiers"] = expected["demarche"]["dossiers"][0]
        return_list.append(second_response)
        # Deleted dossiers calls
        ## First page call / Third call
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_anytype_empty.json"), encoding="utf-8"
        ) as file:
            deletedDossiers_str = file.read()
        expected["demarche"]["deletedDossiers"] = json.loads(deletedDossiers_str)
        third_response = deepcopy(api_response_base)
        third_response["demarche"]["deletedDossiers"] = expected["demarche"]["deletedDossiers"][0]
        return_list.append(third_response)
        m_execute = Mock(side_effect=return_list)
        m_client = Mock()
        m_client.return_value.execute = m_execute

        with patch(f"{TESTED_MODULE}.Client", m_client):
            result = query_source_api(self.f_config_loaded_obj["input"])

        self.assertEqual(m_execute.call_count, 3)
        self.assertEqual(result, expected)

    @patch(f"{TESTED_MODULE}.gql")
    @patch(f"{TESTED_MODULE}.AIOHTTPTransport")
    def test_dossiers_multipage_ok(self, m_transport, m_gql):
        """Response with only active dossiers, multiple pages."""
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_base.ok.json"), encoding="utf-8"
        ) as file:
            api_response_base_str = file.read()
        api_response_base = json.loads(api_response_base_str)
        return_list = []
        expected = deepcopy(api_response_base)
        # Common part call / First call
        return_list.append(api_response_base)
        # Dossiers calls
        ## First page call / Second call
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_dossiers_multi.ok.json"), encoding="utf-8"
        ) as file:
            dossiers_str = file.read()
        expected["demarche"]["dossiers"] = json.loads(dossiers_str)
        second_response = deepcopy(api_response_base)
        second_response["demarche"]["dossiers"] = expected["demarche"]["dossiers"][0]
        return_list.append(second_response)
        ## Second page call / Third call
        third_response = deepcopy(api_response_base)
        third_response["demarche"]["dossiers"] = expected["demarche"]["dossiers"][1]
        return_list.append(third_response)
        # Deleted dossiers calls
        ## First page call / Fourth call
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_anytype_empty.json"), encoding="utf-8"
        ) as file:
            deletedDossiers_str = file.read()
        expected["demarche"]["deletedDossiers"] = json.loads(deletedDossiers_str)
        fourth_response = deepcopy(api_response_base)
        fourth_response["demarche"]["deletedDossiers"] = expected["demarche"]["deletedDossiers"][0]
        return_list.append(fourth_response)
        m_execute = Mock(side_effect=return_list)
        m_client = Mock()
        m_client.return_value.execute = m_execute

        with patch(f"{TESTED_MODULE}.Client", m_client):
            result = query_source_api(self.f_config_loaded_obj["input"])

        self.assertEqual(m_execute.call_count, 4)
        self.assertEqual(result, expected)

    @patch(f"{TESTED_MODULE}.gql")
    @patch(f"{TESTED_MODULE}.AIOHTTPTransport")
    def test_deletedDossiers_monopage_ok(self, m_transport, m_gql):
        """Response with only deleted dossiers, only one page."""
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_base.ok.json"), encoding="utf-8"
        ) as file:
            api_response_base_str = file.read()
        api_response_base = json.loads(api_response_base_str)
        return_list = []
        expected = deepcopy(api_response_base)
        # Common part call / First call
        return_list.append(api_response_base)
        # Dossiers calls
        ## First page call / Second call
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_anytype_empty.json"), encoding="utf-8"
        ) as file:
            dossiers_str = file.read()
        expected["demarche"]["dossiers"] = json.loads(dossiers_str)
        second_response = deepcopy(api_response_base)
        second_response["demarche"]["dossiers"] = expected["demarche"]["dossiers"][0]
        return_list.append(second_response)
        # Deleted dossiers calls
        ## First page call / Third call
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_deletedDossiers_mono.ok.json"),
            encoding="utf-8",
        ) as file:
            deletedDossiers_str = file.read()
        expected["demarche"]["deletedDossiers"] = json.loads(deletedDossiers_str)
        third_response = deepcopy(api_response_base)
        third_response["demarche"]["deletedDossiers"] = expected["demarche"]["deletedDossiers"][0]
        return_list.append(third_response)
        m_execute = Mock(side_effect=return_list)
        m_client = Mock()
        m_client.return_value.execute = m_execute

        with patch(f"{TESTED_MODULE}.Client", m_client):
            result = query_source_api(self.f_config_loaded_obj["input"])

        self.assertEqual(m_execute.call_count, 3)
        self.assertEqual(result, expected)

    @patch(f"{TESTED_MODULE}.gql")
    @patch(f"{TESTED_MODULE}.AIOHTTPTransport")
    def test_deletedDossiers_multipage_ok(self, m_transport, m_gql):
        """Response with only deleted dossiers, multiple pages."""
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_base.ok.json"), encoding="utf-8"
        ) as file:
            api_response_base_str = file.read()
        api_response_base = json.loads(api_response_base_str)
        return_list = []
        expected = deepcopy(api_response_base)
        # Common part call / First call
        return_list.append(api_response_base)
        # Dossiers calls
        ## First page call / Second call
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_anytype_empty.json"), encoding="utf-8"
        ) as file:
            dossiers_str = file.read()
        expected["demarche"]["dossiers"] = json.loads(dossiers_str)
        second_response = deepcopy(api_response_base)
        second_response["demarche"]["dossiers"] = expected["demarche"]["dossiers"][0]
        return_list.append(second_response)
        # Deleted dossiers calls
        ## First page call / Third call
        with open(
            Path(OCSGE_PV_FIXTURE_DIR, "query_source_api_deletedDossiers_multi.ok.json"),
            encoding="utf-8",
        ) as file:
            deletedDossiers_str = file.read()
        expected["demarche"]["deletedDossiers"] = json.loads(deletedDossiers_str)
        third_response = deepcopy(api_response_base)
        third_response["demarche"]["deletedDossiers"] = expected["demarche"]["deletedDossiers"][0]
        return_list.append(third_response)
        ## Second page call / Fourth call
        fourth_response = deepcopy(api_response_base)
        fourth_response["demarche"]["deletedDossiers"] = expected["demarche"]["deletedDossiers"][1]
        return_list.append(fourth_response)
        m_execute = Mock(side_effect=return_list)
        m_client = Mock()
        m_client.return_value.execute = m_execute

        with patch(f"{TESTED_MODULE}.Client", m_client):
            result = query_source_api(self.f_config_loaded_obj["input"])

        self.assertEqual(m_execute.call_count, 4)
        self.assertEqual(result, expected)
