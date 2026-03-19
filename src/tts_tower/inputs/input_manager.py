#Standard Library Imports
import traceback
import pdb

#Installed Dependency Imports
# None

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
from tts_tower.util import reverse_prio_dict_merge
from .input_client import FailedClient
from .state import StateClient

log = create_logger(__name__)

# ===============================================
# :: Helper Class
# ===============================================
class input_get:
    """Simple wrapper class to identify InputClient names to pass as input to other InputClients"""
    def __init__(self, name):
        """
        Initializes the wrapper with the name of the dependent client.

        :param name: The name of the InputClient to retrieve data from.
        :type name: str
        """
        self.name = name

def log_step_exception(name, step, e):
    """
    Logs an exception that occurred during a specific step of an InputClient's lifecycle.

    :param name: The identifier of the InputClient.
    :type name: str
    :param step: The lifecycle step where the error occurred (e.g., 'initialization', 'population').
    :type step: str
    :param e: The exception instance caught.
    :type e: Exception
    """
    e_short = f'{e.__class__} :: {". ".join([str(_) for _ in e.args])}'
    log.warning(
        f'Exception during {step} of "{name}" Input Client, will be unusable. See log for full traceback:\n{e_short}')
    log.warning(traceback.format_exc())

# ===============================================
# :: Manager
# ===============================================
class InputManager:
    """
    Primary manager of all Inputs to the Rulechecking process.

    Handles initializing, populating, and distributing Inputs to any Checkers that request them.
    Contains exception handling to catch and prevent Exceptions from bringing down the whole script.

    Manager is set to read-only by default
    """
    def __init__(self):
        log.debug(f'Initializing InputClientManager')
        # >> Initialize "private" state
        self.__writeable = False # Locks inputs down after initialization
        self.__ic = None
        
    def __enter__(self):
        """
        Enters the context manager, enabling write access for adding clients.
        Resets the internal client registry.

        :return: The active InputManager instance.
        :rtype: InputManager
        """
        log.debug(f'Starting writeable context for InputClientManager')
        self.__ic = {} # Reset the state/client list
        self.__writeable = True
        return self
    
    def __exit__(self, *argv, **kwargs):
        """
        Exits the context manager, locking write access.
        Logs a summary of successful and failed client additions.

        :param argv: Variable arguments containing exception information (type, value, traceback) if one occurred.
        :param kwargs: Keyword arguments (unused).
        """
        self.__writeable = False
        # >> Report status of the input adds
        n_total = len([_ for _ in self.iter_all_clients()])
        n_success = len([_ for _ in self.iter_all_clients(skip_failed=True)])
        log.debug(f'Finished writing to InputClientManager, {n_success} successful clients and {n_total - n_success} failed')
            
    def _add(self, name, cls_const, argv, kwargs_dict=None):
        """
        Internal workhorse for initializing and logging a new Input.
        
        Resolves any ``input_get`` dependencies before instantiation.

        :param name: Unique identifier for the input client.
        :type name: str
        :param cls_const: The class constructor for the InputClient.
        :type cls_const: type
        :param argv: List of positional arguments to pass to the client's constructor.
        :type argv: list
        :param kwargs_dict: Dictionary of keyword arguments to pass to the client's constructor.
        :type kwargs_dict: dict, optional
        :raises Exception: If the manager is not currently in a writeable context.
        """
        if not self.__writeable:
            raise Exception(f'InputManager is not currently in a writeable context!')

        # >> Set empty default (dict is mutable)
        kwargs_dict = kwargs_dict or {}
        
        if name in self.__ic:
            log.warning(f'Found duplicate Input Client name "{name}", overwriting!')
            
        log.debug(f'Adding InputClient from definition: "{name}" ; {cls_const}')

        # >> Blanket try..except to decrease likelihood of blowing the whole run
        try:
            # Need to swap in for any "input_get" objects
            for arg_i, arg in enumerate(argv):
                if isinstance(arg, input_get):
                    argv[arg_i] = self.get(arg.name)

            for arg_k, arg_v in kwargs_dict.items():
                if isinstance(arg_v, input_get):
                    if self.has_input(arg_v.name):
                        kwargs_dict[arg_k] = self.get(arg_v.name)
                    else:
                        kwargs_dict[arg_k] = None
            self.__ic[name] = cls_const(*argv, **kwargs_dict)

        # >> Any failure results in a FailedClient added instead
        except Exception as e:
            log_step_exception(name, 'initialization', e)
            self.__ic[name] = FailedClient(name, e)
            
    def add_client(self, name, cls_const, args, kwargs_dict=None):
        """
        Add a new InputClient with all associated logic.

        :param name: Unique identifier for the input client.
        :type name: str
        :param cls_const: The InputClient class (not an instance) to be instantiated.
        :type cls_const: type
        :param args: List of positional arguments to pass to the client's ``__init__``.
        :type args: list
        :param kwargs_dict: Dictionary of keyword arguments to pass to the client's ``__init__``.
        :type kwargs_dict: dict, optional
        """
        self._add(name, cls_const, args, kwargs_dict=kwargs_dict)
        
    def add_state(self, name, value):
        """
        Add a simple state value (StateClient) to the Inputs list.

        :param name: Unique identifier for the state.
        :type name: str
        :param value: The value to be stored in the state.
        :type value: Any
        """
        self._add(name, StateClient, [name, value])
        
    def has_input(self, name):
        """
        Basic check whether a particular Input (or State) has been added with a specific name.

        :param name: The name of the input to check.
        :type name: str
        :return: True if the input exists, False otherwise.
        :rtype: bool
        """
        return name in self.__ic
            
    def get(self, name):
        """
        Check if this manager has a particular Input (or State) by name and return if it does.

        :param name: The name of the input to retrieve.
        :type name: str
        :return: The requested InputClient instance.
        :rtype: InputClient
        :raises ValueError: If no Input Client with the specified name is found.
        """
        if not self.has_input(name):
            raise ValueError(f'No Input Client named "{name}" found')
        return self.__ic[name]
    
    def iter_all_clients(self, skip_failed=False):
        """
        Provide a generator for Inputs (or States), optionally skipping Failed clients.

        :param skip_failed: If True, skips clients that failed to initialize or populate. Defaults to False.
        :type skip_failed: bool
        :yield: A tuple containing the client name and the client instance.
        :rtype: Iterator[tuple[str, InputClient]]
        """
        for name, ic in self.__ic.items():
            if isinstance(ic, FailedClient) and skip_failed is True:
                continue
            yield name, ic

    def populate_all_clients(self):
        """
        Run population routines for all InputClients safely.
        
        Catches exceptions during population, logs them, and replaces the client with a FailedClient.
        """
        for name, ic in self.iter_all_clients():
            try:
                ic.populate()
            except Exception as e:
                log_step_exception(name, 'population', e)
                self.__ic[name] = FailedClient(name, e)
                self.__ic[name].populate()

    def get_run_info(self):
        """
        Aggregates run information (metadata) from all registered input clients.

        Merges dictionaries returned by each client's ``_get_run_info`` method.

        :return: A dictionary containing merged run information from all clients.
        :rtype: dict
        """
        run_info = {}
        for ic_name, ic in self.iter_all_clients():
            try:
                # Merge the dictionaries preserving old entries
                run_info = reverse_prio_dict_merge(run_info, ic._get_run_info())
            except Exception:
                log.critical(f'Failed to capture run info from {ic_name}')
                log.debug(traceback.format_exc())
        return run_info # Un-reverse everything at the end