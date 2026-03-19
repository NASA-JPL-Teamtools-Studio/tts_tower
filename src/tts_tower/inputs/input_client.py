#Standard Library Imports
from abc import ABC, abstractmethod
from enum import IntEnum, auto
from copy import deepcopy
import pdb

#Installed Dependency Imports
# None

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
# None

log = create_logger(__name__)

# ===============================================
# :: State Enum
# ===============================================
class IC_STATE(IntEnum):
    """
    Enumeration defining the lifecycle states of an InputClient.

    Attributes:
        ERROR: Indicates an error occurred during initialization or population.
        INIT_START: Indicates initialization has started.
        INIT_END: Indicates initialization has completed successfully.
        POP_START: Indicates population has started.
        POP_END: Indicates population has completed successfully.
        UNLOCKED: Indicates the client is explicitly unlocked for attribute modification.
    """
    ERROR = auto()
    INIT_START = auto()
    INIT_END = auto()
    POP_START = auto()
    POP_END = auto()
    UNLOCKED = auto()

# ===============================================
# :: Base
# ===============================================
class InputClient(ABC):
    """Basic structure for Inputs to the Rulechecking process
    Defines a couple of interfaces used by the InputManager to structure input population and supply to checkers

    The init method sets the initial state to INIT_START, identifies any dependencies
    (other InputClients) passed in args or kwargs, calls the concrete implementation's
    _impl_init, and updates the state to INIT_END upon success.

    :param args: Positional arguments passed to _impl_init. Any InputClient instances are tracked as sub-clients.
    :param kwargs: Keyword arguments passed to _impl_init. Any InputClient values are tracked as sub-clients.
    """
    def __init__(self, *args, **kwargs):
        # Initialize state
        self.__set_state(IC_STATE.INIT_START)
        log.debug(f'Initializing {self.__class__}')

        self._sub_clients = [_ for _ in args if isinstance(_, InputClient)] + [_ for _ in kwargs.values() if isinstance(_, InputClient)]

        try:
            self._impl_init(*args, **kwargs)
            log.debug(f'Successfully initialized {self.__class__}')
            if self.get_state() != IC_STATE.ERROR:
                self.__set_state(IC_STATE.INIT_END)
        except Exception as e:
            # Manager will handle primary outbound logging, just debug here
            log.debug(f'Failed to initialize {self.__class__}')
            self.__set_state(IC_STATE.ERROR)
            raise e

    def populate(self):
        """To be called by InputManager. Takes no input, input should be managed and validated during Init
        
        This method transitions the state to POP_START, checks for failed sub-clients,
        calls the concrete _impl_populate method, and finally transitions to POP_END.
        """
        if self.get_state() == IC_STATE.ERROR:
            log.warning(f'InputClient {self.__class__} attempting to populate FailedClient')
            return
        if self.get_state() < IC_STATE.INIT_END:
            raise ValueError(f'Attempting to Populate uninitialized InputCLient {self.__class__}')
        if self.get_state() > IC_STATE.INIT_END:
            log.warning(f'InputClient {self.__class__} requesting re-population')

        self.__set_state(IC_STATE.POP_START)
        log.debug(f'Populating {self.__class__}')

        try:
            # Check for failed sub-clients first
            failed_clients = [_ for _ in self._sub_clients if _.get_state() == IC_STATE.ERROR]
            if any(failed_clients):
                raise Exception(
                    f'Failed sub-client dependencies: {", ".join([str(_.__class__) for _ in failed_clients])}')

            self._impl_populate()
            log.debug(f'Successfully populated {self.__class__}')
            self.__set_state(IC_STATE.POP_END)
        except Exception as e:
            # Manager will handle primary outbound logging, just debug here
            log.debug(f'Failed to populate {self.__class__}')
            self.__set_state(IC_STATE.ERROR)
            raise e

    @abstractmethod
    def _impl_init(self, *args, **kwargs):
        """To be implemented by inheritors. Should validate inputs and store them for efficient population later"""
        pass

    @abstractmethod
    def _impl_populate(self):
        """To be implemented by inheritors. Should validate environment, then do any actions to populate input data
        e.g. query data, process R/XMLs, etc.
        """
        pass

    def _get_run_info(self):
        """An opportunity to report any number of information fields in key-value format"""
        return {}

    def __setattr__(self, key, value):
        """
        Sets an attribute on the client instance with state-based locking.

        Attributes can only be modified when the client is in INIT_START, POP_START, or UNLOCKED states.

        :param key: The name of the attribute.
        :param value: The value to set.
        :raises AttributeError: If the client is in a locked state (e.g., INIT_END, POP_END).
        """
        if self.get_state() in [IC_STATE.INIT_START, IC_STATE.POP_START, IC_STATE.UNLOCKED]:
            super().__setattr__(key, value)
            return
        raise AttributeError(f'InputClient {self.__class__} is not Initializing or Populating ({self.get_state().name}), cannot set state')

    def __set_state(self, state):
        """
        Internal method to update the client's state.

        :param state: The new state (must be an IC_STATE enum).
        :raises TypeError: If state is not an instance of IC_STATE.
        """
        if not isinstance(state, IC_STATE):
            raise TypeError(f'InputClient state must be IC_STATE Enum, not {type(state)}')
        super().__setattr__('_InputClient__state', state)

    def get_state(self):
        """
        Retrieves the current lifecycle state of the client.

        :return: The current IC_STATE.
        """
        return self.__state

    def _unlock(self):
        """Mainly for debugging, jams state to UNLOCKED to allow editing of attributes outside of init/populate"""
        self.__set_state(IC_STATE.UNLOCKED)

    def _lock(self, previous_state=IC_STATE.POP_END):
        """Mainly for debugging, jams state to POP_END to allow editing of attributes outside of init/populate"""
        """Defaults to POP_END, which may or may not be correct, so I put a kwarg in there"""
        self.__set_state(previous_state)

    def _set_error(self):
        """Mainly for FailedClient so you can set the state to ERROR"""
        self.__set_state(IC_STATE.ERROR)

        
# ===============================================
# :: Dummy Class
# ===============================================
class FailedClient(InputClient):
    """Dummy class that higher-level processes can use to clearly identify Inputs which are not available
    
    Initializes the FailedClient with error details.

    :param name: The name of the client that failed.
    :param exception: The exception that caused the failure.
    """

    def _impl_init(self, name, exception):
        self._unlock()
        self.name = name
        log.debug(f'Initializing FailedClient dummy in place of {self.name}...')
        self.exception = exception
        self._set_error()

        
    def _impl_populate(self):
        """
        No-op implementation of populate for a failed client.
        """
        pass