"""Photovoltaic farm declarations importer

Import photovoltaic farms declaration files from the official 
declaration service API, and insert them into a database. 

This script's only argument is the path to a configuration file.
A model named 'import_declarations_config.ok.json' is available in 
the 'tests/fixture' folder.

This file contains the following functions :
    * main - main function of the script
"""