import pytest
from unittest.mock import MagicMock, patch

# Import code under test
from tts_tower.checkers.checker_base import CheckerBase

# Mock RuleResults since it's instantiated inside CheckerBase.__init__
class MockRuleResults:
    def __init__(self, rule_id, rev):
        self.id = rule_id
        self.rev = rev
        self.set_status = MagicMock()
        self.add_dispo = MagicMock()

# ===================================================================
# :: Concrete Implementation for Testing
# ===================================================================

class ConcreteChecker(CheckerBase):
    NAME = "TestChecker"
    FR_IDS = [("RULE-1", 1), ("RULE-2", 2)]
    INPUTS = [("input1", True)]

    def _impl_init(self, *args):
        self.init_called = True
        self.init_args = args

    def _impl_do_rulecheck(self, *args):
        self.check_called = True
        self.check_args = args

class SingleRuleChecker(CheckerBase):
    NAME = "SingleChecker"
    FR_IDS = [("RULE-A", 1)]
    INPUTS = []
    
    def _impl_init(self, *args): pass
    def _impl_do_rulecheck(self, *args): pass

# ===================================================================
# :: Tests
# ===================================================================

# FIXED: Use 'new=' to replace the class entirely so isinstance works
@patch('tts_tower.checkers.checker_base.RuleResults', new=MockRuleResults)
class TestCheckerBase:

    def test_init_creates_rule_objects(self):
        """Verify __init__ creates RuleResult objects from FR_IDS."""
        checker = ConcreteChecker()
        
        # Should have 2 rules based on FR_IDS
        assert len(checker.rule_list) == 2
        assert checker.rule_list[0].id == "RULE-1"
        assert checker.rule_list[1].id == "RULE-2"
        
        # self.rule should be a dict when multiple rules exist
        assert isinstance(checker.rule, dict)
        assert checker.rule["RULE-1"] == checker.rule_list[0]

    def test_init_single_rule_behavior(self):
        """Verify self.rule is the object directly if only one FR_ID exists."""
        checker = SingleRuleChecker()
        
        assert len(checker.rule_list) == 1
        # self.rule should be the object itself, not a dict
        assert isinstance(checker.rule, MockRuleResults)
        assert checker.rule.id == "RULE-A"

    def test_do_rulecheck_flow(self):
        """Verify do_rulecheck calls impl methods and sets complete flag."""
        checker = ConcreteChecker()
        assert checker.check_complete() is False
        
        args = ("arg1", "arg2")
        checker.do_rulecheck(*args)
        
        assert checker.init_called is True
        assert checker.init_args == args
        assert checker.check_called is True
        assert checker.check_args == args
        assert checker.check_complete() is True

    def test_do_rulecheck_prevents_double_run(self):
        """Verify calling do_rulecheck twice raises Exception."""
        checker = ConcreteChecker()
        checker.do_rulecheck()
        
        with pytest.raises(Exception) as exc:
            checker.do_rulecheck()
        
        assert "has already completed checks" in str(exc.value)

    def test_flag_all_error(self):
        """Verify flag_all_error updates status/dispo for all rules."""
        checker = ConcreteChecker()
        msg = "Fatal Error"
        
        checker.flag_all_error(msg)
        
        assert checker.check_complete() is True
        
        for rule in checker.rule_list:
            rule.set_status.assert_called_with("ERROR")
            rule.add_dispo.assert_called_with(msg)

    def test_yield_rules(self):
        """Verify yield_rules iterates over all rules."""
        checker = ConcreteChecker()
        rules = list(checker.yield_rules())
        assert len(rules) == 2
        assert rules == checker.rule_list

    def test_get_rule_multi(self):
        """Verify retrieval by ID for multi-rule checker."""
        checker = ConcreteChecker()
        
        r1 = checker.get_rule("RULE-1")
        assert r1.id == "RULE-1"
        
        with pytest.raises(ValueError):
            checker.get_rule("BAD-ID")

    def test_get_rule_single(self):
        """Verify retrieval by ID for single-rule checker."""
        checker = SingleRuleChecker()
        
        # This works because we patched RuleResults with MockRuleResults class,
        # so isinstance(checker.rule, RuleResults) returns True.
        rA = checker.get_rule("RULE-A")
        assert rA.id == "RULE-A"
        
        with pytest.raises(ValueError):
            checker.get_rule("BAD-ID")