"""Describes unit tests for the ocsge_pv.geometrize_declarations module.

There is one test class for each tested functionnality.
See internal docstrings for more information.
Each variable prefixed by "m_" is a mock, or part of it.
Each variable prefixed by "f_" is a fixture.
"""
from copy import deepcopy
import json
from unittest import TestCase, mock, skip
from unittest.mock import MagicMock, call, mock_open, patch

from jsonschema import validate, ValidationError
from psycopg import sql
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
        # Preparation
        m_open.side_effect = [
            mock_open(read_data=self.f_config_ok_raw).return_value,
            mock_open(read_data=self.f_config_schema_raw).return_value
        ]
        expected_result = deepcopy(self.f_config_ok_obj)
        expected_result["main_database"]["_pg_string"] = (
            "host=" + expected_result["main_database"]["host"]
            + " port=" + str(expected_result["main_database"]["port"])
            + " dbname=" + expected_result["main_database"]["name"]
            + " user=" + expected_result["main_database"]["user"]
            + " password=" + expected_result["main_database"]["password"])
        expected_result["main_database"]["_table_name_raw"] = (
            expected_result["main_database"]["schema"] + "."
            + expected_result["main_database"]["table"])
        expected_result["main_database"]["_table_name_sql"] = sql.SQL(".").join([
            expected_result["main_database"]["schema"],
            expected_result["main_database"]["table"]])
        expected_result["cadastre_database"]["_pg_string"] = (
            "host=" + expected_result["cadastre_database"]["host"]
            + " port=" + str(expected_result["cadastre_database"]["port"])
            + " dbname=" + expected_result["cadastre_database"]["name"]
            + " user=" + expected_result["cadastre_database"]["user"]
            + " password=" + expected_result["cadastre_database"]["password"])
        expected_result["cadastre_database"]["_table_name_raw"] = (
            expected_result["cadastre_database"]["schema"] + "."
            + expected_result["cadastre_database"]["table"])
        # Call to the tested function
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
        with self.assertRaises(ValidationError):
            result = load_configuration(self.f_config_nok_path)
        # Assertions
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
        self.m_cursor = MagicMock()
        self.m_cursor.__enter__.return_value.execute = self.m_execute

    @patch("osgeo.osr.CreateCoordinateTransformation")
    @patch("osgeo.ogr.Open")
    @patch("psycopg.connect")
    @patch("ocsge_pv.geometrize_declarations.load_configuration")
    def test_ok(self, m_loader, m_psycopg_connect, m_ogr_open, m_osr_createct):
        # Preparation
        ## OGR/OSR entities 
        m_main_ogr_ds = MagicMock()
        m_main_ogr_lay = MagicMock()
        m_main_ogr_sr = MagicMock()
        m_main_ogr_lay.GetSpatialRef.return_value = m_main_ogr_sr
        m_main_ogr_ds.GetLayerByName.return_value = m_main_ogr_lay
        m_main_ogr_sr.GetName.return_value = "RGF93 v1 / Lambert-93"
        m_main_ogr_sr.EPSGTreatsAsLatLong.return_value = None
        m_parcel_ogr_ds = MagicMock()
        m_parcel_ogr_lay = MagicMock()
        m_parcel_ogr_sr = MagicMock()
        m_parcel_ogr_lay.GetSpatialRef.return_value = m_parcel_ogr_sr
        m_parcel_ogr_ds.GetLayerByName.return_value = m_parcel_ogr_lay
        m_parcel_ogr_sr.GetName.return_value = "WGS 84"
        m_parcel_ogr_sr.EPSGTreatsAsLatLong.return_value = None
        m_ogr_open.side_effect=[m_main_ogr_ds, m_parcel_ogr_ds]
        m_psycopg_connect.return_value.__enter__.return_value.cursor = self.m_cursor
        ## Configuration object
        f_config_path = "tests/fixtures/geometrize_config.ok.json"
        with open(f_config_path, "r", encoding="utf-8") as fp:
            f_configuration = json.load(fp)
        f_configuration["main_database"]["_pg_string"] = (
            "host=" + f_configuration["main_database"]["host"]
            + " port=" + str(f_configuration["main_database"]["port"])
            + " dbname=" + f_configuration["main_database"]["name"]
            + " user=" + f_configuration["main_database"]["user"]
            + " password=" + f_configuration["main_database"]["password"])
        f_configuration["cadastre_database"]["_pg_string"] = (
            "host=" + f_configuration["cadastre_database"]["host"]
            + " port=" + str(f_configuration["cadastre_database"]["port"])
            + " dbname=" + f_configuration["cadastre_database"]["name"]
            + " user=" + f_configuration["cadastre_database"]["user"]
            + " password=" + f_configuration["cadastre_database"]["password"])
        f_configuration["main_database"]["_table_name_raw"] = (
            f_configuration["main_database"]["schema"] + "."
            + f_configuration["main_database"]["table"])
        f_configuration["main_database"]["_table_name_sql"] = ("SQL("
            + f_configuration["main_database"]["_table_name_raw"] + ")")
        f_configuration["cadastre_database"]["_table_name_raw"] = (
            f_configuration["cadastre_database"]["schema"] + "."
            + f_configuration["cadastre_database"]["table"])
        m_loader.return_value = f_configuration
        # Call to the tested function
        main(f_config_path)
        # Assertions
        ## Configuration
        m_loader.assert_called_once_with(f_config_path)
        ## OGR/OSR
        m_ogr_open.assert_called()
        self.assertEqual(m_ogr_open.call_count, 2)
        m_main_ogr_ds.GetLayerByName.assert_called_once_with(
            f_configuration["main_database"]["_table_name_raw"])
        m_main_ogr_lay.GetSpatialRef.assert_called_once()
        m_main_ogr_sr.GetName.assert_called_once()
        m_main_ogr_sr.EPSGTreatsAsLatLong.assert_called_once()
        m_parcel_ogr_ds.GetLayerByName.assert_called_once_with(
            f_configuration["cadastre_database"]["_table_name_raw"])
        m_parcel_ogr_lay.GetSpatialRef.assert_called_once()
        m_parcel_ogr_sr.GetName.assert_called_once()
        m_parcel_ogr_sr.EPSGTreatsAsLatLong.assert_called_once()
        m_osr_createct.assert_called_once_with(m_parcel_ogr_sr, m_main_ogr_sr)
        ## Psycopg
        m_psycopg_connect.assert_has_calls([
            call(f_configuration["main_database"]["_pg_string"])
        ])
        self.m_cursor.assert_called()
        self.m_execute.assert_called()
        self.assertIn(call("SELECT "), self.m_execute.call_args_list)





