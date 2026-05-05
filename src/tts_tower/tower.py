from abc import ABC, abstractmethod
from datetime import datetime
import pdb

from tts_tower.rule_results import RuleResults
from tts_html_utils.core.compiler import HtmlCompiler
from tts_html_utils.core.components.text import H1
from tts_html_utils.core.components.misc import Div, Link, LineBreak
from tts_html_utils.core.components.structure import PaneContainer
from tts_tower.data_containers.rule_results import RuleResultContainer, DispositionContainer
from tts_tower.data_containers.tower_key import TowerKeyContainer
from tts_tower.inputs.input_client import FailedClient
from tts_tower.inputs.input_manager import InputManager
from tts_tower import util
from tts_tower.checkers.util import load_checkers
from tts_tower.checkers.checker_manager import CheckerManager
from tts_tower.rule_results import (
    consolidate_rule_results,
    verify_rule_revisions,
    consolidate_rule_reports,
)
from tts_data_utils.core.generic import GenericContainer
from tts_utilities.logger import create_logger

logger = create_logger(__name__)

class Tower(ABC):
    """
    Abstract Base Class acting as the primary orchestrator for the Tower rule-checking process.

    This class manages the lifecycle of a rule check run, including:
    1. Registering and initializing Input Clients.
    2. Registering and loading Checker modules.
    3. Executing checks via the CheckerManager.
    4. Consolidating and verifying results against a Rule Dictionary.
    5. Generating standardized HTML reports.

    Subclasses must define the specific Rule enums (`RULE_MATURITY`, `RULE_STATUS`, `RULE_CRITICALITY`)
    and implement the `build_rule_metadata` method.
    """
    RULE_MATURITY =  None
    RULE_STATUS = None
    RULE_CRITICALITY = None
    RUN_INFO_ORDER = []

    def __init__(self):
        """
        Initializes the Tower instance with empty lists for input clients and checkers.
        """
        self.input_clients = []
        self.checkers = []

    def add_input_client(self, name, cls, args, kwargs={}):
        """
        Registers an InputClient definition to be initialized during the run setup.

        :param name: Unique identifier for the input client.
        :type name: str
        :param cls: The InputClient class (not an instance) to be instantiated.
        :type cls: Type[InputClient]
        :param args: List of positional arguments to pass to the client's ``__init__``.
        :type args: list
        :param kwargs: Dictionary of keyword arguments to pass to the client's ``__init__``.
        :type kwargs: dict, optional
        """
        self.input_clients.append((name, cls, args, kwargs))

    def add_checker(self, checker):
        """
        Registers a source module path containing checkers to be loaded.

        :param checker: Python dot-path to the module containing CheckerBase implementations (e.g., 'my_project.checkers.sys_checkers').
        :type checker: str
        """
        self.checkers.append(checker)
        
    def write_reports(self, html_fname, html_report_name):
        """
        Compiles and writes the HTML summary report to a file.

        This method aggregates verified rule results, pending rules, and custom report components
        into a structured HTML document using ``HtmlCompiler``.

        :param html_fname: The file path where the HTML report will be written.
        :type html_fname: str
        :param html_report_name: The display title used within the report header.
        :type html_report_name: str
        """
        raw_data = []
        subcontainers = []
        report_components = {}
        rules_subscribed_to_report = {}
        verified_reports = consolidate_rule_reports(self.verified_rr, self.rules_role_manual)

        for rr in self.verified_rr + self.nonmatching_rr + self.bad_version_rr:
            if len(rr._reports):
                children = []
                for report_name, report_contents in rr._reports.items():
                    children.append(Link(report_name, href=f"#"+report_name.lower().replace(' ','-')))
                    children.append(LineBreak())
                    if report_name not in report_components.keys():
                        report_components[report_name] = Div()
                        rules_subscribed_to_report[report_name] = []

                    for child in report_contents[0]:
                        report_components[report_name].add_child(child)
                    rules_subscribed_to_report[report_name].append(rr.id)

                #leave out the last line break
                report_links = Div(children=children[:-1])
                report_links = report_links.render()
            else:
                report_links = 'None'
                            
            row = {
                'Rule ID': rr.id,
                'Criticality': self.rules_role_manual[rr.id].crit if rr.id in self.rules_role_manual else 'User',
                'Title': rr.user_title if rr.user_title is not None else self.rules_role_manual[rr.id].title,
                'Maturity': self.rules_role_manual[rr.id].maturity if rr.id in self.rules_role_manual else 'NA',
                'Status': rr._RuleResults__status.name,
                'Reports': report_links
            }
            disposition_rows_this_rule = []
            for d in rr._dispositions:
                disposition_row = {
                    'message': d.message,
                    'status': d.status.name if hasattr(d.status, 'name') else 'UNKNOWN',
                    'target': d.target,
                    'flag': d.flag
                }
                disposition_rows_this_rule.append(disposition_row)

            #TO DO: make a Datacontainer for this and wrap disposition_rows_this_rule in it
            subcontainers.append({
                'Dictionary Metadata': self.build_rule_metadata(self.rules_role_manual[rr.id] if rr.id in self.rules_role_manual else None),
                'All Dispositions': DispositionContainer(disposition_rows_this_rule)
                })
            raw_data.append(row)

        rule_ids_with_implementation = set([x['Rule ID'] for x in raw_data])
        for k, v in self.rules_role_manual.items():
            if k in rule_ids_with_implementation: continue
            row = {
                'Rule ID': k,
                'Criticality': v.crit,
                'Title': v.title,
                'Maturity': v.maturity,
                'Status': 'Pending',
                'Reports': 'None'
            }

            subcontainers.append({
                'Dictionary Metadata': self.build_rule_metadata(v), 
                'All Dispositions': DispositionContainer()
                })
            raw_data.append(row)

        #TO DO: This way of sorting is a cludge, but I need it to get over the hump. I will fix it
        #when rearchitecting this part of Tower core, so stay tuned. See ticket #23 (TO DO: export issue from JPL internal GH)
        maturity_order = {rm.name: rm.sort_order for rm in self.RULE_MATURITY}
        status_order = {rs.name: rs.sort_order for rs in self.RULE_STATUS}

        rule_results = RuleResultContainer(raw_data=raw_data, subcontainers=subcontainers)
        for rr in rule_results: 
            if rr['Criticality'] == 'DELETED': rr['Status'] = 'DELETED'
            if rr['Criticality'] == 'I': rr['Status'] = 'INFO_ONLY'

        rule_results = rule_results.sort(by='Rule ID')
        rule_results = rule_results.sort(lam=lambda x: status_order.get(x['Status'].upper().replace(' ', '_'), -1), reverse=True)
        rule_results = rule_results.sort(lam=lambda x: maturity_order.get(x['Maturity'].upper().replace(' ', '_'), -1), reverse=True)


        #hack to get us over the hump and put DELETED at the end without having to change upstream code
        # not_deleted = rule_results.ne('Maturity', 'DELETED')
        # deleted = rule_results.eq('Maturity', 'DELETED')
        # rule_results = not_deleted + deleted
        
        criticality_key = TowerKeyContainer()
        maturity_key = TowerKeyContainer()
        status_key = TowerKeyContainer()
        
        criticality_key.from_enum(self.RULE_CRITICALITY, 'Criticality')
        maturity_key.from_enum(self.RULE_MATURITY, 'Maturity')
        status_key.from_enum(self.RULE_STATUS, 'Status')
        
        ats_report = HtmlCompiler(html_report_name)
        ats_report.add_body_component(H1(html_report_name))
        pane_container = PaneContainer()

        keys = Div([
            criticality_key.power_table(style={'width': '31%', 'margin': '1%', 'float': 'left'}),
            maturity_key.power_table(style={'width': '31%', 'margin': '1%', 'float': 'left'}),
            status_key.power_table(style={'width': '31%', 'margin': '1%', 'float': 'left'})
            ])

        pane_container.add_pane([
            rule_results.power_table(id='rule-results-table', add_filters='local', add_sorting='local')
            ], 'Rule Results')
        pane_container.add_pane(keys, 'Rule Result Keys')
        for report_component_name, report_component in report_components.items():
            rules_this_report = rule_results.isin('Rule ID', rules_subscribed_to_report[report_component_name])
            rule_table_this_report = rules_this_report.power_table(f'Rules Contributing to {report_component_name}', id='rule-results-table')
            pane_container.add_pane([rule_table_this_report,# add_filters='local', add_sorting='local'),
                                    report_component], report_component_name)

        raw_data = [{'': k, ' ': self.run_info.get(k, 'UNKNOWN')} for k in self.RUN_INFO_ORDER]
        raw_data += [{'': k, ' ': self.run_info.get(k, 'UNKNOWN')} for k in self.run_info.keys() if k not in self.RUN_INFO_ORDER]
        pane_container.add_pane(GenericContainer(raw_data=raw_data).power_table(), 'Run Info')
        ats_report.add_body_component(pane_container)
        ats_report.render_to_file(html_fname)

    @abstractmethod
    def build_rule_metadata(self, dictionary_record):
        """
        Abstract method to construct the metadata dictionary for a specific rule.
        
        This dictionary is displayed in the expandable detail section of the HTML report.

        :param dictionary_record: The rule definition object from the dictionary (or None if User defined).
        :type dictionary_record: Any
        :return: A dictionary of key-value pairs to display as metadata.
        :rtype: dict
        """
        return

    def consolidate_and_verify(self):
        """
        Aggregates results from all checkers, handles deleted rules, and verifies version consistency.

        This method:
        1. Retrieves the official rule dictionary.
        2. Identifies rules marked 'DELETED' in the dictionary that weren't checked and adds a placeholder result.
        3. Consolidates multiple results for the same rule ID (merging dispositions/status).
        4. Verifies that the revision checked matches the revision in the dictionary.
        5. Populates ``self.verified_rr``, ``self.nonmatching_rr``, and ``self.bad_version_rr``.
        """
        rule_dictionary = self.icm.get('rule_dictionary')
        if isinstance(rule_dictionary, FailedClient):
            raise TypeError(f'Failed to initialize a rule dictionary client, cannot continue')
        self.rules_role_manual = rule_dictionary.rules

        all_rr = self.cm.get_all_rule_results()
        for source_rule_id, source_rule in rule_dictionary.rules.items():
            if len([rr for rr in all_rr if rr.id == source_rule_id]) == 0 and source_rule.row['Maturity'] == 'DELETED':
                result = RuleResults(source_rule_id, source_rule.rev, user_title=source_rule.title)
                result.rule_status_enum = self.RULE_STATUS
                result.set_status(self.RULE_STATUS.PENDING)
                result.add_status_dispo('DELETED', 'Rule has been deleted and no longer needs to be checked.')
                all_rr.append(result)

        self.consolidated_rr = consolidate_rule_results(all_rr)
        self.verified_rr, self.nonmatching_rr, self.bad_version_rr = verify_rule_revisions(self.consolidated_rr, self.rules_role_manual)

    def initialize_and_populate_clients(self):
        """
        Instantiates the InputManager context, registers all added clients, and executes population.
        
        This sets ``self.icm`` to the populated InputManager instance.
        """
        logger.info('Initialzing Clients')
        with InputManager() as icm:
            for ic in self.input_clients: icm.add_client(*ic)
        self.icm = icm        
        logger.info('Populating Clients')
        self.icm.populate_all_clients()


    def run(self):
        """
        Main execution entry point for the Tower process.

        1. Initializes run information (timestamps, input client metadata).
        2. Loads checker classes from registered modules.
        3. Initializes the CheckerManager and runs all checks against the input manager.
        4. Retrieves the rule dictionary and consolidates results.
        """
        self.run_info = {
            'Run Time': datetime.utcnow().strftime('%D-%H:%M:%S UTC'),
        }

        self.run_info = util.reverse_prio_dict_merge(self.run_info, self.icm.get_run_info())

        self.checkers = load_checkers(*self.checkers)
        logger.info('Running Checks')
        self.cm = CheckerManager(self.checkers)
        # self.cm.set_maturity_enum(self.RULE_MATURITY)
        self.cm.set_rule_status_enum(self.RULE_STATUS)
        # self.cm.set_criticality_enum(self.RULE_CRITICALITY)
        self.cm.do_all_checks(self.icm)

        rule_dictionary = self.icm.get('rule_dictionary')
        if isinstance(rule_dictionary, FailedClient):
            raise TypeError(f'Failed to initialize a rule dictionary client, cannot continue')
        self.rules_role_manual = rule_dictionary.rules

        self.consolidate_and_verify()
