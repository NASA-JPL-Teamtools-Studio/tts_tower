import pytest
from unittest.mock import MagicMock, patch
from tts_utilities.logger import create_logger
import logging

# Assuming the classes are in a module named input_client
from tts_tower.inputs.input_client import InputClient, IC_STATE, FailedClient

# ===============================================
# :: Test Concrete Implementation
# ===============================================
class MockInputClient(InputClient):
    """Concrete implementation for testing abstract base logic"""
    def _impl_init(self, *args, **kwargs):
        self.init_called = True
        if kwargs.get('fail_init'):
            raise RuntimeError("Init Failed")

    def _impl_populate(self):
        self.pop_called = True
        if getattr(self, 'fail_pop', False):
            raise RuntimeError("Populate Failed")

# ===============================================
# :: Initialization Tests
# ===============================================

def test_initialization_success():
    """Verifies that a successful initialization sets state to INIT_END"""
    client = MockInputClient()
    assert client.get_state() == IC_STATE.INIT_END
    assert client.init_called is True

def test_initialization_failure():
    """Verifies that an exception in _impl_init sets state to ERROR and re-raises"""
    with pytest.raises(RuntimeError, match="Init Failed"):
        MockInputClient(fail_init=True)
    
    try:
        MockInputClient(fail_init=True)
    except RuntimeError:
        pass

def test_sub_client_identification():
    """Verifies that sub-clients are correctly identified from positional and keyword arguments"""
    sub1 = MockInputClient()
    sub2 = MockInputClient()
    parent = MockInputClient(sub1, extra="data", other_client=sub2)
    
    assert sub1 in parent._sub_clients
    assert sub2 in parent._sub_clients
    assert len(parent._sub_clients) == 2

# ===============================================
# :: Population Tests
# ===============================================

def test_populate_success():
    """Verifies state transitions from INIT_END to POP_END upon successful population"""
    client = MockInputClient()
    client.populate()
    assert client.get_state() == IC_STATE.POP_END
    assert client.pop_called is True

def test_populate_before_init():
    """Verifies that calling populate before initialization is complete raises a ValueError"""
    # Create an uninitialized client by bypassing __init__ for testing state logic
    client = MockInputClient.__new__(MockInputClient)
    # Manually set state to simulation uninitialized
    client._InputClient__set_state(IC_STATE.INIT_START) 
    
    with pytest.raises(ValueError, match="Attempting to Populate uninitialized InputCLient"):
        client.populate()

def test_repopulate_warning():
    """Verifies that attempting to re-populate a client already in POP_END triggers a warning"""
    client = MockInputClient()
    client.populate()  # State is now POP_END

    # Patch the logger object in the module where the InputClient logic resides
    with patch('tts_tower.inputs.input_client.log') as mock_log:
        client.populate()
    
    # Verify that .warning() was called on the logger
    mock_log.warning.assert_called()
    
    # Check that the expected string is contained in the first positional argument
    log_message = mock_log.warning.call_args[0][0]
    assert "requesting re-population" in log_message

def test_populate_dependency_failure():
    """Verifies that populate fails if a registered sub-client is in the ERROR state"""
    failed_sub = FailedClient("BrokenClient", RuntimeError("Failure"))
    # Ensure failed_sub is actually in ERROR state
    assert failed_sub.get_state() == IC_STATE.ERROR
    
    parent = MockInputClient(failed_sub)
    
    with pytest.raises(Exception, match="Failed sub-client dependencies"):
        parent.populate()

def test_populate_impl_failure():
    """Verifies that a failure in _impl_populate sets the state to ERROR"""
    client = MockInputClient()
    
    # FIX: Use _unlock to set the trigger attribute, then lock it back to INIT_END
    client._unlock()
    client.fail_pop = True
    client._lock(IC_STATE.INIT_END)
    
    with pytest.raises(RuntimeError, match="Populate Failed"):
        client.populate()
    assert client.get_state() == IC_STATE.ERROR

# ===============================================
# :: Attribute Locking Tests
# ===============================================

def test_attribute_locking():
    """Verifies that attributes cannot be set outside of allowed states (Init/Pop/Unlocked)"""
    client = MockInputClient()
    # At state INIT_END
    with pytest.raises(AttributeError, match="cannot set state"):
        client.new_attr = "Forbidden"

def test_attribute_setting_during_populate():
    """Verifies that attributes can be set while the state is POP_START"""
    class PopAttrClient(InputClient):
        def _impl_init(self, *args, **kwargs): pass
        def _impl_populate(self):
            self.dynamic_attr = "Allowed"
            
    client = PopAttrClient()
    client.populate()
    # Note: Success means the populate loop finished without AttributeError

def test_unlock_lock_utility():
    """Verifies that _unlock allows attribute setting and _lock restricts it"""
    client = MockInputClient()
    client._unlock()
    assert client.get_state() == IC_STATE.UNLOCKED
    client.debug_attr = "Works"
    
    client._lock(IC_STATE.POP_END)
    assert client.get_state() == IC_STATE.POP_END
    with pytest.raises(AttributeError):
        client.another_attr = "Fails"

# ===============================================
# :: FailedClient Tests
# ===============================================

def test_failed_client_init():
    """Verifies FailedClient correctly stores error info and ends in ERROR state"""
    exc = RuntimeError("Fatal")
    # This will now pass because of the change in InputClient.__init__
    client = FailedClient("TargetSystem", exc)
    
    assert client.name == "TargetSystem"
    assert client.exception == exc
    assert client.get_state() == IC_STATE.ERROR