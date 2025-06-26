"""Photovoltaic farm data deleting tool

Allow to delete specific entries in the managed tables.

The only mandatory argument is the path to a JSON configuration file.
The environment variable OCSGE_PV_RESOURCE_DIR describes the path to
<repo>/src/ocsge_pv/resources or a copy of this directory. If empty or
unset, /app/src/ocsge_pv/resources will be used instead.
See cli_arg_parser for optionnal arguments.
Documentation for the configuration file is provided:
    * annotated schema:
        src/ocsge_pv/resources/delete_data_config.schema.json
    * example: tests/fixture/delete_data_config.ok_full.json

This file contains the following functions :
    * cli_arg_parser - parse CLI arguments
    * load_configuration - return validated configuration from file
    * add_ids_from_cli - add ids from CLI arguments to configuration
    * main - main function of the script
"""

import argparse
import json
import logging
import os
import re
import traceback
from copy import deepcopy
from pathlib import Path

import jsonschema
import psycopg
from psycopg import sql

NAME = "delete_data"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s(%(funcName)s) %(levelname)s: %(message)s",
)
logging.captureWarnings(True)
logger = logging.getLogger(NAME)


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
        description=("Deletes photovoltaic data objects from database"),
    )
    parser.add_argument(
        "path", type=Path, help="the path of the configuration file for %(prog)s"
    )
    parser.add_argument("--detections", help="Comma separated list of detections' ids")
    parser.add_argument(
        "--declarations", help="Comma separated list of declarations' ids"
    )
    parser.add_argument(
        "--pairs",
        help="Comma separated list of id pairs. Each pair has the form '<detection_id>-<declaration_id>'",
    )
    parser.add_argument(
        "-v", "--verbose", dest="verbose", action="store_true", help="output more logs"
    )
    return parser.parse_args()


def load_configuration(path: Path) -> dict:
    """Returns validated configuration from file

    Args:
        path (str): path to the configuration file

    Raises:
        jonschema.ValidationError: The configuration file does not
            match the validation schema

    Returns:
        Dict: the configuration object translated from the input file
    """
    try:
        resource_dir = os.environ.get("OCSGE_PV_RESOURCE_DIR")
        if resource_dir is None or resource_dir.strip() == "":
            resource_dir = "/app/src/ocsge_pv/resources"
        validation_schema_path = Path(resource_dir, "delete_data_config.schema.json")
        with open(path, encoding="utf-8") as config_file:
            config_str = config_file.read()
        source_configuration = json.loads(config_str)
        with open(validation_schema_path, encoding="utf-8") as schema_file:
            schema_str = schema_file.read()
        schema = json.loads(schema_str)
        jsonschema.validate(source_configuration, schema)
        modified_configuration = {}
        modified_configuration["main_database"] = deepcopy(
            source_configuration["main_database"]
        )
        modified_configuration["main_database"]["_pg_string"] = (
            "host="
            + modified_configuration["main_database"]["host"]
            + " port="
            + str(modified_configuration["main_database"]["port"])
            + " dbname="
            + modified_configuration["main_database"]["name"]
            + " user="
            + modified_configuration["main_database"]["user"]
            + " password="
            + modified_configuration["main_database"]["password"]
        )
        modified_configuration["to_delete"] = {
            "declarations": [],
            "detections": [],
            "pairs": [],
        }
        if (
            "to_delete" in source_configuration
            and "declarations" in source_configuration["to_delete"]
        ):
            modified_configuration["to_delete"]["declarations"] = deepcopy(
                source_configuration["to_delete"]["declarations"]
            )
            modified_configuration["to_delete"]["declarations"].sort()
        if (
            "to_delete" in source_configuration
            and "detections" in source_configuration["to_delete"]
        ):
            modified_configuration["to_delete"]["detections"] = deepcopy(
                source_configuration["to_delete"]["detections"]
            )
            modified_configuration["to_delete"]["detections"].sort()
        if (
            "to_delete" in source_configuration
            and "pairs" in source_configuration["to_delete"]
        ):
            modified_configuration["to_delete"]["pairs"] = deepcopy(
                source_configuration["to_delete"]["pairs"]
            )
        return modified_configuration
    except Exception as exc:
        logger.error(traceback.format_exc())
        raise exc


def get_ids_from_cli(arguments: argparse.Namespace) -> dict:
    """Get ids lists froom configuration object and CLI arguments

    Args:
        arguments (argparse.Namespace): result from cli_arg_parser()

    Raises:
        Exception: unidentified error

    Returns:
        dict: extracted ids, same format as in the configuration
            {
                "declarations": list[int],
                "detections": list[int],
                "pairs": [
                    {
                        "declaration": int,
                        "detection": int,
                    },
                    ...
                ],
            }
    """
    try:
        dec_list = []
        det_list = []
        pair_list = []
        if arguments.pairs is not None:
            for pair_str in arguments.pairs.split(","):
                pair_split = pair_str.split("-")
                pair_obj = {
                    "detection": int(pair_split[0]),
                    "declaration": int(pair_split[1]),
                }
                if pair_obj not in pair_list:
                    pair_list.append(pair_obj)
        if arguments.declarations is not None:
            for declaration_str in arguments.declarations.split(","):
                dec_list.append(int(declaration_str))
            dec_list.sort()
        if arguments.detections is not None:
            for detection_str in arguments.detections.split(","):
                det_list.append(int(detection_str))
            det_list.sort()
    except Exception as exc:
        logger.error(traceback.format_exc())
        raise exc
    extracted_dict = {
        "declarations": dec_list,
        "detections": det_list,
        "pairs": pair_list,
    }
    return deepcopy(extracted_dict)


# -- PROCESSING FUNCTIONS --


def combine_id_inventories(conf_inventory: dict, cli_inventory: dict) -> dict:
    """Combine inventories from configuration and CLI arguments.

    Args:
        conf_inventory (dict): ids inventory from configuration
        cli_inventory (dict): ids inventory from CLI arguments

    Returns:
        dict: combined deletions' ids inventory
    """
    logger.info(
        f"Deletions inventory from configuration file: {json.dumps(conf_inventory)}"
    )
    logger.info(f"deletions inventory from CLI arguments: {json.dumps(cli_inventory)}")
    dec_set = set(conf_inventory["declarations"])
    det_set = set(conf_inventory["detections"])
    pairs_list = deepcopy(conf_inventory["pairs"])
    temp_result = {
        "declarations": set(conf_inventory["declarations"]),
        "detections": set(conf_inventory["detections"]),
        "pairs": deepcopy(conf_inventory["pairs"]),
    }
    for item in cli_inventory["declarations"]:
        dec_set.add(item)
    for item in cli_inventory["detections"]:
        det_set.add(item)
    for item in cli_inventory["pairs"]:
        if item not in result["pairs"]:
            pairs_list.append(item)
    result = {
        "declarations": list(dec_set),
        "detections": list(det_set),
        "pairs": pairs_list,
    }
    result["declarations"].sort()
    result["detections"].sort()
    return result


def delete_declarations(db_info: dict, declarations: set) -> None:
    """Delete declarations and associated pairs

    Args:
        db_info (dict): database connection and table information
        declarations (set): target declarations ids list

    Raises:
        Exception: unidentified error, mostly in databse interactions
    """
    logger.info("Deleting declarations and associated pairs")
    deleted_declarations_count = 0
    deleted_pairs_count = 0
    with psycopg.connect(db_info["_pg_string"]) as conn:
        try:
            cur = conn.cursor()
            with conn.transaction():
                cur.execute(
                    sql.SQL(
                        "DELETE FROM {table} WHERE declaration_id IN ({id_list})"
                    ).format(
                        table=sql.Identifier(
                            db_info["schema"],
                            db_info["tables"]["links"],
                        ),
                        id_list=sql.SQL(", ").join(
                            sql.Placeholder() * len(declarations)
                        ),
                    ),
                    tuple(declarations),
                )
                message = cur.statusmessage
                count_match = re.match(r"DELETE +([0-9]+)", message)
                count_str = count_match.group(1)
                deleted_pairs_count = int(count_str)

                cur.execute(
                    sql.SQL(
                        "DELETE FROM {table} WHERE id_dossier IN ({id_list})"
                    ).format(
                        table=sql.Identifier(
                            db_info["schema"],
                            db_info["tables"]["declarations"],
                        ),
                        id_list=sql.SQL(", ").join(
                            sql.Placeholder() * len(declarations)
                        ),
                    ),
                    tuple(declarations),
                )
                message = cur.statusmessage
                count_match = re.match(r"DELETE +([0-9]+)", message)
                count_str = count_match.group(1)
                deleted_declarations_count = int(count_str)
        except Exception as exc:
            logger.error(traceback.format_exc())
            conn.rollback()
            raise exc
    logger.info(
        f"{deleted_declarations_count} declarations and {deleted_pairs_count} pairs deleted."
    )


def delete_detections(db_info: dict, detections: set) -> None:
    """Delete detections and associated pairs

    Args:
        db_info (dict): database connection and table information
        detections (set): target detections ids list

    Raises:
        Exception: unidentified error, mostly in databse interactions
    """
    logger.info("Deleting detections and associated pairs")
    deleted_detections_count = 0
    deleted_pairs_count = 0
    with psycopg.connect(db_info["_pg_string"]) as conn:
        try:
            cur = conn.cursor()
            with conn.transaction():
                cur.execute(
                    sql.SQL(
                        "DELETE FROM {table} WHERE detection_id IN ({id_list})"
                    ).format(
                        table=sql.Identifier(
                            db_info["schema"],
                            db_info["tables"]["links"],
                        ),
                        id_list=sql.SQL(", ").join(sql.Placeholder() * len(detections)),
                    ),
                    tuple(detections),
                )
                message = cur.statusmessage
                count_match = re.match(r"DELETE +([0-9]+)", message)
                count_str = count_match.group(1)
                deleted_pairs_count = int(count_str)

                cur.execute(
                    sql.SQL("DELETE FROM {table} WHERE id_v2 IN ({id_list})").format(
                        table=sql.Identifier(
                            db_info["schema"],
                            db_info["tables"]["detections"],
                        ),
                        id_list=sql.SQL(", ").join(sql.Placeholder() * len(detections)),
                    ),
                    tuple(detections),
                )
                message = cur.statusmessage
                count_match = re.match(r"DELETE +([0-9]+)", message)
                count_str = count_match.group(1)
                deleted_detections_count = int(count_str)
        except Exception as exc:
            logger.error(traceback.format_exc())
            conn.rollback()
            raise exc
    logger.info(
        f"{deleted_detections_count} detections and {deleted_pairs_count} pairs deleted."
    )


def delete_pairs(db_info: dict, pairs: list) -> None:
    """Delete pairs

    Args:
        db_info (dict): database connection and table information
        pairs (list): target id pairs list

    Raises:
        Exception: unidentified error, mostly in databse interactions
    """
    logger.info("Deleting explicit pairs")
    deleted_pairs_count = 0
    with psycopg.connect(db_info["_pg_string"]) as conn:
        try:
            cur = conn.cursor()
            with conn.transaction():
                for item in pairs:
                    cur.execute(
                        sql.SQL(
                            "DELETE FROM {table} WHERE declaration_id=%s AND detection_id=%s"
                        ).format(
                            table=sql.Identifier(
                                db_info["schema"],
                                db_info["tables"]["links"],
                            )
                        ),
                        (
                            item["declaration"],
                            item["detection"],
                        ),
                    )
                    message = cur.statusmessage
                    count_match = re.match(r"DELETE +([0-9]+)", message)
                    count_str = count_match.group(1)
                    deleted_pairs_count += int(count_str)
        except Exception as exc:
            logger.error(traceback.format_exc())
            conn.rollback()
            raise exc
    logger.info(f"{deleted_pairs_count} pairs deleted.")


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
        logger.info("Start of discrete data deletion.")
        cli_args = cli_arg_parser()
        log_level_description = "normal"
        if cli_args.verbose:
            logger.setLevel(logging.DEBUG)
            log_level_description = "verbose"
        logger.info(
            f"Logging level: '{logger.getEffectiveLevel()}' ({log_level_description})"
        )
        # Read configuration
        logger.info("Loading configuration...")
        configuration = load_configuration(cli_args.path)
        # Compute deletion ids lists
        # Note that deleting a declaration or a detection will also delete all related pairs
        logger.info("Computing initial deletions lists...")
        cli_id_dict = get_ids_from_cli(cli_args)
        inventory = combine_id_inventories(configuration["to_delete"], cli_id_dict)
        # Realise the deletions from the database
        logger.info("Deleting elements from database...")
        delete_declarations(configuration["main_database"], inventory["declarations"])
        delete_detections(configuration["main_database"], inventory["detections"])
        delete_pairs(configuration["main_database"], inventory["pairs"])
        # Finished
        logger.info("End of discrete data deletion.")
        return 0
    except Exception:
        logger.error(traceback.format_exc())
        return 1


# -- MAIN SCRIPT --


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
