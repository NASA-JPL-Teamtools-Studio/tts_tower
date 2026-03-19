from abc import ABC, abstractmethod
import pdb

from tts_tower.rule_results import RuleResults

# ===================================================================
# :: Checker Base Class
# ===================================================================
class CheckerBase(ABC):
    """
    Abstract Base Class for all Tower Checkers.

    This class provides the standard interface for defining flight rule logic.
    It handles the initialization of ``RuleResults`` objects based on the
    defined ``FR_IDS`` and manages the execution lifecycle of the check.

    These properties and methods must implement:
    * ``FR_IDS``
    * ``INPUTS``
    * ``_impl_init``
    * ``_impl_do_rulecheck``
    """

    @classmethod
    @property
    @abstractmethod
    def FR_IDS(cls):
        """
        List of tuples identifying all of the Rules checked by this checker.

        Each entry should be of the form: ("FOO-1234", 56789)

        Where:
        * "FOO-1234" is the  Rule ID
        * 56789 is the latest approved revision number

        Note that this is called FR_IDS because it was originally written with 
        Flight Rules in mind, but it is flexible enough to be any kind of rule.
        """
        raise NotImplementedError

    @classmethod
    @property
    @abstractmethod
    def INPUTS(cls):
        """
        List of tuples identifying all of the InputClients that this checker accepts.

        Must be in the order the inputs are accepted in __init__.

        Each entry should be of the form: ("input_name", bool)

        Where:
        * "input_name" is the name of the InputClient previously supplied to the InputManager
        * `True` means the checker **requires** the input
        * `False` means the checker will accept `None` if it's not available

        Init method sets up the ``RuleResults`` containers for every Flight Rule ID defined in ``FR_IDS``.
        If multiple rules are defined, ``self.rule`` becomes a dictionary mapping IDs to results.
        If a single rule is defined, ``self.rule`` is the direct ``RuleResults`` object.
        """
        raise NotImplementedError
    
    def __init__(self):
        self.rule_list = [RuleResults(*_) for _ in self.FR_IDS]
        if len(self.FR_IDS) > 1:
            self.rule = {_.id: _ for _ in self.rule_list}
        else:
            self.rule = self.rule_list[0]
            
        self._check_complete = False

    def do_rulecheck(self, *args):
        """
        Execute the rule checking logic.

        This wrapper ensures that the check is only run once. It delegates the actual
        initialization and checking logic to ``_impl_init`` and ``_impl_do_rulecheck``.

        :param args: Variable length argument list containing the inputs requested in ``INPUTS``.
        :raises Exception: If the checker has already completed its checks.
        """
        if self._check_complete:
            raise Exception(f'Checker "{self.NAME}" has already completed checks!')
        self._impl_init(*args)
        self._impl_do_rulecheck(*args)
        self._check_complete = True

    def flag_all_error(self, message):
        """
        Sets the status of all associated rules to 'ERROR' with a provided message.

        This is typically used when required inputs are missing or malformed, preventing
        the actual logic from running.

        :param message: The error message to attach to the rule dispositions.
        :type message: str
        """
        for rule in self.yield_rules():
            rule.set_status("ERROR")
            rule.add_dispo(message)
        self._check_complete = True


    @abstractmethod
    def _impl_init(self, *args):
        """
        Abstract method for unpacking and validating inputs.

        Implementations should assign the passed ``args`` to instance variables
        (e.g., ``self.evrs = args[0]``).

        :param args: The inputs supplied by the InputManager.
        """
        pass

    @abstractmethod
    def _impl_do_rulecheck(self, *args):
        """
        Abstract method containing the core rule checking logic.

        Implementations should analyze the inputs and update ``self.rule`` (or specific rules
        via ``self.get_rule``) with dispositions and status updates.

        :param args: The inputs supplied by the InputManager.
        """
        pass
        
    def yield_rules(self):
        """
        Generator yielding all RuleResult objects managed by this checker.

        :yield: RuleResults object.
        :rtype: Iterator[RuleResults]
        """
        for rule in self.rule_list:
            yield rule

    def get_rule(self, rule_id):
        """
        Retrieve a specific RuleResults object by its Flight Rule ID.

        :param rule_id: The unique identifier of the flight rule.
        :type rule_id: str
        :return: The requested RuleResults object.
        :rtype: RuleResults
        :raises ValueError: If the checker does not manage the specified rule ID.
        """
        if isinstance(self.rule, RuleResults):
            if self.rule.id == rule_id:
                return self.rule
        else:
            if rule_id in self.rule:
                return self.rule[rule_id]

        raise ValueError(f'Checker "{self.NAME}" has no rule with ID {rule_id}')
            
    def check_complete(self):
        """
        Check if the rule check has successfully completed.

        :return: True if checks are complete, False otherwise.
        :rtype: bool
        """
        return bool(self._check_complete)