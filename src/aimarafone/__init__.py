import logging
import os

# Initialize logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Get the package directory
PACKAGE_DIR = os.path.abspath(os.path.dirname(__file__))

# Create resource path as a global variable
RESOURCES_DIR = os.path.join(PACKAGE_DIR, "resources")

# Initialize global variables
# global_variable = "some_value"
