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
from tts_tower.standalone_reports.standalone_report_base import StandAloneReportBase

log = create_logger(__name__)

# ===============================================
# :: Helper Class
# ===============================================
def log_standalone_report_exception(classname, e, tb):
    """
    Helper function to standardize logging for exceptions raised within a Stand Alone Report.

    Logs a warning with the exception type and arguments, and a condensed traceback.
    Also logs the full traceback to debug.

    :param classname: The class object or name of the Stand Alone Report where the exception occurred.
    :type classname: type or str
    :param e: The exception instance caught.
    :type e: Exception
    :param tb: A formatted traceback string identifying the location of the error.
    :type tb: str
    """
    e_short = f'{e.__class__} :: {". ".join([str(_) for _ in e.args])}'

    log.warning(
        f'Exception while running "{classname}" Stand Alone Report Client, please check rules Manually. See log for full traceback:\n{e_short}')
    log.warning(
        f'Abbreviated traceback:\n{tb}')

    log.debug(traceback.format_exc())


# ===============================================
# :: Manager
# ===============================================
class StandAloneReportManager:
    """
    Manager class responsible for instantiating, configuring, and executing a collection of Stand Alone Reports.

    This class handles the retrieval of required inputs for each stand_alone_report from the InputManager,
    executes the checks safely (catching exceptions per stand_alone_report), and aggregates the final results.

    Initializes the manager and instantiates the provided stand_alone_report classes.

    :param stand_alone_reports: A list of StandaloneReport subclasses to be managed.
    :type stand_alone_reports: list[Type[StandaloneReport]]
    """
    def __init__(self, stand_alone_reports):
        self.stand_alone_reports = [_() for _ in stand_alone_reports if _ != StandAloneReportBase]
        log.debug(f'Initialized {len(self.stand_alone_reports)} flight rule stand alone reports')

    def set_rule_status_enum(self, rule_status_enum_class):
        """
        Propagates the specific Rule Status Enum to all managed stand_alone_reports and their rules.

        This sets the initial status of all rules to ``PENDING``.

        :param rule_status_enum_class: The Enum class defining valid rule statuses (e.g., PASSED, VIOLATING).
        :type rule_status_enum_class: EnumMeta
        """
        for stand_alone_report in self.stand_alone_reports:
            for rule in stand_alone_report.rule_list:
                rule.rule_status_enum = rule_status_enum_class
                rule.set_status(rule_status_enum_class.PENDING)
                
    def generate_standalone_reports(self, icm, rule_result_container):
        """
        Executes the rule check logic for all managed stand_alone_reports.

        For each stand_alone_report:
        1. Identifies required inputs defined in ``stand_alone_report.INPUTS``.
        2. Retrieves those inputs from the InputManager (``icm``).
        3. Verifies inputs are present and not in a Failed state.
        4. Calls ``stand_alone_report.generate_report()`` with the retrieved inputs.
        5. Catches and logs any exceptions causing a stand_alone_report to fail, ensuring other stand_alone_reports proceed.

        :param icm: The populated InputManager instance containing data for checks.
        :type icm: InputManager
        """
        for stand_alone_report in self.stand_alone_reports:
            log.debug(f'Starting check for "{stand_alone_report.__class__}"')
            inputs = []
            input_error = False

            for input_name, input_required in stand_alone_report.INPUTS:
                if input_name == 'rule_result_container':
                    one_input = rule_result_container
                elif not icm.has_input(input_name):
                    if input_required:
                        log.warning(f'Could not run stand_alone_report "{stand_alone_report.__class__.__name__}" due to a Missing Input "{input_name}"')
                        input_error = True
                    one_input = None
                else:
                    one_input = icm.get(input_name)
                    if isinstance(one_input, FailedClient):
                        if input_required:
                            log.warning(f'Could not run stand_alone_report "{stand_alone_report.__class__.__name__}" due to Failed Input "{input_name}"')
                            input_error = True
                        one_input = None
                
                inputs.append(one_input)

            if input_error:
                stand_alone_report.flag_all_error(f'Error parsing required input for {stand_alone_report.__class__.__name__}, check manually')
            else: # Only runs if we don't break out of the previous "for" loop, a.k.a. we found all required inputs
                try:
                    stand_alone_report.generate_report(*inputs)
                except Exception as e:
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    tb = traceback.extract_tb(exc_tb)
                    last_call = tb[-1]  # Last item is the actual line that caused the error

                    file_name = last_call.filename
                    line_number = last_call.lineno
                    function_name = last_call.name
                    code_line = last_call.line

                    log_standalone_report_exception(stand_alone_report.__class__, e, f'{file_name}::{function_name}::{line_number}::{code_line}')
                    stand_alone_report.flag_all_error(f'Error running stand_alone_report {stand_alone_report.__class__.__name__}, check manually')
                else:
                    log.debug(f'Ran stand_alone_report {stand_alone_report.__class__.__name__}')
            
    def get_all_rule_results(self):
        """
        Aggregates the RuleResult objects from all stand_alone_reports that successfully completed.

        :return: A flat list of RuleResult objects from all complete stand_alone_reports.
        :rtype: list[RuleResults]
        """
        rule_results = []
        for stand_alone_report in [_ for _ in self.stand_alone_reports if _.check_complete()]:
            rule_results += stand_alone_report.rule_list
            
        return rule_results