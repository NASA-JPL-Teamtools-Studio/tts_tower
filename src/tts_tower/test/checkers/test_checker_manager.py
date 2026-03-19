import unittest
from unittest.mock import MagicMock, patch
import sys

# --- STEP 1: Define Concrete Stubs ---
# This avoids the "Cannot spec a Mock object" error and fixes identity checks.
class StubFailedClient: pass
class StubCheckerBase: pass

# --- STEP 2: Mock the modules BEFORE importing Manager ---
with patch.dict(sys.modules, {
    'tts_utilities.logger': MagicMock(),
    'tts_tower.inputs.input_client': MagicMock(),
    'tts_tower.checkers.checker_base': MagicMock()
}):
    # Import the components under test
    from tts_tower.checkers.checker_manager import CheckerManager
    # Overwrite the imported names with our stubs for reliable testing
    import tts_tower.checkers.checker_manager as cm
    cm.FailedClient = StubFailedClient
    cm.CheckerBase = StubCheckerBase

class TestCheckerManager(unittest.TestCase):

    def setUp(self):
        # Setup Mock Rule
        self.mock_rule = MagicMock()
        
        # Define a fake Checker class that inherits from nothing (to avoid mock bloat)
        class MockChecker:
            def __init__(self):
                self.rule_list = []
                self.INPUTS = []
                self.do_rulecheck = MagicMock()
                self.flag_all_error = MagicMock()
                self.check_complete = MagicMock(return_value=True)
            
            def set_rule_status_enum(self, val): pass

        self.MockCheckerClass = MockChecker
        self.mock_icm = MagicMock()

    def test_init_filters_checker_base(self):
        """Ensure CheckerBase class itself is filtered out."""
        # We pass the Stub class and our Mock class
        checkers = [self.MockCheckerClass, StubCheckerBase]
        manager = CheckerManager(checkers)
        
        # Only the MockCheckerClass should have been instantiated
        self.assertEqual(len(manager.checkers), 1)
        self.assertIsInstance(manager.checkers[0], self.MockCheckerClass)

    def test_set_rule_status_enum(self):
        """Verify that rules are updated with the provided enum class."""
        manager = CheckerManager([self.MockCheckerClass])
        checker = manager.checkers[0]
        checker.rule_list = [MagicMock()]
        
        mock_enum = MagicMock()
        mock_enum.PENDING = "PENDING"
        
        manager.set_rule_status_enum(mock_enum)
        
        self.assertEqual(checker.rule_list[0].rule_status_enum, mock_enum)
        checker.rule_list[0].set_status.assert_called_with("PENDING")

    def test_do_all_checks_success(self):
        """Test successful execution with valid inputs."""
        manager = CheckerManager([self.MockCheckerClass])
        checker = manager.checkers[0]
        checker.INPUTS = [('in1', True)]
        
        self.mock_icm.has_input.return_value = True
        self.mock_icm.get.return_value = "data"

        manager.do_all_checks(self.mock_icm)
        checker.do_rulecheck.assert_called_once_with("data")

    def test_do_all_checks_failed_client(self):
        """Test that a FailedClient instance triggers an error."""
        manager = CheckerManager([self.MockCheckerClass])
        checker = manager.checkers[0]
        checker.INPUTS = [('in1', True)]

        self.mock_icm.has_input.return_value = True
        # Use our stub class instance
        self.mock_icm.get.return_value = StubFailedClient()

        manager.do_all_checks(self.mock_icm)
        
        checker.flag_all_error.assert_called()
        checker.do_rulecheck.assert_not_called()

    @patch('tts_tower.checkers.checker_manager.log_checker_exception')
    def test_do_all_checks_exception_handling(self, mock_log_ex):
        """Test that crashes in do_rulecheck are caught."""
        manager = CheckerManager([self.MockCheckerClass])
        checker = manager.checkers[0]
        checker.INPUTS = [] # No inputs needed
        
        checker.do_rulecheck.side_effect = Exception("Boom")

        manager.do_all_checks(self.mock_icm)
        
        mock_log_ex.assert_called_once()
        checker.flag_all_error.assert_called()

    def test_get_all_rule_results(self):
        """Verify results collection logic."""
        manager = CheckerManager([self.MockCheckerClass])
        checker = manager.checkers[0]
        checker.rule_list = ["result1"]
        checker.check_complete.return_value = True
        
        results = manager.get_all_rule_results()
        self.assertIn("result1", results)

if __name__ == '__main__':
    unittest.main()