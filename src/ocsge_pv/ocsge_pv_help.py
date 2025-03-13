"""General help provider for the project's executables

Displays command line interface help message for all of the project
executables, then exits.

No argument is expected. Any given argument will be ignored.

This file contains the following functions :
    * main - main function of the script
"""

# -- IMPORTS --
# standard library
import sys

# package
from ocsge_pv.import_declarations import cli_arg_parser as import_declarations_cli
from ocsge_pv.geometrize_declarations import cli_arg_parser as geometrize_declarations_cli
from ocsge_pv.pair_from_sources import cli_arg_parser as pair_from_sources_cli

# -- MAIN FUNCTION --
def main() -> int:
    """Main routine, entrypoint for the program
    
    Returns:
        int: shell exit code of the execution
    """
    original_sys_argv = sys.argv
    try:
        sys.argv = ["./ocsge_pv_help.py", "--help"]
        print("-----------------------------")
        print("---- import_declarations ----\n")
        try:
            import_declarations_cli()
        except SystemExit:
            print("\n-----------------------------")
        print("-- geometrize_declarations --\n")
        try:
            geometrize_declarations_cli()
        except SystemExit:
            print("\n-----------------------------")
        print("----- pair_from_sources -----\n")
        try:
            pair_from_sources_cli()
        except SystemExit:
            print("")
        return 0
    finally:
        sys.argv = original_sys_argv

# -- MAIN SCRIPT --
if (__name__ == "__main__"):
    exit_code = main()
    sys.exit(exit_code)