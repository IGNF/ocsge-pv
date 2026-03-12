"""Photovoltaic farm declarations importer

Import photovoltaic farms declaration files from the official
declaration service API, and insert them into a database.

The only mandatory argument is the path to a JSON configuration file.
The environment variable OCSGE_PV_RESOURCE_DIR describes the path to
<repo>/src/ocsge_pv/resources or a copy of this directory. If empty or
unset, /app/src/ocsge_pv/resources will be used instead.
See cli_arg_parser for optionnal arguments.
Documentation for the configuration file is provided:
    * annotated schema:
        src/ocsge_pv/resources/import_declarations_config.schema.json
    * example: tests/fixture/import_declarations_config.ok.json

This file contains the following functions :
    * cli_arg_parser - parse CLI arguments
    * format_feature - convert a feature's format from input to output
    * format_source_result - convert format from input data to output
    * load_configuration - return validated configuration from file
    * query_source_api - fetch input data from the source API
    * write_output - insert output data in the target table
    * main - main function of the script
"""

# -- IMPORTS --


import argparse
import json
import logging
import os
import re
import sys
import traceback
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

import jsonschema
import psycopg
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as AIOHTTPTransport_logger
from osgeo import ogr, osr
from psycopg import sql

# -- GLOBALS --


NAME = "import_declarations"
logging.basicConfig(
    level=logging.INFO,
    format=r"%(asctime)s %(name)s\(%(funcName)s\) %(levelname)s: %(message)s",
)
# logging.captureWarnings(True)
AIOHTTPTransport_logger.setLevel(logging.WARNING)
logger = logging.getLogger(NAME)
ogr.UseExceptions()
osr.UseExceptions()
SOURCE_SRID = 4326
SOURCE_SRS = osr.SpatialReference()
SOURCE_SRS.ImportFromEPSG(SOURCE_SRID)  # Axes order: (latitude, longitude)


# -- FUNCTIONS --


def cli_arg_parser() -> argparse.Namespace:
    """Parse CLI arguments

    Args:
        * sys.argv (implicit) - CLI arguments

    Returns:
        argparse.Namespace: processed arguments
    """
    parser = argparse.ArgumentParser(
        prog=NAME,
        description=(
            "Import photovoltaic farms declaration files from the official declaration"
            + " service API, and insert them into a database."
        ),
    )
    parser.add_argument("path", type=Path, help="the path of the configuration file for %(prog)s")
    parser.add_argument(
        "-v", "--verbose", dest="verbose", action="store_true", help="output more logs"
    )
    return parser.parse_args()


def format_feature(in_data: dict) -> dict:
    """Transform declaration dossier to postgis feature

    Args:
        in_data (Dict): dossier's data for a single declaration

    Returns:
        Dict: structure to insert in the output database
    """
    out_data = {
        "id_dossier": None,
        "porteur": None,
        "siret_port": None,
        "ref_urba": None,
        "type_proj": None,
        "surf_socle": None,
        "etat": None,
        "puiss_max": None,
        "date_depot": None,
        "date_deliv": None,
        "date_insta": None,
        "duree_exp": None,
        "adresse": None,
        "num_parcelles": None,
        "surf_occup": None,
        "surf_terr": None,
        "localisat": None,
        "sol_nature": None,
        "sol_detail": None,
        "usage_terr": None,
        "type_agri": None,
        "agri_ini": None,
        "agri_resid": None,
        "ancrage": None,
        "cloture": None,
        "revetement": None,
        "haut_pann": None,
        "espacement": None,
        "nat_pieux": None,
        "transit": None,
        "agrivolt": None,
        "ex_date": None,
        "ex_agriv": None,
        "ex_techniq": None,
        "geom": None,
        "creation": None,
        "dern_modif": None,
        "archive": None,
        "statut": None,
        "supprime": None,
    }
    if in_data is not None:
        dossier_number = in_data["number"]
        out_data["id_dossier"] = dossier_number
        out_data["dern_modif"] = datetime.fromisoformat(in_data["dateDerniereModification"])
        out_data["creation"] = datetime.fromisoformat(in_data["dateDepot"])
        out_data["archive"] = in_data["archived"]
        out_data["statut"] = in_data["state"]
        out_data["supprime"] = in_data["dateSuppressionParUsager"] is not None
        parcels_list = []
        contains_raw_geometry = False
        if "champs" in in_data:
            for champ in in_data["champs"]:
                field_name = ""
                try:
                    if (
                        re.search(
                            r"^Cas particulier des projets en période transitoire +:",
                            champ["label"],
                        )
                        is not None
                    ):  #
                        field_name = "transit"
                        out_data[field_name] = bool(champ["checked"])
                    elif (
                        re.search(
                            r"mon projet se situe dans la période des mesures transitoires et qu'il remplit l'ensemble des conditions",
                            champ["label"],
                        )
                        is not None
                    ):
                        field_name = "ex_date"
                        out_data[field_name] = bool(champ["checked"])
                    elif (
                        re.search(
                            r"^Cas particulier des projets agrivoltaïques +:",
                            champ["label"],
                        )
                        is not None
                    ):  #
                        field_name = "agrivolt"
                        out_data[field_name] = bool(champ["checked"])
                    elif (
                        re.search(
                            r"mon projet est une installation agrivoltaïque qui remplit l'ensemble de critères de la question précédente",
                            champ["label"],
                        )
                        is not None
                    ):
                        field_name = "ex_agriv"
                        out_data[field_name] = bool(champ["checked"])
                    elif re.search(r"^Etes-vous le porteur de projet", champ["label"]) is not None:
                        field_name = "porteur"
                        out_data[field_name] = bool(champ["checked"])
                    elif re.search(r"SIRET du porteur", champ["label"]) is not None:
                        field_name = "siret_port"
                        out_data[field_name] = str(champ["stringValue"])
                    elif (
                        re.search(r"référence de l'autorisation d'urbanisme", champ["label"])
                        is not None
                    ):
                        field_name = "ref_urba"
                        out_data[field_name] = str(champ["stringValue"])
                    elif re.search(r"type de projet principal", champ["label"]) is not None:
                        field_name = "type_proj"
                        out_data[field_name] = str(champ["stringValue"])
                    elif (
                        re.search(
                            r"installations de type trackers.*surface du socle béton",
                            champ["label"],
                        )
                        is not None
                    ):
                        field_name = "surf_socle"
                        out_data[field_name] = float(champ["decimalNumber"])
                    elif re.search(r"avancement du projet", champ["label"]) is not None:
                        field_name = "etat"
                        out_data[field_name] = str(champ["stringValue"])
                    elif re.search(r"puissance crête maximum", champ["label"]) is not None:
                        field_name = "puiss_max"
                        out_data[field_name] = int(champ["integerNumber"])
                    elif (
                        re.search(
                            r"date du dépôt de la demande d'autorisation d'urbanisme",
                            champ["label"],
                        )
                        is not None
                    ):
                        field_name = "date_depot"
                        out_data[field_name] = date.fromisoformat(champ["date"])
                    elif (
                        re.search(
                            r"date à laquelle l'autorisation d'urbanisme a été délivrée",
                            champ["label"],
                        )
                        is not None
                    ):
                        field_name = "date_deliv"
                        out_data[field_name] = date.fromisoformat(champ["date"])
                    elif re.search(r"date d'installation effective", champ["label"]) is not None:
                        field_name = "date_insta"
                        out_data[field_name] = date.fromisoformat(champ["date"])
                    elif re.search(r"durée initiale d'exploitation", champ["label"]) is not None:
                        field_name = "duree_exp"
                        out_data[field_name] = int(champ["integerNumber"])
                    elif re.search(r"adresse d’implantation du projet", champ["label"]) is not None:
                        field_name = "adresse"
                        out_data[field_name] = str(champ["stringValue"])
                    elif (
                        re.search(r"surface occupée par l'installation", champ["label"]) is not None
                    ):
                        field_name = "surf_occup"
                        out_data[field_name] = float(champ["decimalNumber"])
                    elif (
                        re.search(r"surface du terrain d’implantation", champ["label"]) is not None
                    ):
                        field_name = "surf_terr"
                        out_data[field_name] = float(champ["decimalNumber"])
                    elif re.search(r"Le projet est-il situé en \?", champ["label"]) is not None:
                        field_name = "localisat"
                        out_data[field_name] = str(champ["stringValue"])
                    elif re.search(r"nature principale du sol", champ["label"]) is not None:
                        field_name = "sol_nature"
                        out_data[field_name] = str(champ["primaryValue"])
                        if champ["secondaryValue"]:
                            field_name = "sol_detail"
                            out_data[field_name] = str(champ["secondaryValue"])
                    elif (
                        re.search(
                            r"type d’usage actuel du terrain d’implantation",
                            champ["label"],
                        )
                        is not None
                    ):
                        field_name = "usage_terr"
                        out_data[field_name] = str(champ["stringValue"])
                    elif re.search(r"type d’activité agricole", champ["label"]) is not None:
                        field_name = "type_agri"
                        out_data[field_name] = str(champ["stringValue"])
                    elif re.search(r"production agricole initiale", champ["label"]) is not None:
                        field_name = "agri_ini"
                        out_data[field_name] = str(champ["stringValue"])
                    elif re.search(r"production agricole résiduelle", champ["label"]) is not None:
                        field_name = "agri_resid"
                        out_data[field_name] = str(champ["stringValue"])
                    elif (
                        re.search(
                            r"ancrage au sol.*avec des pieux en bois ou en métal",
                            champ["label"],
                        )
                        is not None
                    ):
                        field_name = "nat_pieux"
                        out_data[field_name] = bool(champ["checked"])
                    elif re.search(r"type d'ancrage au sol", champ["label"]) is not None:
                        field_name = "ancrage"
                        out_data[field_name] = str(champ["stringValue"])
                    elif re.search(r"type de clôture", champ["label"]) is not None:
                        field_name = "cloture"
                        out_data[field_name] = str(champ["stringValue"])
                    elif re.search(r"type de revêtement", champ["label"]) is not None:
                        field_name = "revetement"
                        out_data[field_name] = str(champ["stringValue"])
                    elif re.search(r"hauteur des panneaux", champ["label"]) is not None:
                        field_name = "haut_pann"
                        out_data[field_name] = float(champ["decimalNumber"])
                    elif re.search(r"espacement entre deux rangées", champ["label"]) is not None:
                        field_name = "espacement"
                        out_data[field_name] = float(champ["decimalNumber"])
                    elif (
                        re.search(
                            r"^Les caractéristiques techniques de mon installation ne répondent pas aux critères",
                            champ["label"],
                        )
                        is not None
                    ):
                        field_name = "ex_techniq"
                        out_data[field_name] = not bool(champ["checked"])
                    elif (
                        re.search(
                            r"^Les caractéristiques techniques de mon installation répondent aux critères",
                            champ["label"],
                        )
                        is not None
                    ):
                        field_name = "ex_techniq"
                        out_data[field_name] = bool(champ["checked"])
                    elif champ["__typename"] == "CarteChamp" and "parcelles" in champ["label"]:
                        field_name = "num_parcelles"
                        geometry = ogr.CreateGeometryFromWkt("MULTIPOLYGON EMPTY", SOURCE_SRS)
                        for geo_area in champ["geoAreas"]:
                            if geo_area["source"] == "cadastre":
                                parcel_uid = "{}{}{:0>2}{:0>4}".format(
                                    geo_area["commune"],
                                    geo_area["prefixe"],
                                    geo_area["section"],
                                    geo_area["numero"],
                                )
                                parcels_list.append(parcel_uid)
                                parcel_geom = ogr.CreateGeometryFromJson(
                                    json.dumps(geo_area["geometry"], indent=None)
                                )
                                # This geometry's SRS in the source is EPSG:4326 but with swapped axis
                                # Axes order: (longitude, latitude)
                                parcel_geom.SwapXY()
                                parcel_geom.AssignSpatialReference(SOURCE_SRS)
                                parcel_geom = parcel_geom.MakeValid()
                                tmp_geometry = geometry.Clone()
                                geometry = tmp_geometry.Union(parcel_geom)
                                logger.debug(
                                    "geometry type for parcel "
                                    + f"'{parcel_uid}': {parcel_geom.GetGeometryName()}"
                                )
                            else:
                                contains_raw_geometry = True
                        tmp_geometry = geometry.Clone()
                        geometry = ogr.ForceToMultiPolygon(tmp_geometry.MakeValid())
                        logger.debug(
                            "geometry type for dossier "
                            + f"'{dossier_number}': {geometry.GetGeometryName()}"
                        )
                        if len(parcels_list) == 0:
                            logger.warning(
                                f"dossier '{dossier_number}' contains no selected parcel."
                            )
                        if contains_raw_geometry:
                            logger.warning(f"dossier '{dossier_number}' contains raw geometries")
                except (KeyError, TypeError, ValueError) as exc:
                    exc_type = str(type(exc)).replace("<class '", "").replace("'>", "")
                    message = (
                        f"on dossier '{dossier_number}', champ '{field_name}'"
                        + f" -- {exc_type}: {exc.args[0]}"
                    )
                    logger.warning(message)
        try:
            if out_data["porteur"]:
                out_data["siret_port"] = str(in_data["demandeur"]["siret"])
            if not out_data["transit"]:
                out_data["ex_date"] = False
            if len(parcels_list) > 0:
                out_data["num_parcelles"] = ";".join(parcels_list)
            out_data["geom"] = geometry
        except Exception as exc:
            logger.error(f"on dossier '{dossier_number}'")
            raise exc
    return out_data


def format_source_result(data: list[dict]) -> list[dict]:
    """Transform input data to output data

    Args:
        data (List[Dict]): raw data as returned by query_source_api

    Returns:
        List[Dict]: features list with the target SQL table structure
    """
    feature_list = []
    id_list = []
    # debug_input_str = json.dumps(data, sort_keys=True, default=str)
    # logger.debug(f"Raw input data: {debug_input_str}")
    for page in data["demarche"]["dossiers"]:
        for entry in page["nodes"]:
            if entry["number"] not in id_list:
                id_list.append(entry["number"])
                feature = format_feature(entry)
                feature_list.append(feature)
    feature_list.sort(key=lambda feature: feature["id_dossier"])
    # debug_output_str = json.dumps(feature_list, sort_keys=True, default=str)
    # logger.debug(f"Output data: {debug_output_str}")
    return deepcopy(feature_list)


def get_deleted_dossier_list(data: list[dict]) -> set:
    """Extract deleted dossiers from input data

    Args:
        data (List[Dict]): raw data as returned by query_source_api

    Returns:
        set: deleted dossiers id set
    """
    id_set = set()
    for page in data["demarche"]["deletedDossiers"]:
        for entry in page["nodes"]:
            id_set.add(entry["number"])
    return deepcopy(id_set)


def load_configuration(path: Path) -> dict:
    """Returns validated configuration from file

    Args:
        path (str): path to the configuration file

    Raises:
        jonschema.ValidationError: The configuration file does
            not match the validation schema

    Returns:
        Dict: the configuration object translated from the input file
    """
    try:
        resource_dir = os.environ.get("OCSGE_PV_RESOURCE_DIR")
        if resource_dir is None or resource_dir.strip() == "":
            resource_dir = "/app/src/ocsge_pv/resources"
        validation_schema_path = Path(resource_dir, "import_declarations_config.schema.json")
        with open(path, encoding="utf-8") as config_file:
            config_str = config_file.read()
        source_configuration = json.loads(config_str)
        with open(validation_schema_path, encoding="utf-8") as schema_file:
            schema_str = schema_file.read()
        schema = json.loads(schema_str)
        jsonschema.validate(source_configuration, schema)
        modified_configuration = deepcopy(source_configuration)
        # Output database
        modified_configuration["output"]["_pg_string"] = (
            "host="
            + modified_configuration["output"]["host"]
            + " port="
            + str(modified_configuration["output"]["port"])
            + " dbname="
            + modified_configuration["output"]["name"]
            + " user="
            + modified_configuration["output"]["user"]
            + " password="
            + modified_configuration["output"]["password"]
        )
        return modified_configuration
    except Exception as exc:
        raise exc


def mark_as_deleted(output_conf: dict, data: set) -> None:
    """Write declarations to database

    Args:
        output_conf (Dict): configuration used to access the database
        data (set): set of deleted dossiers id
    """
    with psycopg.connect(output_conf["_pg_string"], autocommit=True) as conn:
        cur = conn.cursor()
        try:
            with conn.transaction():
                for id_dossier in data:
                    id_count_row = cur.execute(
                        sql.SQL("SELECT COUNT(*) FROM {table} WHERE {id_key} = {id_value}").format(
                            table=sql.Identifier(output_conf["schema"], output_conf["table"]),
                            id_key=sql.Identifier("id_dossier"),
                            id_value=sql.Placeholder(),
                        ),
                        [id_dossier],
                    ).fetchone()
                    if id_count_row[0] == 1:
                        instruction = sql.SQL(
                            "UPDATE {table} SET ({key}) = ({value}) WHERE {id_key} = {id_value}"
                        ).format(
                            table=sql.Identifier(output_conf["schema"], output_conf["table"]),
                            key=sql.SQL("supprime"),
                            value=sql.Placeholder(),
                            id_key=sql.Identifier("id_dossier"),
                            id_value=sql.Placeholder(),
                        )
                        cur.execute(instruction, {"value": True, "id_value": id_dossier})
                    elif id_count_row[0] > 1:
                        raise ValueError(
                            "To many declarations found in database with id_dossier="
                            + f"{feature['id_dossier']}: {id_count_row[0]} entries found."
                        )
        except Exception as exc:
            conn.rollback()
            raise exc


def query_source_api(input_conf: dict) -> list[dict]:
    """Read input data from the source GraphQL API

    Args:
        input_conf (Dict): configuration used to access the API

    Returns:
        List[Dict]: The converted input data structured almost like
            the original full response model, but with the properties
            "demarche"."dossiers" and "demarche"."deletedDossiers"
            expressed as lists of pages.
    """
    resource_dir = os.environ.get("OCSGE_PV_RESOURCE_DIR")
    if resource_dir is None or resource_dir.strip() == "":
        resource_dir = "/app/src/ocsge_pv/resources"
    gql_headers = {"Authorization": "Bearer {:s}".format(input_conf["auth_token"])}
    aiohttp_client_session_args = {
        # The following option lets the client use the proxy defined by environment variables
        # Else, the proxy must be defined in the .netrc file
        # (its path, "$HOME/.netrc" by default, is defined by the "NETRC" environment variable)
        "trust_env": True
    }
    transport = AIOHTTPTransport(
        url=input_conf["api_url"],
        headers=gql_headers,
        ssl=True,
        client_session_args=aiohttp_client_session_args,
    )
    gql_client = Client(transport=transport, fetch_schema_from_transport=True)
    gql_query_filepath = Path(resource_dir, "get_demarche_query.gql")
    with open(gql_query_filepath, encoding="utf-8") as query_file:
        query_string = query_file.read()
    query_gql = gql(query_string)
    base_params = {
        "demarcheNumber": input_conf["demarche_id"],
        "first": 100,
        "includeAnotations": False,
        "includeAvis": False,
        "includeChamps": True,
        "includeCorrections": True,
        "includeDeletedDossiers": True,
        "includeDossiers": True,
        "includeGeometry": True,
        "includeGroupeInstructeurs": False,
        "includeInstructeurs": False,
        "includeLabels": False,
        "includeMessages": False,
        "includePendingDeletedDossiers": False,
        "includeRevision": False,
        "includeService": False,
        "includeTraitements": False,
        "order": "ASC",
    }
    date_filter = input_conf.get("min_update_datetime")
    if date_filter is not None:
        base_params["updatedSince"] = date_filter
    category_list = (None, "dossiers", "deletedDossiers")
    full_result = {"demarche": {}}
    for category in category_list:
        category_params = {
            "includeDossiers": category == "dossiers",
            "includeDeletedDossiers": category == "deletedDossiers",
            "includePendingDeletedDossiers": category == "pendingDeletedDossiers",
        }
        query_params = base_params | category_params
        if category is None:
            # Non paginated data, common to the whole datasource
            common_result = gql_client.execute(query_gql, variable_values=query_params)
            for key in iter(common_result.keys()):
                if key == "demarche":
                    for sub_key in iter(common_result[key].keys()):
                        if sub_key not in category_list:
                            full_result[key][sub_key] = deepcopy(common_result[key][sub_key])
                else:
                    full_result[key] = deepcopy(common_result[key])
        else:
            # Paginated data, specific to a type of dossier
            category_result_list = []
            last_cursor = None
            has_next_page = True
            while has_next_page:
                if last_cursor is not None:
                    query_params["after"] = last_cursor
                response_page = gql_client.execute(query_gql, variable_values=query_params)
                category_result = response_page["demarche"][category]
                category_result_list.append(deepcopy(category_result))
                last_cursor = category_result["pageInfo"]["endCursor"]
                has_next_page = category_result["pageInfo"]["hasNextPage"]
            full_result["demarche"][category] = deepcopy(category_result_list)
    return full_result


def write_output(output_conf: dict, data: list) -> None:
    """Write declarations to database

    Args:
        output_conf (Dict): configuration used to access the database
        data (List): list of output data to insert
    """
    keys_list = None
    line_writing_mode = None
    values_list = None
    value_dict = None
    cur = None
    with psycopg.connect(output_conf["_pg_string"], autocommit=True) as conn:
        cur = conn.cursor()
        try:
            with conn.transaction():
                coord_transform = None
                swap = False
                instruction = None
                out_srid = int(
                    cur.execute(
                        sql.SQL("SELECT Find_SRID({schema}, {table}, {column})").format(
                            schema=sql.Placeholder("schema", psycopg.adapt.PyFormat.TEXT),
                            table=sql.Placeholder("table", psycopg.adapt.PyFormat.TEXT),
                            column=sql.Placeholder("column", psycopg.adapt.PyFormat.TEXT),
                        ),
                        {
                            "schema": output_conf["schema"],
                            "table": output_conf["table"],
                            "column": "geom",
                        },
                    ).fetchone()[0]
                )
                logger.debug(f"Output table SRID: {repr(out_srid)}")
                if out_srid == SOURCE_SRID:
                    out_srs = SOURCE_SRS.Clone()
                    logger.debug(f"Output table SRID's name: {out_srs.GetName()}")
                else:
                    out_srs = osr.SpatialReference()
                    out_srs.ImportFromEPSG(out_srid)
                    logger.debug(f"Output table SRID's name: {out_srs.GetName()}")
                    coord_transform = osr.CreateCoordinateTransformation(SOURCE_SRS, out_srs)
                if out_srs.EPSGTreatsAsLatLong() == 1 or out_srs.EPSGTreatsAsNorthingEasting() == 1:
                    swap = True
                for feature in data:
                    id_count_row = cur.execute(
                        sql.SQL("SELECT COUNT(*) FROM {table} WHERE {id_key} = {id_value}").format(
                            table=sql.Identifier(output_conf["schema"], output_conf["table"]),
                            id_key=sql.Identifier("id_dossier"),
                            id_value=sql.Placeholder(),
                        ),
                        [feature["id_dossier"]],
                    ).fetchone()
                    if id_count_row[0] > 1:
                        raise ValueError(
                            "Too many declarations found in database with id_dossier="
                            + f"{feature['id_dossier']}: {id_count_row[0]} entries found."
                        )
                    keys_list = []
                    value_dict = {}
                    geom_ogr = feature["geom"].Clone()
                    if coord_transform is not None:
                        geom_ogr.Transform(coord_transform)
                    if swap:
                        geom_ogr.SwapXY()
                        # PostGIS only uses (lon,lat) or (east,noth) order in WKT
                    geom_wkt = geom_ogr.ExportToWkt()
                    value_dict["geom"] = geom_wkt
                    if id_count_row[0] == 0:
                        line_writing_mode = "insert"
                        for field in feature.keys():
                            if field != "geom":
                                keys_list.append(field)
                                value_dict[field] = feature[field]
                        template = (
                            "INSERT INTO {table} ({keys}, {geom_key}) "
                            + "VALUES({values}, ST_GeomFromText({geom_value}))"
                        )
                        instruction = sql.SQL(template).format(
                            table=sql.Identifier(output_conf["schema"], output_conf["table"]),
                            keys=sql.SQL(", ").join(map(sql.Identifier, keys_list)),
                            values=sql.SQL(", ").join(map(sql.Placeholder, keys_list)),
                            geom_key=sql.Identifier("geom"),
                            geom_value=sql.Placeholder("geom"),
                        )
                        cur.execute(
                            instruction,
                            value_dict,
                        )
                    elif id_count_row[0] == 1:
                        # What to do if this declaration is already described in the database ?
                        line_writing_mode = "update"
                        for field in feature.keys():
                            if field not in ["id_dossier", "geom"]:
                                keys_list.append(field)
                                value_dict[field] = feature[field]
                        template = (
                            "UPDATE {table} SET ({keys}, {geom_key}) = ({values}, "
                            + "ST_GeomFromText({geom_value})) WHERE {id_key} = {id_value}"
                        )
                        instruction = sql.SQL(template).format(
                            table=sql.Identifier(output_conf["schema"], output_conf["table"]),
                            keys=sql.SQL(", ").join(map(sql.Identifier, keys_list)),
                            values=sql.SQL(", ").join(map(sql.Placeholder, keys_list)),
                            id_key=sql.Identifier("id_dossier"),
                            id_value=feature["id_dossier"],
                            geom_key=sql.Identifier("geom"),
                            geom_value=sql.Placeholder("geom"),
                        )
                        cur.execute(
                            instruction,
                            value_dict,
                        )
        except psycopg.Error as exc:
            logger.error(f"PostgreSQL error code: {exc.sqlstate}")
            logger.error(f"PG_DIAG_CONTEXT: {exc.diag.context}")
            logger.error(f"PG_DIAG_MESSAGE_PRIMARY: {exc.diag.message_primary}")
            logger.error(f"PG_DIAG_MESSAGE_DETAIL: {exc.diag.message_detail}")
            logger.error(f"PG_DIAG_MESSAGE_HINT: {exc.diag.message_hint}")
            logger.error(
                f"Cursor query: (raw_query: {cur._query.query}, parameters: {cur._query.params})"
            )
            conn.rollback()
            logger.error(f"Line writing mode: '{line_writing_mode}'\n")
            logger.error(f"Values mapping: '{value_dict}'\n")
            raise exc
        except Exception as exc:
            conn.rollback()
            logger.error(f"Line writing mode: '{line_writing_mode}'\n")
            logger.error(f"Values mapping: '{value_dict}'\n")
            raise exc


# -- MAIN FUNCTION --


def main() -> int:
    """Main routine, entrypoint for the program

    Args:
        path (str): path to the configuration file
            (implicit, contained in sys.argv[])

    Returns:
        int: shell exit code of the execution
    """
    try:
        logger.info("Start of declaration data import.")
        cli_args = cli_arg_parser()
        if cli_args.verbose:
            logger.setLevel(logging.DEBUG)
        logger.info("Loading configuration...")
        configuration = load_configuration(cli_args.path)
        logger.info("Fetching data...")
        input_data = query_source_api(configuration["input"])
        deleted_data = get_deleted_dossier_list(input_data)
        logger.info("Formating data...")
        output_data = format_source_result(input_data)
        logger.info("Writing into database...")
        write_output(configuration["output"], output_data)
        mark_as_deleted(configuration["output"], deleted_data)
        logger.info("End of declaration data import.")
        return 0
    except Exception:
        logger.error(traceback.format_exc())
        return 1


# -- MAIN SCRIPT --


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
