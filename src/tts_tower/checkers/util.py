#Standard Library Imports
import importlib
import inspect

#Installed Dependency Imports
# None

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
from .checker_base import CheckerBase


log = create_logger(__name__)

# ===================================================================
# Utilities
# ===================================================================

def load_checkers(*source_dirs):
    """
    Dynamically imports and retrieves Checker classes from specified module paths.

    This function iterates through the provided source directory dot-paths, imports
    the corresponding modules, and inspects their members to gather all classes
    that inherit from ``CheckerBase``.

    :param source_dirs: Variable length argument list of Python dot-paths to modules (e.g., 'my_project.checkers').
    :type source_dirs: str
    :return: A list of discovered Checker class objects (not instances).
    :rtype: list
    """
    all_checkers = []
    for source_dir in source_dirs:
        # import the module containing checkers
        mod = importlib.import_module(source_dir)
        # Loop through each, weeding out everything but checkers derived from CheckerBase
        all_checkers += [_[1] for _ in inspect.getmembers(mod, lambda x: inspect.isclass(x) and issubclass(x, CheckerBase))]
    return all_checkers