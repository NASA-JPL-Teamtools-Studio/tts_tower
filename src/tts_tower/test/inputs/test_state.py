import pytest
from unittest.mock import MagicMock
import sys

# Do NOT mock tower.inputs.state, as that is what we are testing.
# We mock the base class module though to control inheritance if needed, 
# but usually better to let it run if possible.
# Here we ensure InputClient is available.

# Import the code under test
from tts_tower.inputs.state import StateClient
from tts_tower.inputs.input_client import IC_STATE

class TestStateClient:
    def test_init_success(self):
        """Verify StateClient initializes correctly with valid data."""
        state_name = "SystemMode"
        state_val = "Safe"
        
        client = StateClient(state_name, state_val)
        
        # Verify attributes set by _impl_init
        assert client.state_name == state_name
        assert client.state == state_val
        
        # Verify InputClient base class lifecycle state
        assert client.get_state() == IC_STATE.INIT_END

    def test_init_fails_on_none(self):
        """Verify _impl_init raises exception if state is None."""
        state_name = "BadState"
        
        # InputClient base __init__ re-raises exceptions from _impl_init
        with pytest.raises(Exception) as excinfo:
            StateClient(state_name, None)
        
        assert f"Got no good state value for {state_name}!" in str(excinfo.value)

    def test_run_info_format(self):
        """Verify _get_run_info returns the expected dictionary format."""
        client = StateClient("Voltage", 5.0)
        
        run_info = client._get_run_info()
        
        assert run_info == {"Voltage": 5.0}

    def test_populate_is_noop(self):
        """Verify _impl_populate does nothing but completes successfully."""
        client = StateClient("Flag", True)
        
        # Should not raise exception
        client.populate()
        
        # Should transition to POP_END state
        assert client.get_state() == IC_STATE.POP_END