#Standard Library Imports
import json
from enum import IntEnum
import pdb

#built in xml is only used below for writing, not reading
#so nosec flag is justified
# nosec B405 suppresses the import warning, but usage checks (B313-B319) remain active.
import xml.etree.ElementTree as ET  # nosec B405
from defusedxml import minidom

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
from tts_tower.report.sections.base import TowerSection
from tts_html_utils.core.components.misc import HorizontalBreak
from tts_tower.util import AccessEnum, auto, as_list

logger = create_logger(__name__)

# ===================================================================
# :: Enums/states
# ===================================================================
# class RULE_STATUS(IntEnum, AccessEnum):
#     """Defines all possible states of a Rule, in ascending order
#     The numerical order of these Enums intrinsically defines which states can "overwrite" others

#     A state with a larger number can overwrite a smaller one. E.g. if a Rule has state PENDING (0), it can
#     be overwritten with any other state.  But if it has state PASSED (3), it can only be overwritten by
#     FLAGGED (4), VIOLATING (5), or ERROR (6).  A rule that has state ERROR (6) will never change its state
#     """
#     DELETED = -1
#     PENDING = 0
#     INFO_ONLY = 1
#     NA = 2
#     PASSED = 3
#     FLAGGED = 4
#     VIOLATING = 5
#     ERROR = 6
#     MISMATCH = 7

#     def __init__(self, value):
#         sort_order = {
#             'DELETED': -1,
#             'NA': 0,
#             'PASSED': 1,
#             'PENDING': 2,
#             'INFO_ONLY': 3,
#             'FLAGGED': 4,
#             'VIOLATING': 5,
#             'ERROR': 6,
#             'MISMATCH': 7,
#         }
#         self._value_ = value
#         self.sort_order = sort_order[self.name]

class RULE_REVISION_SPECIAL(AccessEnum):
    """Special values for overriding TOWER's default rule revision behavior
    If a RuleResults has one of these values for its "revision" attribute, special handling (or no handling) is applied
    """
    USER_RULE = auto() # A user-defined rule, a.k.a not a Flight Rule
    IGNORE_REVISION = auto() # Do not perform revision checking for this rule


# ===================================================================
# :: Disposition Class
# ===================================================================
class RuleDisposition:
    """
    Container class for any disposition, with space for a message, status, type flag, and related object.

    This class serves as the atomic unit of feedback for a rule check, capturing
    what happened, the resulting status, and context about the object involved.

    :param message: Primary information-containing message for the disposition.
    :type message: str
    :param rule_status_enum: The Enum class defining valid rule statuses (e.g., RULE_STATUS).
    :type rule_status_enum: EnumType
    :param status: Rule status to be applied by this disposition. If None, the disposition is informational only.
    :type status: str or IntEnum, optional
    :param flag: A special identifier used by testing suites to differentiate specific dispositions programmatically.
    :type flag: int or str, optional
    :param target: A target object relevant to this disposition (e.g., a Command, Sequence, or File object).
    :type target: any, optional
    """
    DISPO_TYPE = "GENERIC"

    def __init__(self, message, rule_status_enum, status=None, flag=None, target=None):
        self.message = message
        self.status = rule_status_enum.get(status) if (status is not None) else status
        self.target = target
        self.flag = int(flag) if (flag is not None) else flag

    @property
    def context(self):
        """
        Retrieves the string representation of the target object context, if a target exists.
        
        :return: String context or None.
        :rtype: str or None
        """
        if self.target:
            return self.get_target_context()
        return None

    def get_target_context(self):
        """
        Helper method to extract context string from the target. 
        Intended to be overridden by specific disposition types.
        
        :return: String representation of target.
        :rtype: str
        """
        return str(self.target)  # Intended to be overridden by specific disposition types

    @property
    def text(self):
        """
        The full text representation of the disposition, combining context (if present) and message.
        
        :return: Formatted disposition text.
        :rtype: str
        """
        if self.context:
            return f'{self.context} - {self.message}'
        return self.message


class RuleCmdDisposition(RuleDisposition):
    """
    Disposition specific to Command objects. 
    Overrides context retrieval to use `repr_context()` of the command.
    """
    DISPO_TYPE = "CMD"

    def get_target_context(self):
        """
        Extracts context from a Command object.

        :return: The string representation of the command's context.
        :rtype: str
        """
        return self.target.repr_context()

class RuleSeqDisposition(RuleDisposition):
    """
    Disposition specific to Sequence objects.
    Overrides context retrieval to use the sequence `name`.
    """
    DISPO_TYPE = "SEQ"

    def get_target_context(self):
        """
        Extracts context from a Sequence object.

        :return: The name of the sequence.
        :rtype: str
        """
        return self.target.name

class RuleFileDisposition(RuleDisposition):
    """
    Disposition specific to File objects.
    Overrides context retrieval to use the file `onboard_name`.
    """
    DISPO_TYPE = "FILE_LOAD"

    def get_target_context(self):
        """
        Extracts context from a File object.

        :return: The onboard name of the file.
        :rtype: str
        """
        return self.target.onboard_name

# ===================================================================
# :: Rule Class
# ===================================================================
class RuleResults:
    """
    Primary storage and tracking class for Flight Rules.
    
    Keeps track of the Status (i.e. PASSED, VIOLATING, etc.) and all dispositions/errors generated while
    checking a particular Flight Rule.

    :param rule_id: Flight rule ID (e.g., "AVS-0002", "SYS-A-0010").
    :type rule_id: str
    :param revision: FR Source revision number. If this doesn't match the latest Approved revision for a rule,
                     dispositions will be rejected unless individually accepted by the user.
                     RULE_REVISION_SPECIAL enumerations provide some special parsing.
    :type revision: int or RULE_REVISION_SPECIAL
    :param user_title: An optional human-readable title for the rule to override the dictionary default.
    :type user_title: str, optional
    """
    def __init__(self, rule_id, revision, user_title=None):

        self.id = rule_id
        self.rev = revision
        self.user_title = user_title
        
        # Start every result as "PENDING"
        self.__status = None #this might break things since this isn't an enum value

        self._dispositions = []

        self._reports = {}
        
        self._errors = []

    @property
    def status(self):
        """
        The current aggregate status of the rule.
        
        :return: The current status enum member.
        :rtype: Enum member
        """
        return self.__status
        
    def set_status(self, new_status):
        """
        Set a new status for this rule. If the new status is 'lower' priority than an existing status, nothing happens.
        (e.g., ERROR overwrites PASSED, but PASSED does not overwrite ERROR).

        :param new_status: New status to attempt to set the rule to.
        :type new_status: RULE_STATUS or str
        :raises TypeError: If the new_status is not a valid Enum or string.
        """
        if not (isinstance(new_status, self.rule_status_enum) or isinstance(new_status, str)):
            raise TypeError(f'For consistency, all Rule Status values must be of IntEnum type "RULE_STATUS" or str, got {type(new_status)}')
        new_status_enum = self.rule_status_enum.get(new_status)

        # Only set the new status if it is a higher "value" than the existing status
        try:
            if self.__status is None:
                #To get us through the default to set it initially since now we do that
                #via checker_manager
                logger.debug(f'Setting Status for rule {self.id}: was "{str(self.__status)}" -> is "{str(new_status)}"')
                self.__status = new_status_enum # "increment" status                                
            elif new_status_enum > self.__status:
                logger.debug(f'Setting Status for rule {self.id}: was "{str(self.__status)}" -> is "{str(new_status)}"')
                self.__status = new_status_enum # "increment" status
            elif new_status_enum < self.__status:
                logger.debug(f'Trying to set Status for rule {self.id}, but skipping because new status is lower priority:  was "{str(self.__status)}" -> is "{str(new_status_enum)}"')
        except:
            pdb.set_trace()

    def is_pending(self):
        """
        Checks if the rule status is currently PENDING.

        :return: True if status is PENDING, False otherwise.
        :rtype: bool
        """
        return (self.status is self.rule_status_enum.PENDING)

    def _append_new_dispo(self, new_dispo):
        """
        Internal method to append a disposition and update rule status if the disposition carries a status.

        :param new_dispo: The disposition object to add.
        :type new_dispo: RuleDisposition
        """
        if new_dispo.status is not None:
            self.set_status(new_dispo.status)
        self._dispositions.append(new_dispo)

    # >> Shorthands
    def add_dispo(self, message):
        """
        Simply adds a generic disposition to this rule's running list without changing status.

        :param message: The text content of the disposition.
        :type message: str
        """
        new_dispo = RuleDisposition(message, self.rule_status_enum)
        self._append_new_dispo(new_dispo)

    def add_status_dispo(self, status, message):
        """
        Adds a generic disposition and attempts to update the rule status.

        :param status: The status to associate with this disposition (e.g., 'PASSED', 'VIOLATING').
        :type status: str or Enum
        :param message: The text content of the disposition.
        :type message: str
        """
        new_dispo = RuleDisposition(message, self.rule_status_enum, status=status)
        self._append_new_dispo(new_dispo)

    def add_cmd_dispo(self, cmd, message):
        """
        Add a disposition, automatically adding context about a specific FSW Command.

        :param cmd: The Command object related to the message.
        :type cmd: Command
        :param message: The text content of the disposition.
        :type message: str
        """
        new_dispo = RuleCmdDisposition(message, self.rule_status_enum, target=cmd)
        self._append_new_dispo(new_dispo)

    def add_cmd_status_dispo(self, cmd, status, message, flag=None):
        """
        Add a disposition w/ Cmd context and set the rule Status. Also adds an entry for test checking.

        :param cmd: The Command object related to the message.
        :type cmd: Command
        :param status: The status to associate with this disposition.
        :type status: str or Enum
        :param message: The text content of the disposition.
        :type message: str
        :param flag: Optional flag identifier for testing.
        :type flag: int or str, optional
        """
        new_dispo = RuleCmdDisposition(message, self.rule_status_enum, status=status, flag=flag, target=cmd)
        self._append_new_dispo(new_dispo)

    def add_seq_dispo(self, seq, message):
        """
        Add a disposition, automatically adding context about a specific Sequence.

        :param seq: The Sequence object related to the message.
        :type seq: Sequence
        :param message: The text content of the disposition.
        :type message: str
        """
        new_dispo = RuleSeqDisposition(message, self.rule_status_enum, target=seq)
        self._append_new_dispo(new_dispo)

    def add_seq_status_dispo(self, seq, status, message, flag=None):
        """
        Add a disposition w/ Seq context and set the rule Status. Also adds an entry for test checking.

        :param seq: The Sequence object related to the message.
        :type seq: Sequence
        :param status: The status to associate with this disposition.
        :type status: str or Enum
        :param message: The text content of the disposition.
        :type message: str
        :param flag: Optional flag identifier for testing.
        :type flag: int or str, optional
        """
        new_dispo = RuleSeqDisposition(message, self.rule_status_enum, status=status, flag=flag, target=seq)
        self._append_new_dispo(new_dispo)

    def add_file_dispo(self, file_load, message):
        """
        Add a disposition, automatically adding context about a specific File Load.

        :param file_load: The File object related to the message.
        :type file_load: File
        :param message: The text content of the disposition.
        :type message: str
        """
        new_dispo = RuleFileDisposition(message, self.rule_status_enum, target=file_load)
        self._append_new_dispo(new_dispo)

    def add_file_status_dispo(self, file_load, status, message, flag=None):
        """
        Add a disposition w/ File context and set the rule Status. Also adds an entry for test checking.

        :param file_load: The File object related to the message.
        :type file_load: File
        :param status: The status to associate with this disposition.
        :type status: str or Enum
        :param message: The text content of the disposition.
        :type message: str
        :param flag: Optional flag identifier for testing.
        :type flag: int or str, optional
        """
        new_dispo = RuleFileDisposition(message, self.rule_status_enum, status=status, flag=flag, target=file_load)
        self._append_new_dispo(new_dispo)

    @property
    def dispositions(self):
        """
        List of all dispositions associated with this rule.
        
        :return: List of RuleDisposition objects.
        :rtype: list[RuleDisposition]
        """
        return self._dispositions

    def get_all_dispos(self):
        """
        Returns a shallow copy of all dispositions.
        
        :return: Copy of the dispositions list.
        :rtype: list[RuleDisposition]
        """
        return [_ for _ in self.dispositions]

    def get_cmd_dispos(self):
        """
        Returns a list of all Command-type dispositions.
        
        :return: List of RuleCmdDisposition objects.
        :rtype: list[RuleCmdDisposition]
        """
        return [_ for _ in self.dispositions if _.DISPO_TYPE == 'CMD']

    def get_seq_dispos(self):
        """
        Returns a list of all Sequence-type dispositions.
        
        :return: List of RuleSeqDisposition objects.
        :rtype: list[RuleSeqDisposition]
        """
        return [_ for _ in self.dispositions if _.DISPO_TYPE == 'SEQ']

    def get_file_dispos(self):
        """
        Returns a list of all File-type dispositions.
        
        :return: List of RuleFileDisposition objects.
        :rtype: list[RuleFileDisposition]
        """
        return [_ for _ in self.dispositions if _.DISPO_TYPE == 'FILE_LOAD']

    def add_report(self, report_name, components, weight=0, section_class=None, append=False):
        """
        Attaches report components to this rule result, to be displayed in the generated HTML report.

        :param report_name: Name of the report section (e.g., "Execution").
        :type report_name: str
        :param components: List of (or single) Report Components (e.g., Plot, Table). See `tts-html-utils`.
        :type components: list or object
        :param weight: Sorting weight for the report tab (lower numbers appear first). Defaults to 0.
        :type weight: int, optional
        :param section_class: Custom TowerSection class to use for rendering. `deprecated`
        :type section_class: type, optional
        :param append: If True, appends components to an existing report name instead of warning about duplicates.
        :type append: bool, optional
        """
        if not isinstance(components, list): 
            components = [components]

        if report_name in self._reports:
            if append:
                #allows componenets to be None, False, [], 0, etc
                if components:
                    components = self._reports[report_name][0] + components
                else:
                    components = self._reports[report_name][0]
            else:
                logger.warning(f'Rule "{self.id}" already has report with name "{report_name}", skipping duplicate')
                return
        self._reports[report_name] = (components, weight, section_class)

    def get_reports(self):
        """
        Returns the dictionary of attached reports.

        :return: Dictionary mapping report names to component/metadata tuples.
        :rtype: dict
        """
        return self._reports
        
    def merge(self, other_results):
        """
        Merge another RuleResult for the same Flight Rule into this one.
        Picks the "highest" status of the 2, but merges all dispositions into one big list.

        :param other_results: The other RuleResults object to merge into this one.
        :type other_results: RuleResults
        :raises ValueError: If the Rule IDs or Revisions do not match (and are not ignored).
        """
        if other_results.id != self.id:
            raise ValueError(f'Provided Rule ID Does not match: mine - "{self.id}" , other - "{other_results.id}"')
        if (other_results.rev != self.rev) and not any([_ == RULE_REVISION_SPECIAL.IGNORE_REVISION for _ in [other_results.rev, self.rev]]):
            raise ValueError(f'Provided Rule Revision for {self.id} Does not match: mine - "{self.rev}" , other - "{other_results.rev}"')
            
        self.set_status(max(self.status, other_results.status)) # We define our self.rule_status_enum values such that higher values override lower ones, so max() works here
        for dispo in other_results.dispositions:
            self._append_new_dispo(dispo)

        for report_name, report_content in other_results.get_reports().items():
            self.add_report(report_name, report_content[0], weight=report_content[1], section_class=report_content[2])

    def to_fr_source_dict(self):
        """
        Converts the rule result into a dictionary compatible with the Flight Rule Source schema.

        :return: Dictionary with keys 'status', 'disposition', and 'rule_id'.
        :rtype: dict
        """
        return {
            'status': self.status.name,
            'disposition': '\n'.join([_.text for _ in self.dispositions]),
            'rule_id': self.id
        }
        
# ===================================================================
# :: Result Handling
# ===================================================================

def consolidate_rule_results(all_rule_results):
    """
    Groups a flat list of RuleResults by ID and consolidates them.

    If multiple results exist for the same Rule ID:
    1. It identifies the highest revision number used.
    2. It filters out any results with older revisions (logging a warning).
    3. It merges all remaining results into a single RuleResults object.

    :param all_rule_results: List of RuleResults objects from various checkers.
    :type all_rule_results: list[RuleResults]
    :return: A list of unique, consolidated RuleResults objects.
    :rtype: list[RuleResults]
    """
    all_rule_ids = list(set([_.id for _ in all_rule_results])) # Get a list of all unique Flight Rule ID's represented
    all_rule_ids.sort()
    
    consolidated_rule_results = []
    for rule_id in all_rule_ids:
        these_rule_results = [_ for _ in all_rule_results if _.id == rule_id]
        
        revisions = list(set([_.rev for _ in these_rule_results if (not isinstance(_.rev, RULE_REVISION_SPECIAL))]))
        if len(revisions) > 1:
            highest_rev = max(revisions)
            these_rule_results = [_ for _ in these_rule_results if (_.rev == highest_rev) or isinstance(_.rev, RULE_REVISION_SPECIAL)] # Select only the highest revision results
            logger.warning(f'Found different Checker Revisions in results for FR {rule_id}, only using highest Rev out of: {", ".join([str(_) for _ in revisions])}')
        
        while len(these_rule_results) > 1:
            to_merge = these_rule_results.pop()
            these_rule_results[0].merge(to_merge)
            
        consolidated_rule_results.append(these_rule_results[0])
        
    return consolidated_rule_results

def verify_rule_revisions(rule_results, fr_source_rules, revision_passthrough_list=None):
    """
    Verifies that the revision of the verified rules matches the latest revision in the source dictionary.

    :param rule_results: List of consolidated RuleResults objects.
    :type rule_results: list[RuleResults]
    :param fr_source_rules: The Rule Dictionary containing official rule definitions.
    :type fr_source_rules: dict
    :param revision_passthrough_list: List of Rule IDs to ignore version mismatches for. Defaults to None.
    :type revision_passthrough_list: list[str], optional
    :return: Three lists: verified_rr (passed), nonmatching_rr (ID not found), bad_version_rr (version mismatch).
    :rtype: tuple[list, list, list]
    """
    revision_passthrough_list = [_.lower() for _ in (revision_passthrough_list or [])]

    verified_rr = []
    nonmatching_rr = []
    bad_version_rr = []
    
    for rule_result in rule_results:
        if not isinstance(rule_result.rev, RULE_REVISION_SPECIAL):
            rule_store_entry = fr_source_rules.get(rule_result.id.upper()) # Returns "None" if this ID isn't present
            if rule_store_entry is None:
                logger.warning(f'Could not find rule ID "{rule_result.id}" in FR Source results, skipping reporting')
                nonmatching_rr.append(rule_result)
                continue

            if rule_result.rev != rule_store_entry.rev:
                if (rule_result.id.lower() in revision_passthrough_list) or ('all' in revision_passthrough_list):
                    logger.info(f'Bad Revision Match for rule ID "{rule_result.id}" : Script rev - {rule_result.rev} ; FR Source latest rev - {rule_store_entry.rev}, entry is in the passthrough list, so reporting anyway')
                else:
                    logger.warning(f'Bad Revision Match for rule ID "{rule_result.id}" : Script rev - {rule_result.rev} ; FR Source latest rev - {rule_store_entry.rev}')
                    rule_result.add_status_dispo('MISMATCH', f'Bad Revision Match for rule ID "{rule_result.id}" : Script rev - {rule_result.rev} ; FR Source latest rev - {rule_store_entry.rev}.')
                    bad_version_rr.append(rule_result)
                    continue
            
        verified_rr.append(rule_result)
        
    return verified_rr, nonmatching_rr, bad_version_rr

def rules_to_json(rule_results, outfile=None):
    """
    Serializes rule results to a JSON string and optionally writes to a file.

    :param rule_results: List of RuleResult objects.
    :type rule_results: list[RuleResults]
    :param outfile: Optional path to write the JSON output. If None, only returns string.
    :type outfile: str, optional
    :return: JSON string representation of the results.
    :rtype: str
    """
    rule_dicts = [_.to_fr_source_dict() for _ in rule_results]
    rule_json = json.dumps(rule_dicts)

    if outfile is not None:
        with open(outfile, 'w') as f:
            f.write(rule_json)

    return rule_json

def rules_to_xml(rule_results, outfile=None):
    """
    Serializes rule results to an XML string and optionally writes to a file.
    
    :param rule_results: List of RuleResult objects.
    :type rule_results: list[RuleResults]
    :param outfile: Optional path to write the XML output. If None, only returns string.
    :type outfile: str, optional
    :return: Pretty-printed XML string representation of the results.
    :rtype: str
    """
    root = ET.Element('rule_check_script_responses')

    for rule in rule_results:
        name = rule.id
        # FIX: Explicitly check for None because status 0 (PENDING) evaluates to False
        status = rule.status.name if rule.status is not None else "UNKNOWN" 
        dispo_objs = rule.dispositions

        rule_sub = ET.SubElement(root, 'rule_check_status', {'check_status': status, 'rule_id': name, 'rml_file': ''})
        dispo_sub = ET.SubElement(rule_sub, 'disposition')
        
        # Extracted .text from objects before joining to prevent TypeError
        dispo_text_list = [d.text for d in dispo_objs]
        dispo_sub.text = "<br>\n".join(dispo_text_list)

    # Use safe encoding with defusedxml (though mostly relevant for parsing, good practice to keep consistent)
    rough_string = ET.tostring(root, encoding='utf-8')
    
    # Use defusedxml.minidom to pretty print the output (resolves Bandit B318)
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    if outfile is not None:
        with open(outfile, 'w') as f:
            f.write(pretty_xml)

    return pretty_xml

def consolidate_rule_reports(rule_results, source_rules):
    """
    Aggregates individual reports attached to RuleResults into TowerSection objects.

    If multiple rules contribute to the same report name (e.g. "Power"), they are
    grouped together into a single Section.

    :param rule_results: List of RuleResult objects.
    :type rule_results: list[RuleResults]
    :param source_rules: The Rule Dictionary containing definitions for the rules.
    :type source_rules: dict
    :return: List of TowerSection objects ready for rendering.
    :rtype: list[TowerSection]
    """
    reports = {}
    for rule in rule_results:
        for report_name, report_contents in rule.get_reports().items():
            if report_name not in reports:
                reports[report_name] = [[], []]
            reports[report_name][0].append(rule)
            reports[report_name][1].append(report_contents)

    sections = []
    for report_name, report_info in reports.items():
        report_rules, report_contents = report_info
        report_contents.sort(key=lambda x: x[1]) # Sort by the "weight" field
        report_classes = list(set([_[2] for _ in report_contents if _[2] is not None]))
        if len(report_classes) == 0:
            report_class = TowerSection
        else:
            report_class = report_classes[0]

        components = as_list(report_contents[0][0]) + sum([[HorizontalBreak()]+as_list(_[0]) for _ in report_contents[1:] if _[0]], [])

        sections.append(report_class(report_name, components=components, contributors=report_rules, source_rules=source_rules))

    return sections