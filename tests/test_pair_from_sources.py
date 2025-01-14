"""Describes unit tests for the ocsge_pv.pair_from_sources module.

There is one test class for each tested functionnality.
See internal docstrings for more information.
Each variable prefixed by "m_" is a mock, or part of it.
"""

from unittest import TestCase, mock
from unittest.mock import MagicMock, call, mock_open

import pytest

import ocsge_pv.pair_from_sources as TM # tested module

# TODO Features to test :
# * read configuration
# * connect to database
# * read photovoltaic input tables (detections and declarations)
# * prepare geometry conversion (if necessary)
# * compute links list
# * write link in photovoltaic output table (link table) if it doesn't exist

