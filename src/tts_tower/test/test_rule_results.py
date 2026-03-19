import pytest
import sys
from unittest.mock import MagicMock, patch, mock_open
from enum import IntEnum, auto

# ===================================================================
# :: Setup Dependencies
# ===================================================================
# We strictly avoid sys.modules hacking for the module under test.
# We only patch external dependencies if absolutely necessary.

# Import the module under test
from tts_tower.rule_results import (
    RuleResults, 
    RuleDisposition, 
    RuleCmdDisposition, 
    RuleSeqDisposition, 
    RuleFileDisposition,
    RULE_REVISION_SPECIAL,
    consolidate_rule_results,
    verify_rule_revisions,
    consolidate_rule_reports,
    rules_to_json,
    rules_to_xml
)

# 3. Create a Mock Status Enum to inject into RuleResults
class MockAccessEnum(IntEnum):
    @classmethod
    def get(cls, x, strict=True):
        if isinstance(x, cls): return x
        try: return cls[x]
        except KeyError:
            try: return cls(x)
            except ValueError: return None

class MockStatus(MockAccessEnum):
    PENDING = 0
    PASSED = 1
    FLAGGED = 2
    VIOLATING = 3
    ERROR = 4
    MISMATCH = 7

# ===================================================================
# :: Fixtures
# ===================================================================

@pytest.fixture
def rule():
    """Returns a fresh RuleResults instance with the status enum injected."""
    r = RuleResults("TEST-001", 1, user_title="Test Rule")
    r.rule_status_enum = MockStatus
    # Manually initialize status like the CheckerManager would
    r.set_status(MockStatus.PENDING)
    return r

# ===================================================================
# :: Test Dispositions
# ===================================================================

class TestRuleDisposition:
    def test_generic_disposition_init(self):
        d = RuleDisposition("Message", MockStatus, status="FLAGGED", flag=1)
        assert d.message == "Message"
        assert d.status == MockStatus.FLAGGED
        assert d.flag == 1
        assert d.text == "Message"

    def test_cmd_disposition_context(self):
        mock_cmd = MagicMock()
        mock_cmd.repr_context.return_value = "CMD_ABC"
        
        d = RuleCmdDisposition("Bad Cmd", MockStatus, target=mock_cmd)
        assert d.target == mock_cmd
        assert d.context == "CMD_ABC"
        assert d.text == "CMD_ABC - Bad Cmd"

    def test_seq_disposition_context(self):
        mock_seq = MagicMock()
        mock_seq.name = "SEQ_123"
        
        d = RuleSeqDisposition("Bad Seq", MockStatus, target=mock_seq)
        assert d.context == "SEQ_123"
        assert d.text == "SEQ_123 - Bad Seq"

    def test_file_disposition_context(self):
        mock_file = MagicMock()
        mock_file.onboard_name = "file.dat"
        
        d = RuleFileDisposition("Bad File", MockStatus, target=mock_file)
        assert d.context == "file.dat"
        assert d.text == "file.dat - Bad File"

# ===================================================================
# :: Test RuleResults Logic
# ===================================================================

class TestRuleResults:
    def test_status_update_logic(self, rule):
        """Verify status only upgrades, never downgrades."""
        assert rule.status == MockStatus.PENDING
        
        # Upgrade to PASSED
        rule.set_status("PASSED")
        assert rule.status == MockStatus.PASSED
        
        # Upgrade to VIOLATING
        rule.set_status(MockStatus.VIOLATING)
        assert rule.status == MockStatus.VIOLATING
        
        # Attempt downgrade to PASSED (should fail silently/log debug)
        rule.set_status("PASSED")
        assert rule.status == MockStatus.VIOLATING

    def test_add_disposition_wrappers(self, rule):
        """Test the helper methods for adding specific dispositions."""
        # Generic
        rule.add_dispo("Generic Dispo")
        assert len(rule.dispositions) == 1
        assert isinstance(rule.dispositions[0], RuleDisposition)
        
        # Cmd
        mock_cmd = MagicMock()
        rule.add_cmd_dispo(mock_cmd, "Cmd Dispo")
        assert len(rule.dispositions) == 2
        assert isinstance(rule.dispositions[1], RuleCmdDisposition)
        assert rule.dispositions[1].target == mock_cmd

        # Status Dispo (should update rule status)
        rule.add_status_dispo("ERROR", "Major Fail")
        assert rule.status == MockStatus.ERROR
        assert rule.dispositions[-1].status == MockStatus.ERROR

    def test_report_management(self, rule):
        """Test adding and retrieving reports."""
        mock_component = MagicMock()
        
        rule.add_report("MyReport", mock_component, weight=10)
        reports = rule.get_reports()
        
        assert "MyReport" in reports
        # Format: (components_list, weight, section_class)
        assert reports["MyReport"][0] == [mock_component]
        assert reports["MyReport"][1] == 10

        # Test append logic
        mock_component_2 = MagicMock()
        rule.add_report("MyReport", mock_component_2, append=True)
        assert len(reports["MyReport"][0]) == 2

    def test_merge_success(self, rule):
        """Test merging two results for the same rule."""
        rule.set_status("PASSED")
        rule.add_dispo("D1")
        
        other = RuleResults("TEST-001", 1)
        other.rule_status_enum = MockStatus
        other.set_status("VIOLATING") # Higher status
        other.add_dispo("D2")
        other.add_report("Report2", MagicMock())

        rule.merge(other)

        # Status should take the max (VIOLATING > PASSED)
        assert rule.status == MockStatus.VIOLATING
        # Dispositions should contain both
        assert len(rule.dispositions) == 2
        assert rule.dispositions[0].message == "D1"
        assert rule.dispositions[1].message == "D2"
        # Reports should allow new ones
        assert "Report2" in rule.get_reports()

    def test_merge_mismatch_error(self, rule):
        """Test that merging mismatching IDs raises ValueError."""
        other = RuleResults("TEST-999", 1)
        with pytest.raises(ValueError) as exc:
            rule.merge(other)
        assert "Rule ID Does not match" in str(exc.value)

# ===================================================================
# :: Test Consolidate and Verify Functions
# ===================================================================

def test_consolidate_rule_results():
    """
    Test grouping by ID and selecting the highest revision.
    """
    r1_old = RuleResults("A", 1)
    r1_new = RuleResults("A", 2)
    r2 = RuleResults("B", 5)
    
    # Mock merging to ensure r1_new absorbs r1_old
    r1_new.merge = MagicMock()
    
    all_results = [r1_old, r1_new, r2]
    
    consolidated = consolidate_rule_results(all_results)
    
    assert len(consolidated) == 2
    ids = sorted([r.id for r in consolidated])
    assert ids == ["A", "B"]
    
    assert r1_new in consolidated
    assert r1_old not in consolidated

def test_verify_rule_revisions():
    """
    Test verifying script revisions against source dict revisions.
    """
    # Setup Results
    rr_good = RuleResults("GOOD", 5)
    rr_bad = RuleResults("BAD", 1) # Source is 2
    rr_missing = RuleResults("MISSING", 1) # Not in source
    
    results = [rr_good, rr_bad, rr_missing]
    
    # Setup Source Rules Dict (needs .rev attribute)
    mock_good = MagicMock(); mock_good.rev = 5
    mock_bad = MagicMock(); mock_bad.rev = 2
    
    source_rules = {
        "GOOD": mock_good,
        "BAD": mock_bad
    }
    
    # Setup Mocks to handle status setting inside the function
    for r in results:
        r.rule_status_enum = MockStatus
        r.set_status(MockStatus.PENDING)

    verified, nonmatching, bad_ver = verify_rule_revisions(results, source_rules)
    
    assert rr_good in verified
    assert rr_missing in nonmatching
    assert rr_bad in bad_ver
    
    # Check that the bad version got a disposition added
    assert len(rr_bad.dispositions) > 0
    assert rr_bad.dispositions[0].status == MockStatus.MISMATCH

# ===================================================================
# :: Test Export Functions
# ===================================================================

def test_rules_to_json(rule):
    rule.add_dispo("Test Dispo")
    results = [rule]
    
    # We mock open inside the function to avoid writing files
    with patch('builtins.open', mock_open()):
        json_output = rules_to_json(results, outfile="dummy.json")
    
    assert '"rule_id": "TEST-001"' in json_output
    assert '"status": "PENDING"' in json_output
    assert '"disposition": "Test Dispo"' in json_output

def test_rules_to_xml(rule):
    rule.add_dispo("Test Dispo")
    results = [rule]
    
    with patch('builtins.open', mock_open()):
        xml_output = rules_to_xml(results, outfile="dummy.xml")
    
    assert 'rule_id="TEST-001"' in xml_output
    assert 'check_status="PENDING"' in xml_output
    assert '<disposition>Test Dispo</disposition>' in xml_output

# ===================================================================
# :: Test Report Consolidation
# ===================================================================

def test_consolidate_rule_reports(rule):
    # Rule with a report
    rule.add_report("Execution", "Some Component")
    
    source_rules = {}
    
    sections = consolidate_rule_reports([rule], source_rules)
    
    assert len(sections) == 1
    section = sections[0]
    # Name matches report name
    assert section.name == "Execution"
    # Contributors include our rule
    assert rule in section._contributors