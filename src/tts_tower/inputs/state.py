#Standard Library Imports

#Installed Dependency Imports

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
from .input_client import InputClient

log = create_logger(__name__)

# ===================================================================
# :: Input Client
# ===================================================================

class StateClient(InputClient):
    """
    A simple InputClient implementation designed to hold a static state or configuration value.

    This client allows for the injection of known variables, environment flags, or 
    run-specific parameters into the InputManager context, making them available 
    to checkers and reports without requiring external data fetching.
    """
    # ===================================================================
    # :: InputClient Implementation
    # ===================================================================
    def _impl_init(self, state_name, state):
        """
        Initializes the client with a specific identifier and value.

        Validates that the provided state value is not None before storing it.

        :param state_name: The unique display name or key for this state variable.
        :type state_name: str
        :param state: The value of the state to be stored.
        :type state: Any
        :raises Exception: If the provided ``state`` is None.
        """
        # Not much to do here, just storing the state
        # But if the value is none, fail so we can detect it easily later
        if state is None:
            raise Exception(f'Got no good state value for {state_name}!')
            
        # If the state exists, just save it and move on, nothing else to do
        self.state_name = state_name
        self.state = state

    def _impl_populate(self):
        """
        Implementation of the abstract populate method.

        Since the state is provided strictly at initialization, no further 
        data fetching or population logic is required for this client.
        """
        pass # No implementation required

    def _get_run_info(self):
        """
        Generates metadata about this client for the run report.

        :return: A dictionary mapping the state name to its stored value.
        :rtype: dict
        """
        return {
            self.state_name: self.state
        }