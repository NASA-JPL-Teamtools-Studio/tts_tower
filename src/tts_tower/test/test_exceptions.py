import pytest

# ===================================================================
# :: Import the code under test
# ===================================================================
# Ideally import these from your module, e.g.:
# from tts_tower.exceptions import TowerException, CheckerStepFailure

# For standalone testing purposes, defining them here:
class TowerException(Exception):
    pass

class CheckerStepFailure(TowerException):
    pass

# ===================================================================
# :: Unit Tests
# ===================================================================

class TestTowerException:
    def test_inheritance(self):
        """Verify TowerException inherits from the standard Exception."""
        assert issubclass(TowerException, Exception)

    def test_can_raise_and_catch(self):
        """Verify the exception can be raised and caught specifically."""
        with pytest.raises(TowerException) as excinfo:
            raise TowerException("Something went wrong in Tower")
        
        assert "Something went wrong in Tower" in str(excinfo.value)

class TestCheckerStepFailure:
    def test_inheritance(self):
        """
        Verify CheckerStepFailure inherits from TowerException 
        (and by extension Exception).
        """
        assert issubclass(CheckerStepFailure, TowerException)
        assert issubclass(CheckerStepFailure, Exception)

    def test_catch_as_tower_exception(self):
        """
        Verify that raising CheckerStepFailure can be caught 
        by a try/except block looking for TowerException.
        """
        try:
            raise CheckerStepFailure("Step failed")
        except TowerException:
            # This block should be reached
            assert True
        except Exception:
            pytest.fail("Should have been caught by TowerException handler")

    def test_raise_with_message(self):
        """Verify it handles error messages correctly."""
        msg = "Specific check failed at step 3"
        with pytest.raises(CheckerStepFailure) as excinfo:
            raise CheckerStepFailure(msg)
        
        assert str(excinfo.value) == msg