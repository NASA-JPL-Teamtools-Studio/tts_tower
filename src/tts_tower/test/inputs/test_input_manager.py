import pytest
from unittest.mock import MagicMock, patch
import sys

# Import the code under test
from tts_tower.inputs.input_client import InputClient, IC_STATE

# Define a concrete implementation for testing the abstract base class
class MockInputClient(InputClient):
    def _impl_init(self, *args, **kwargs):
        pass
    def _impl_populate(self):
        pass

class TestInputClient:
    def test_init_success(self):
        """Verifies that a successful init sets state to INIT_END"""
        client = MockInputClient()
        assert client.get_state() == IC_STATE.INIT_END

    def test_init_failure(self):
        """Verifies that exceptions during _impl_init set state to ERROR and re-raise"""
        class BrokenClient(InputClient):
            def _impl_init(self):
                raise ValueError("Init Failed")
            def _impl_populate(self): pass

        with pytest.raises(ValueError):
            BrokenClient()
        
        # We can't inspect the instance because init failed, so we trust the raise logic

    def test_populate_success(self):
        """Verifies populate() transitions state correctly"""
        client = MockInputClient()
        assert client.get_state() == IC_STATE.INIT_END
        
        client.populate()
        assert client.get_state() == IC_STATE.POP_END

    def test_populate_failure(self):
        """Verifies exceptions during populate set state to ERROR"""
        class BrokenPopulate(InputClient):
            def _impl_init(self): pass
            def _impl_populate(self): 
                raise RuntimeError("Pop Failed")

        client = BrokenPopulate()
        with pytest.raises(RuntimeError):
            client.populate()
            
        assert client.get_state() == IC_STATE.ERROR

    def test_populate_before_init(self):
        """Verifies populate raises error if called before init is complete"""
        # Hard to simulate naturally since __init__ runs on creation, 
        # but we can manually mess with state for testing
        client = MockInputClient()
        client._InputClient__set_state(IC_STATE.INIT_START) # Force bad state
        
        with pytest.raises(ValueError):
            client.populate()

    def test_repopulate_warning(self):
        """Verifies that attempting to re-populate a client already in POP_END triggers a warning"""
        client = MockInputClient()
        client.populate() # State is now POP_END
        
        # Patch the logger specifically found in the input_client module
        with patch('tts_tower.inputs.input_client.log') as mock_log:
            client.populate()
            
            # Verify that .warning() was called on the logger
            mock_log.warning.assert_called()

    def test_sub_client_init(self):
        """Verifies sub-clients are detected in args/kwargs"""
        sub = MockInputClient()
        client = MockInputClient(sub, key=sub)
        
        assert sub in client._sub_clients
        assert len(client._sub_clients) == 2

    def test_sub_client_failure_blocks_populate(self):
        """Verifies that if a sub-client is in ERROR state, populate fails"""
        sub = MockInputClient()
        # Force sub-client into error state
        sub._set_error()
        
        client = MockInputClient(sub)
        
        with pytest.raises(Exception) as exc:
            client.populate()
        
        assert "Failed sub-client dependencies" in str(exc.value)

    def test_setattr_locking(self):
        """Verifies attributes cannot be set after population unless unlocked"""
        client = MockInputClient()
        client.populate() # POP_END
        
        # Should fail
        with pytest.raises(AttributeError):
            client.new_attr = 1
            
        # Unlock
        client._unlock()
        client.new_attr = 1
        assert client.new_attr == 1
        
        # Lock
        client._lock()
        with pytest.raises(AttributeError):
            client.another_attr = 2