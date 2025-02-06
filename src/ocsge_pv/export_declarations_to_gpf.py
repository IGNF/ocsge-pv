"""Photovoltaic farm declarations exporter to the Géoplateforme

Export photovoltaic farms declaration files to the Géoplateforme, 
using it's data delivery API. Also launches the integration from 
the delivery to a store database on he platform. 

This script's only argument is the path to a configuration file.
A model named 'import_declarations_config.ok.json' is available in 
the 'tests/fixture' folder.

This file contains the following functions :
    * main - main function of the script
"""