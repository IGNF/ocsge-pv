"""Photovoltaic farm declarations importer

Import photovoltaic farms declaration files from the official 
declaration service API, and insert them into a database. 

This script's only argument is the path to a configuration file.
A model named 'import_declarations_config.ok.json' is available in 
the 'tests/fixture' folder.

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
# standard library
import argparse
from copy import deepcopy
from datetime import date, datetime
import json
import os
import pathlib
import re
import sys
import traceback
from typing import Dict, List
from zoneinfo import ZoneInfo

# 3rd party
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
import jsonschema
import psycopg
from psycopg import sql

# package

# -- GLOBALS --
try:
    timezone_name = os.environ["TZ"]
    print(f"Zone horaire définie par VE : '{timezone_name}'")
except KeyError:
    timezone_name = "Europe/Paris"
    print(f"Zone horaire définie par défaut : '{timezone_name}'")
timezone_info = ZoneInfo(timezone_name)

# -- FUNCTIONS --
def cli_arg_parser() -> argparse.Namespace:
    """Parse CLI arguments

    Args:
        * sys.argv (implicit) - CLI arguments

    Returns:
        argparse.Namespace: processed arguments
    """
    parser = argparse.ArgumentParser(
        prog="import_declarations",
        description=("Import photovoltaic farms declaration files from the official declaration"
            + " service API, and insert them into a database.")
    )
    parser.add_argument("path",
        type=pathlib.Path,
        help="the path of the configuration file for %(prog)s"
    )
    parser.add_argument("-v", "--verbose",
        dest="verbose",
        action="store_true",
        help="output more logs"
    )
    return parser.parse_args()

def format_feature(in_data: Dict) -> Dict:
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
    }
    if in_data is not None:
        dossier_number = in_data["number"]
        out_data["id_dossier"] = dossier_number
        parcels_list = []
        contains_raw_geometry = False
        for champ in in_data["champs"]:
            field_name = ""
            try:
                if re.search(r"^Cas particulier des projets en période transitoire +:", champ["label"]) is not None:#
                    field_name = "transit"
                    out_data[field_name] = bool(champ["checked"])
                elif re.search(
                        r"mon projet se situe dans la période des mesures transitoires et qu'il remplit l'ensemble des conditions",
                        champ["label"]) is not None:
                    field_name = "ex_date"
                    out_data[field_name] = bool(champ["checked"])
                elif re.search(r"^Cas particulier des projets agrivoltaïques +:", champ["label"]) is not None:#
                    field_name = "agrivolt"
                    out_data[field_name] = bool(champ["checked"])
                elif re.search(
                        r"mon projet est une installation agrivoltaïque qui remplit l'ensemble de critères de la question précédente",
                        champ["label"]) is not None:
                    field_name = "ex_agriv"
                    out_data[field_name] = bool(champ["checked"])
                elif re.search(r"^Etes-vous le porteur de projet", champ["label"]) is not None:
                    field_name = "porteur"
                    out_data[field_name] = bool(champ["checked"])
                elif re.search(r"SIRET du porteur", champ["label"]) is not None:
                    field_name = "siret_port"
                    out_data[field_name] = str(champ["stringValue"])
                elif re.search(r"référence de l'autorisation d'urbanisme", champ["label"]) is not None:
                    field_name = "ref_urba"
                    out_data[field_name] = str(champ["stringValue"])
                elif re.search(r"type de projet principal", champ["label"]) is not None:
                    field_name = "type_proj"
                    out_data[field_name] = str(champ["stringValue"])
                elif re.search(r"installations de type trackers.*surface du socle béton", champ["label"]) is not None:
                    field_name = "surf_socle"
                    out_data[field_name] = float(champ["decimalNumber"]) 
                elif re.search(r"avancement du projet", champ["label"]) is not None:
                    field_name = "etat"
                    out_data[field_name] = str(champ["stringValue"])
                elif re.search(r"puissance crête maximum", champ["label"]) is not None:
                    field_name = "puiss_max"
                    out_data[field_name] = int(champ["integerNumber"])
                elif re.search(r"date du dépôt de la demande d'autorisation d'urbanisme", champ["label"]) is not None:
                    field_name = "date_depot"
                    out_data[field_name] = date.fromisoformat(champ["date"])
                elif re.search(r"date à laquelle l'autorisation d'urbanisme a été délivrée", champ["label"]) is not None:
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
                elif re.search(r"surface occupée par l'installation", champ["label"]) is not None:
                    field_name = "surf_occup"
                    out_data[field_name] = float(champ["decimalNumber"])
                elif re.search(r"surface du terrain d’implantation", champ["label"]) is not None:
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
                elif re.search(r"type d’usage actuel du terrain d’implantation", champ["label"]) is not None:
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
                elif re.search(r"ancrage au sol.*avec des pieux en bois ou en métal", champ["label"]) is not None:
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
                elif re.search(r"^Les caractéristiques techniques de mon installation ne répondent pas aux critères", champ["label"]) is not None:
                    field_name = "ex_techniq"
                    out_data[field_name] = (not bool(champ["checked"]))
                elif re.search(r"^Les caractéristiques techniques de mon installation répondent aux critères", champ["label"]) is not None:
                    field_name = "ex_techniq"
                    out_data[field_name] = bool(champ["checked"])
                elif champ["__typename"] == "CarteChamp" and "parcelles" in champ["label"]:
                    field_name = "num_parcelles"
                    for geo_area in champ["geoAreas"]:
                        if geo_area["source"] == "cadastre":
                            parcel_uid = "{0}{1}{2:0>2}{3:0>4}".format(
                                geo_area["commune"],
                                geo_area["prefixe"],
                                geo_area["section"],
                                geo_area["numero"],
                            )
                            parcels_list.append(parcel_uid)
                        else:
                            contains_raw_geometry = True
                    if len(parcels_list) == 0:
                        raise ValueError("Selected parcels list must contain at least one element.")
                    if contains_raw_geometry:
                        raise ValueError(f"dossier '{dossier_number}' contains raw geometries")
            except (KeyError, TypeError, ValueError) as exc:
                exc_type = str(type(exc)).replace("<class '", "").replace("'>", "")
                log(f"WARNING (format_feature): on dossier '{dossier_number}', champ '{field_name}'")
                log(f"---------- {exc_type}: ", exc)
        try:
            if out_data["porteur"]:
                out_data["siret_port"] = str(in_data["demandeur"]['siret'])
            if not out_data["transit"]:
                out_data["ex_date"] = False
            if len(parcels_list) > 0:
                out_data["num_parcelles"] = ";".join(parcels_list)
        except Exception as exc:
            exc_type = str(type(exc)).replace("<class '", "").replace("'>", "")
            log(f"ERROR (format_feature): on dossier '{dossier_number}'")
            log(f"---------- {exc_type}: ", exc)
            raise exc
    return out_data
    
def format_source_result(data: Dict) -> List:
    """Transform input data to output data

    Args:
        data (Dict): input data with its original structure

    Returns:
        List: features list with the target SQL table structure
    """
    feature_list = []
    id_list = []
    for entry in data["demarche"]["dossiers"]["nodes"]:
        if entry["number"] not in id_list:
            id_list.append(entry["number"])
            feature = format_feature(entry)
            feature_list.append(feature)
    feature_list.sort(key=lambda feature: feature["id_dossier"])
    return deepcopy(feature_list)

def load_configuration(path: str) -> Dict:
    """Returns validated configuration from file
    
    Args:
        path (str): path to the configuration file
    
    Raises:
        jonschema.ValidationError: The configuration file does not match the validation schema

    Returns:
        Dict: the configuration object translated from the input file
    """
    try:
        validation_schema_path = "src/ocsge_pv/resources/import_declarations_config.schema.json"
        with open(path, "r", encoding="utf-8") as config_file:
            config_str = config_file.read()
        source_configuration = json.loads(config_str)
        with open(validation_schema_path, "r", encoding="utf-8") as schema_file:
            schema_str = schema_file.read()
        schema = json.loads(schema_str)
        jsonschema.validate(source_configuration, schema)
        modified_configuration = deepcopy(source_configuration)
        # Output database
        modified_configuration["output"]["_pg_string"] = (
            "host=" + modified_configuration['output']['host']
            + " port=" + str(modified_configuration['output']['port'])
            + " dbname=" + modified_configuration['output']['name']
            + " user=" + modified_configuration['output']['user']
            + " password=" + modified_configuration['output']['password'])
        return modified_configuration
    except Exception as exc:
        exc_type = str(type(exc)).replace("<class '", "").replace("'>", "")
        log(f"ERROR (load_configuration) - {exc_type}:", exc)
        raise exc

def log(*message: str) -> None:
    """Prints message with date and time

    Args:
        message (str): messages to log (like in the print function)
    """
    print(datetime.now(timezone_info), "|", *message)

def query_source_api(input_conf: Dict) -> Dict:
    """Read input data from the source GraphQL API

    Args:
        input_conf (Dict): configuration used to access the API

    Returns:
        Dict: The converted input data with its original structure
    """
    gql_headers = {
        "Authorization": "Bearer {0:s}".format(input_conf["auth_token"]) 
    }
    aiohttp_client_session_args = {
        # The followig option let the client use the proxy defined by environment variables
        # Else, the proxy must be defined in the .netrc file
        # (its path, "$HOME/.netrc" by default, is defined by the "NETRC" environment variable)
        "trust_env": True
    }
    transport = AIOHTTPTransport(
        url=input_conf["api_url"],
        headers=gql_headers,
        ssl=True,
        client_session_args=aiohttp_client_session_args
    )
    gql_client = Client(transport=transport, fetch_schema_from_transport=True)
    with open("src/ocsge_pv/resources/get_demarche_query.gql", encoding="utf-8") as query_file:
        query_string = query_file.read()
    query_gql = gql(query_string)
    query_params = {
        "demarcheNumber": input_conf["demarche_id"],
        "includeDossiers": True,
        "includeChamps": True,
        "state": "accepte",
        "order": "ASC"
    }
    date_filter = input_conf.get("min_update_datetime")
    if date_filter is not None:
        query_params["updatedSince"] = date_filter
    result = gql_client.execute(query_gql, variable_values=query_params)
    return deepcopy(result)

def write_output(output_conf: Dict, data: List) -> None:
    """Write declarations to database
    
    Args:
        output_conf (Dict): configuration used to access the database
        data (List): list of output data to insert
    """
    declaration_id_list = []
    with psycopg.connect(output_conf["_pg_string"], autocommit=True) as conn:
        cur = conn.cursor()
        try:
            with conn.transaction():
                for feature in data:
                    id_count_row = cur.execute(
                        sql.SQL(
                            "SELECT COUNT(*) FROM {table} WHERE {id_key} = {id_value}"
                        ).format(
                            table=sql.Identifier(output_conf["schema"], output_conf["table"]),
                            id_key=sql.Identifier("id_dossier"),
                            id_value=sql.Placeholder()
                        ),
                        [feature["id_dossier"]]
                    ).fetchone()
                    keys_list = []
                    values_list = []
                    if id_count_row[0] == 0:
                        for field in feature.keys():
                            keys_list.append(sql.Identifier(field))
                            values_list.append(feature[field])
                        values_count = len(values_list)
                        instruction = sql.SQL(
                            "INSERT INTO {table} ({keys}) VALUES({values})"
                        ).format(
                                table=sql.Identifier(output_conf["schema"], output_conf["table"]),
                                keys=sql.SQL(", ").join(keys_list),
                                values=sql.SQL(", ").join(sql.Placeholder() * values_count)
                        )
                        cur.execute(
                            instruction,
                            values_list
                        )
                    elif id_count_row[0] == 1:
                        # What to do if this declaration is already described in the database ?
                        for field in feature.keys():
                            if field != "id_dossier":
                                keys_list.append(sql.Identifier(field))
                                values_list.append(feature[field])
                        values_count = len(values_list)
                        instruction = sql.SQL(
                            "UPDATE {table} SET ({keys}) = ({values}) WHERE {id_key} = {id_value}"
                        ).format(
                                table=sql.Identifier(output_conf["schema"], output_conf["table"]),
                                keys=sql.SQL(", ").join(keys_list),
                                values=sql.SQL(", ").join(sql.Placeholder() * values_count,
                                id_key=sql.Identifier("id_dossier"),
                                id_value=sql.Placeholder())
                        )
                        cur.execute(
                            instruction,
                            values_list,
                            feature["id_dossier"]
                        )
                    else:
                        raise ValueError(("To many declarations found in database with id_dossier="
                            + f"{feature['id_dossier']}: {id_count_row[0]} entries found."))
        except Exception as exc:
            exc_type = str(type(exc)).replace("<class '", "").replace("'>", "")
            log(f"ERROR (write_output) - {exc_type}:", traceback.format_exc())
            conn.rollback()
            raise exc

# -- MAIN FUNCTION --
def main() -> None:
    """Main routine, entrypoint for the program
        
    Args:
        configuration_file_path (str): path to the configuration file
            (implicit, contained in sys.argv[])
    
    Returns:
        int: shell exit code of the execution
    """
    try:
        log("Start of declaration data import.")
        cli_args = cli_arg_parser()
        if cli_args.verbose:
            log("Loading configuration...")
        configuration = load_configuration(cli_args.path)
        if cli_args.verbose:
            log("Fetching data...")
        input_data = query_source_api(configuration["input"])
        if cli_args.verbose:
            log("Formating data...")
        output_data = format_source_result(input_data)
        if cli_args.verbose:
            log("Writing into database...")
        write_output(configuration["output"], output_data)
        log("End of declaration data import.")
        return 0
    except Exception as exc:
        exc_type = str(type(exc)).replace("<class '", "").replace("'>", "")
        log(f"ERROR (main) - {exc_type}:", exc)
        return 1

# -- MAIN SCRIPT --
if (__name__ == "__main__"):
    exit_code = main()
    sys.exit(exit_code)
