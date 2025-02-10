"""Photovoltaic farm declarations importer

Import photovoltaic farms declaration files from the official 
declaration service API, and insert them into a database. 

This script's only argument is the path to a configuration file.
A model named 'import_declarations_config.ok.json' is available in 
the 'tests/fixture' folder.

This file contains the following functions :
    * format_feature - convert a feature's format from input to output
    * format_source_result - convert format from input data to output
    * load_configuration - return validated configuration from file
    * query_source_api - fetch input data from the source API
    * write_output - insert output data in the target table
    * main - main function of the script
"""

# -- IMPORTS --
# standard library
from copy import deepcopy
from datetime import date, datetime
import json
import os
import re
from typing import Dict
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
def format_feature(input: Dict) -> Dict:
    """Transform declaration dossier to postgis feature

    Args:
        input (Dict) - dossier's data for a single declaration

    Returns:
        Dict - structure to insert in the output database
    """
    output = {
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
    if input is not None:
        dossier_number = input["number"]
        output["id_dossier"] = dossier_number
        parcels_list = []
        contains_raw_geometry = False
        for champ in input["champs"]:
            field_name = ""
            try:
                if re.search(r"^Cas particulier des projets en période transitoire +:", champ["label"]) is not None:#
                    field_name = "transit"
                    output[field_name] = bool(champ["checked"])
                elif re.search(
                        r"mon projet se situe dans la période des mesures transitoires et qu'il remplit l'ensemble des conditions",
                        champ["label"]) is not None:
                    field_name = "ex_date"
                    output[field_name] = bool(champ["checked"])
                elif re.search(r"^Cas particulier des projets agrivoltaïques +:", champ["label"]) is not None:#
                    field_name = "agrivolt"
                    output[field_name] = bool(champ["checked"])
                elif re.search(
                        r"mon projet est une installation agrivoltaïque qui remplit l'ensemble de critères de la question précédente",
                        champ["label"]) is not None:
                    field_name = "ex_agriv"
                    output[field_name] = bool(champ["checked"])
                elif re.search(r"^Etes-vous le porteur de projet", champ["label"]) is not None:
                    field_name = "porteur"
                    output[field_name] = bool(champ["checked"])
                elif re.search(r"SIRET du porteur", champ["label"]) is not None:
                    field_name = "siret_port"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"référence de l'autorisation d'urbanisme", champ["label"]) is not None:
                    field_name = "ref_urba"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"type de projet principal", champ["label"]) is not None:
                    field_name = "type_proj"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"installations de type trackers.*surface du socle béton", champ["label"]) is not None:
                    field_name = "surf_socle"
                    output[field_name] = float(champ["decimalNumber"]) 
                elif re.search(r"avancement du projet", champ["label"]) is not None:
                    field_name = "etat"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"puissance crête maximum", champ["label"]) is not None:
                    field_name = "puiss_max"
                    output[field_name] = int(champ["integerNumber"])
                elif re.search(r"date du dépôt de la demande d'autorisation d'urbanisme", champ["label"]) is not None:
                    field_name = "date_depot"
                    output[field_name] = date.fromisoformat(champ["date"])
                elif re.search(r"date à laquelle l'autorisation d'urbanisme a été délivrée", champ["label"]) is not None:
                    field_name = "date_deliv"
                    output[field_name] = date.fromisoformat(champ["date"])
                elif re.search(r"date d'installation effective", champ["label"]) is not None:
                    field_name = "date_insta"
                    output[field_name] = date.fromisoformat(champ["date"])
                elif re.search(r"durée initiale d'exploitation", champ["label"]) is not None:
                    field_name = "duree_exp"
                    output[field_name] = int(champ["integerNumber"])
                elif re.search(r"adresse d’implantation du projet", champ["label"]) is not None:
                    field_name = "adresse"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"surface occupée par l'installation", champ["label"]) is not None:
                    field_name = "surf_occup"
                    output[field_name] = float(champ["decimalNumber"])
                elif re.search(r"surface du terrain d’implantation", champ["label"]) is not None:
                    field_name = "surf_terr"
                    output[field_name] = float(champ["decimalNumber"])
                elif re.search(r"Le projet est-il situé en \?", champ["label"]) is not None:
                    field_name = "localisat"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"nature principale du sol", champ["label"]) is not None:
                    field_name = "sol_nature"
                    output[field_name] = str(champ["primaryValue"])
                    if champ["secondaryValue"]:
                        field_name = "sol_detail"
                        output[field_name] = str(champ["secondaryValue"])
                elif re.search(r"type d’usage actuel du terrain d’implantation", champ["label"]) is not None:
                    field_name = "usage_terr"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"type d’activité agricole", champ["label"]) is not None:
                    field_name = "type_agri"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"production agricole initiale", champ["label"]) is not None:
                    field_name = "agri_ini"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"production agricole résiduelle", champ["label"]) is not None:
                    field_name = "agri_resid"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"ancrage au sol.*avec des pieux en bois ou en métal", champ["label"]) is not None:
                    field_name = "nat_pieux"
                    output[field_name] = bool(champ["checked"])
                elif re.search(r"type d'ancrage au sol", champ["label"]) is not None:
                    field_name = "ancrage"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"type de clôture", champ["label"]) is not None:
                    field_name = "cloture"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"type de revêtement", champ["label"]) is not None:
                    field_name = "revetement"
                    output[field_name] = str(champ["stringValue"])
                elif re.search(r"hauteur des panneaux", champ["label"]) is not None:
                    field_name = "haut_pann"
                    output[field_name] = float(champ["decimalNumber"])
                elif re.search(r"espacement entre deux rangées", champ["label"]) is not None:
                    field_name = "espacement"
                    output[field_name] = float(champ["decimalNumber"])
                elif re.search(r"^Les caractéristiques techniques de mon installation ne répondent pas aux critères", champ["label"]) is not None:
                    field_name = "ex_techniq"
                    output[field_name] = (not bool(champ["checked"]))
                elif re.search(r"^Les caractéristiques techniques de mon installation répondent aux critères", champ["label"]) is not None:
                    field_name = "ex_techniq"
                    output[field_name] = bool(champ["checked"])
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
                    if contains_raw_geometry
                        raise ValueError(f"ERROR: dossier '{dossier_number}' contains raw geometries")
            except KeyError as exc:
                print("ERROR: ", exc)
            except (TypeError, ValueError) as exc:
                print(f"ERROR (dossier '{dossier_number}', champ '{field_name}'): ", exc)
        if output["porteur"]:
            output["siret_port"] = str(dossier["demandeur"]['siret'])
        if not output["transit"]:
            output["ex_date"] = False
        if len(parcels_list) > 0:
            output["num_parcelles"] = ";".join(parcels_list)
    return output
    
def format_source_result(data: Dict) -> List:
    """Transform input data to output data

    Args:
        data (Dict) - input data with its original structure

    Returns:
        List - features list with the target SQL table structure
    """
    feature_list = []
    id_list = []
    for entry in data["demarche"]["dossiers"]["nodes"]:
        if entry["number"] not in id_list:
            id_list.append(entry["number"])
            feature = format_feature(entry)
            feature_list.append(feature)
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
    modified_configuration["output"]["_table_name_sql"] = sql.SQL(".").join([
        modified_configuration["output"]["schema"],
        modified_configuration["output"]["table"]])
    return modified_configuration

def query_source_api(input_conf: Dict) -> Dict:
    """Read input data from the source GraphQL API

    Args:
        input_conf (Dict) - configuration used to access the API

    Returns:
        Dict - The converted input data with its original structure
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
        "includeChamps": True
    }
    result = gql_client.execute(query_gql, variable_values=query_params)
    return deepcopy(result)

def write_output(output_conf: Dict, data: List) -> None:
    """Write declarations to database
    
    Args:
        configuration (Dict): program configuration, with DB informations
        update_list (List[Tuple]): list of (fid, geometry) of declarations to update
    """
    declaration_id_list = []
    with psycopg.connect(output_conf["_pg_string"]) as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("BEGIN"))
            for feature in data:
                keys_list = []
                values_list = []
                for field in feature.keys():
                    keys_list.append(sql.Identifier(field))
                    values_list.append(feature[field])
                instruction = sql.SQL(
                    "INSERT INTO {table} ({keys}) VALUES({values})"
                ).format(
                        table=output_conf["_table_name_sql"]
                        keys=sql.SQL(", ").join(keys_list),
                        values=sql.SQL(", ").join(sql.Placeholder() * len(values_list))
                )
                cur.execute(
                    instruction,
                    values_list
                )
            cur.execute(sql.SQL("COMMIT"))

# -- MAIN FUNCTION --
def main(configuration_file_path: str) -> None:
    """Main routine, entrypoint for the program
        
    Args:
        configuration_file_path (str): path to the configuration file
    """
    configuration = load_configuration(configuration_file_path)
    input_data = query_source_api(configuration["input"])
    output_data = format_source_result(input_data)
    write_output(configuration["output"], output_data)

# -- MAIN SCRIPT --
if (__name__ == "__main__"):
    try:
        print(datetime.now(timezone_info), "|", "Début de l'import des données de déclaration.")
        main(sys.argv[1:])
        print(datetime.now(timezone_info), "|", "Fin de l'import des données de déclaration.")
        sys.exit(0)
    except Exception as exc:
        print(exc)
        sys.exit(1)
