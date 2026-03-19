import unittest
from unittest.mock import patch, MagicMock
import sys
import types

# Import the function to be tested
from tts_tower.checkers.util import load_checkers

class TestLoadCheckers(unittest.TestCase):

    def setUp(self):
        class MockCheckerBase:
            pass
        self.MockCheckerBase = MockCheckerBase

        class GoodChecker(MockCheckerBase):
            pass
        self.GoodChecker = GoodChecker

        class BadChecker:
            pass
        self.BadChecker = BadChecker

    def test_load_checkers_success(self):
        # 1. Patch CheckerBase FIRST.
        # This works because importlib is not yet patched, so it can find the real module.
        with patch('tts_tower.checkers.util.CheckerBase', self.MockCheckerBase):
            
            # 2. Patch importlib SECOND.
            # Now we can safely break the import system for the test.
            with patch('tts_tower.checkers.util.importlib.import_module') as mock_import_module:
                
                # Setup the mock return value
                fake_module = types.ModuleType("fake_module")
                fake_module.GoodChecker = self.GoodChecker
                fake_module.BadChecker = self.BadChecker
                mock_import_module.return_value = fake_module

                # 3. Run Code
                result = load_checkers('fake_path')

                # 4. Assert
                self.assertIn(self.GoodChecker, result)
                self.assertNotIn(self.BadChecker, result)

    def test_load_checkers_multiple_paths(self):
        with patch('tts_tower.checkers.util.CheckerBase', self.MockCheckerBase):
            with patch('tts_tower.checkers.util.importlib.import_module') as mock_import_module:
                
                mod1 = types.ModuleType("mod1")
                mod1.CheckerOne = type("CheckerOne", (self.MockCheckerBase,), {})
                
                mod2 = types.ModuleType("mod2")
                mod2.CheckerTwo = type("CheckerTwo", (self.MockCheckerBase,), {})

                # side_effect works now because 'patch' isn't secretly consuming the iterator
                mock_import_module.side_effect = [mod1, mod2]

                result = load_checkers('path/one', 'path/two')

                self.assertEqual(len(result), 2)

    def test_load_checkers_import_error(self):
        # No need to patch CheckerBase here, we just expect a crash
        with patch('tts_tower.checkers.util.importlib.import_module') as mock_import_module:
            mock_import_module.side_effect = ImportError("Module not found")

            with self.assertRaises(ImportError):
                load_checkers('invalid/path')

    def test_load_checkers_excludes_variables(self):
        with patch('tts_tower.checkers.util.CheckerBase', self.MockCheckerBase):
            with patch('tts_tower.checkers.util.importlib.import_module') as mock_import_module:
                
                fake_module = types.ModuleType("fake_module")
                fake_module.SomeString = "I am not a class"
                fake_module.SomeInstance = self.MockCheckerBase() 

                mock_import_module.return_value = fake_module

                result = load_checkers('fake_path')

                self.assertEqual(result, [])

if __name__ == '__main__':
    unittest.main()