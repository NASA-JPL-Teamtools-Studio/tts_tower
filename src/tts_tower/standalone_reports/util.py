#Standard Library Imports
import importlib
import inspect

#Installed Dependency Imports
# None

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
from .standalone_report_base import StandAloneReportBase


log = create_logger(__name__)

# ===================================================================
# Utilities
# ===================================================================

def load_standalone_reports(*source_dirs):
    """
    Dynamically imports and retrieves standalone report classes from specified module paths.

    This function iterates through the provided source directory dot-paths, imports
    the corresponding modules, and inspects their members to gather all classes
    that inherit from ``StandAloneReportBase``.

    :param source_dirs: Variable length argument list of Python dot-paths to modules (e.g., 'my_project.checkers').
    :type source_dirs: str
    :return: A list of discovered standalone report class objects (not instances).
    :rtype: list
    """
    all_stand_alone_reports = []
    for source_dir in source_dirs:
        # import the module containing checkers
        mod = importlib.import_module(source_dir)
        # Loop through each, weeding out everything but checkers derived from CheckerBase
        all_stand_alone_reports += [_[1] for _ in inspect.getmembers(mod, lambda x: inspect.isclass(x) and issubclass(x, StandAloneReportBase))]
    return all_stand_alone_reports