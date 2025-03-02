import logging
import os

import yaml

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the package directory
PACKAGE_DIR = os.path.abspath(os.path.dirname(__file__))

# Create resource path as a global variable
RESOURCES_DIR = os.path.join(PACKAGE_DIR, "resources")

# Initialize global variables
with open(os.path.join(RESOURCES_DIR, "constants.yaml"), "r") as file:
    constants = yaml.safe_load(file)
