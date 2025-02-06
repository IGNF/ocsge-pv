"""Describes unit tests for the ocsge_pv.geometrize_declarations module.

There is one test class for each tested functionnality.
See internal docstrings for more information.
Each variable prefixed by "m_" is a mock, or part of it.
Each variable prefixed by "f_" is a fixture.
"""
from copy import deepcopy
import json
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
        ## Configuration object, nominal before validation
        self.f_config_ok_obj = json.loads(self.f_config_ok_raw)
        ## Configuration object, nominal after complete load
        f_config_loaded_path = "tests/fixtures/geometrize_config.loaded.json"
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
        expected_result = deepcopy(self.f_config_loaded_obj)
        expected_result["main_database"]["_table_name_sql"] = sql.SQL(".").join([
            expected_result["main_database"]["schema"],
            expected_result["main_database"]["table"]])
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

class TestWriter(TestCase):
    """Tests the output writing routine."""
    def setUp(self):
        f_config_loaded_path = "tests/fixtures/geometrize_config.loaded.json"
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
        f_config_loaded_path = "tests/fixtures/geometrize_config.loaded.json"
        with open(f_config_loaded_path, "r", encoding="utf-8") as file:
            f_config_loaded_raw = file.read()
        f_configuration = json.loads(f_config_loaded_raw)
        m_execute = MagicMock()
        m_cursor = MagicMock()
        m_cursor.return_value.__enter__.return_value.execute = m_execute
        update_list = [
            (126, "POLYGON(110 185, 115 185, 115 190, 110 190, 110 185)"),
            (453, "POLYGON(120 185, 125 185, 125 190, 120 190, 120 185)"),
            (1984, "POLYGON(130 195, 135 195, 135 190, 130 190, 130 195)"),
        ]
        m_psycopg_connect.return_value.__enter__.return_value.cursor = m_cursor
        # Call to the tested function
        write_output(f_configuration, update_list, "fid")
        # Assertions
        m_psycopg_connect.assert_has_calls([
            call(f_configuration["main_database"]["_pg_string"])
        ])
        m_cursor.assert_called_once_with()
        m_execute.assert_called()
        self.assertIn(call(sql.SQL("BEGIN")), m_execute.call_args_list)
        self.assertIn(call(sql.SQL("COMMIT")), m_execute.call_args_list)
        sql_update_count = 0
        pattern = "UPDATE .*{2}{0}{2}\\.{2}{1}{2}.* SET \"geom\" = .* WHERE \"fid\" = ".format(
            f_configuration["main_database"]["schema"],
            f_configuration["main_database"]["table"],
            "['\\\\]+"
        )
        for call_entry in m_execute.call_args_list:
            query = call_entry[0][0].as_string()
            if re.match(pattern, query):
                sql_update_count += 1
        self.assertEqual(sql_update_count, 3)


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
        f_config_loaded_path = "tests/fixtures/geometrize_config.loaded.json"
        with open(f_config_loaded_path, "r", encoding="utf-8") as file:
            f_config_loaded_raw = file.read()
        self.f_configuration = json.loads(f_config_loaded_raw)

    @patch("osgeo.osr.CreateCoordinateTransformation")
    @patch("osgeo.ogr.Open")
    @patch("ocsge_pv.geometrize_declarations.write_output")
    @patch("ocsge_pv.geometrize_declarations.load_configuration")
    def test_ok(self, m_loader, m_writer, m_ogr_open, m_osr_createct):
        # Preparation
        ## OGR/OSR entities 
        m_main_ogr_ds = MagicMock()
        m_main_ogr_lay = MagicMock()
        m_main_ogr_sr = MagicMock()
        m_main_ogr_lay.GetSpatialRef.return_value = m_main_ogr_sr
        m_main_ogr_lay.GetFIDColumn.return_value = "fid"
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
        ## Configuration
        f_config_path = "tests/fixtures/geometrize_config.ok.json"
        f_configuration = deepcopy(self.f_configuration)
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
        m_osr_createct.assert_called_once_with(
            m_parcel_ogr_sr,
            m_main_ogr_sr)
        m_writer.assert_called_once_with(
            f_configuration,
            [],
            m_main_ogr_lay.GetFIDColumn.return_value)





