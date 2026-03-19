#Standard Library Imports
import traceback
import pdb
import sys

#Installed Dependency Imports
# None

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
from tts_tower.inputs.input_client import FailedClient
from tts_tower.checkers.checker_base import CheckerBase

log = create_logger(__name__)

# ===============================================
# :: Helper Class
# ===============================================
def log_checker_exception(classname, e, tb):
    """
    Helper function to standardize logging for exceptions raised within a Checker.

    Logs a warning with the exception type and arguments, and a condensed traceback.
    Also logs the full traceback to debug.

    :param classname: The class object or name of the Checker where the exception occurred.
    :type classname: type or str
    :param e: The exception instance caught.
    :type e: Exception
    :param tb: A formatted traceback string identifying the location of the error.
    :type tb: str
    """
    e_short = f'{e.__class__} :: {". ".join([str(_) for _ in e.args])}'

    log.warning(
        f'Exception while running "{classname}" Checker Client, please check rules Manually. See log for full traceback:\n{e_short}')
    log.warning(
        f'Abbreviated traceback:\n{tb}')

    log.debug(traceback.format_exc())


# ===============================================
# :: Manager
# ===============================================
class CheckerManager:
    """
    Manager class responsible for instantiating, configuring, and executing a collection of Checkers.

    This class handles the retrieval of required inputs for each checker from the InputManager,
    executes the checks safely (catching exceptions per checker), and aggregates the final results.

    Initializes the manager and instantiates the provided checker classes.

    :param checkers: A list of CheckerBase subclasses to be managed.
    :type checkers: list[Type[CheckerBase]]
    """
    def __init__(self, checkers):
        self.checkers = [_() for _ in checkers if _ != CheckerBase]
        log.debug(f'Initialized {len(self.checkers)} flight rule checkers')

    def set_rule_status_enum(self, rule_status_enum_class):
        """
        Propagates the specific Rule Status Enum to all managed checkers and their rules.

        This sets the initial status of all rules to ``PENDING``.

        :param rule_status_enum_class: The Enum class defining valid rule statuses (e.g., PASSED, VIOLATING).
        :type rule_status_enum_class: EnumMeta
        """
        for checker in self.checkers:
            for rule in checker.rule_list:
                rule.rule_status_enum = rule_status_enum_class
                rule.set_status(rule_status_enum_class.PENDING)
                
    def do_all_checks(self, icm):
        """
        Executes the rule check logic for all managed checkers.

        For each checker:
        1. Identifies required inputs defined in ``checker.INPUTS``.
        2. Retrieves those inputs from the InputManager (``icm``).
        3. Verifies inputs are present and not in a Failed state.
        4. Calls ``checker.do_rulecheck()`` with the retrieved inputs.
        5. Catches and logs any exceptions causing a checker to fail, ensuring other checkers proceed.

        :param icm: The populated InputManager instance containing data for checks.
        :type icm: InputManager
        """
        for checker in self.checkers:
            log.debug(f'Starting check for "{checker.__class__}"')
            inputs = []
            input_error = False
            for input_name, input_required in checker.INPUTS:
                if not icm.has_input(input_name):
                    if input_required:
                        log.warning(f'Could not run checker "{checker.__class__.__name__}" due to a Missing Input "{input_name}"')
                        input_error = True
                    one_input = None
                else:
                    one_input = icm.get(input_name)
                    if isinstance(one_input, FailedClient):
                        if input_required:
                            log.warning(f'Could not run checker "{checker.__class__.__name__}" due to Failed Input "{input_name}"')
                            input_error = True
                        one_input = None
                
                inputs.append(one_input)

            if input_error:
                checker.flag_all_error(f'Error parsing required input for {checker.__class__.__name__}, check manually')
            else: # Only runs if we don't break out of the previous "for" loop, a.k.a. we found all required inputs
                try:
                    checker.do_rulecheck(*inputs)
                except Exception as e:
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    tb = traceback.extract_tb(exc_tb)
                    last_call = tb[-1]  # Last item is the actual line that caused the error

                    file_name = last_call.filename
                    line_number = last_call.lineno
                    function_name = last_call.name
                    code_line = last_call.line

                    log_checker_exception(checker.__class__, e, f'{file_name}::{function_name}::{line_number}::{code_line}')
                    checker.flag_all_error(f'Error running checker {checker.__class__.__name__}, check manually')
                else:
                    log.debug(f'Ran checker {checker.__class__.__name__}')
            
    def get_all_rule_results(self):
        """
        Aggregates the RuleResult objects from all checkers that successfully completed.

        :return: A flat list of RuleResult objects from all complete checkers.
        :rtype: list[RuleResults]
        """
        rule_results = []
        for checker in [_ for _ in self.checkers if _.check_complete()]:
            rule_results += checker.rule_list
            
        return rule_results