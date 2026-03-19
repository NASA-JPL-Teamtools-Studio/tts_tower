import sys
import os
import traceback
import logging
import copy
import tempfile
from pathlib import Path

#================================================
# :: Terminal Output Constants
#================================================
TERM_RESET = "\x1b[0m" # attr(0)
TERM_FG_YELLOW = "\x1b[38;5;214m" # fg(214)
TERM_FG_RED = "\x1b[38;5;160m" # fg(160)
TERM_FG_GREEN = "\x1b[38;5;28m" # fg(28)
TERM_FG_BLUE = "\x1b[38;5;26m" # fg(26)

# >> Initialize root logger
logger = logging.getLogger('tower')
# The root logger level sets the minimum level to emit across all child loggers
# This needs to be the lowest level (DEBUG) or else no other child loggers or handlers can emit DEBUG logs
logger.setLevel(logging.DEBUG)
# "propagate" determines if this logger sends log requests to the handlers of its parent (including root)
# Setting to False protects against stray handlers running our log messages (looking at you, Staxx...)
logger.propagate = False 

#================================================
# :: Basic formatter
#================================================
class ColorFormatter(logging.Formatter):
    """
    Custom logging formatter that injects ANSI color codes based on log severity.

    This formatter is primarily intended for console/stdout usage to improve
    readability of logs during development.
    """
    
    FORMATS = {
        logging.DEBUG: TERM_RESET,
        logging.INFO: TERM_RESET,
        logging.WARNING: TERM_FG_YELLOW,
        logging.ERROR: TERM_FG_RED,
        logging.CRITICAL: TERM_FG_RED
    }

    def format(self, record):
        """
        Formats the log record, prepending color codes to the level name and 
        line number.

        :param record: The log record to format.
        :type record: logging.LogRecord
        :return: The formatted log string.
        :rtype: str
        """
        level_fmt = self.FORMATS.get(record.levelno, TERM_RESET)
        record_c = copy.copy(record)
        record_c.levelname = f'{level_fmt}{record_c.levelname:<8}{TERM_RESET}'
        return super().format(record_c)

stdout_formatter = ColorFormatter(
    f'{TERM_FG_GREEN}%(asctime)s{TERM_RESET} | %(levelname)-8s | {TERM_FG_BLUE}%(name)s {TERM_FG_BLUE}<%(lineno)d>{TERM_RESET} :: %(message)s',
    datefmt='%Y-%jT%H:%M:%S'
)

# More complete logging, harder to read, w/ no colors for the log file
file_formatter = logging.Formatter(
    '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s %(funcName)s <%(lineno)d> :: %(message)s',
    datefmt='%Y-%jT%H:%M:%S'
)

# Simplistic formatter, usually for unittesting output
simple_formatter = ColorFormatter(
    '| %(levelname)-8s | %(message)s'
)

#================================================
# :: Handlers
#================================================
# Always emit to Stdout
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(stdout_formatter)
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)

def create_logger(name):
    """
    Factory function to retrieve a logger instance.

    This is the standard entry point for modules to get their logger. It ensures
    that loggers are correctly associated with the application's logging hierarchy.

    :param name: The name of the logger (typically ``__name__``).
    :type name: str
    :return: A logger instance configured for the application.
    :rtype: logging.Logger
    """
    return logging.getLogger(name)

def clear_handlers_by_type(handler_type):
    """
    Removes all handlers of a specific type from the root logger.

    :param handler_type: The class of handler to remove (e.g., ``logging.FileHandler``).
    :type handler_type: Type[logging.Handler]
    """
    _handlers = [x for x in logger.handlers if isinstance(x, handler_type)]
    for _handler in _handlers:
        logger.removeHandler(_handler)

# Initialize local variable for file handler
file_handler = None

# Optionally emit to a logfile
def log_to_file(logfile, clear_previous_files=True, tmpdir_fallback=True):
    """
    Configures the logger to output to a specified file.

    This function adds a FileHandler to the root logger. It attempts to write 
    to the requested path, but can fallback to the system temporary directory 
    if the requested path is not writable.

    :param logfile: The desired path for the log file.
    :type logfile: str | pathlib.Path
    :param clear_previous_files: If True, removes existing FileHandlers before adding the new one.
    :type clear_previous_files: bool, optional
    :param tmpdir_fallback: If True, falls back to the system temp directory if ``logfile`` is unwritable.
    :type tmpdir_fallback: bool, optional
    :raises Exception: If ``logfile`` is not a string or Path object.
    :raises PermissionError: If the file cannot be written and fallback is disabled.
    """
    if clear_previous_files is True: clear_handlers_by_type(logging.FileHandler)

    if isinstance(logfile, str):
        logfile = Path(logfile)
    elif isinstance(logfile, Path):
        pass
    else:
        raise Exception('logfile must be pathlib.Path or str type')

    # Attempt to write to the requested location
    # We check if the parent directory exists and is writable
    if logfile.parent.exists() and os.access(logfile.parent, os.W_OK):
        tmpdir_used = False
    elif tmpdir_fallback:
        # Fallback to the system's secure temporary directory
        # tempfile.gettempdir() handles cross-platform paths (Windows/Linux/Mac)
        # safely without hardcoding '/tmp/'
        logfile = Path(tempfile.gettempdir()) / logfile.name
        tmpdir_used = True
    else:
        # If not writable and fallback is disabled, we cannot proceed
        raise PermissionError(f"Cannot write to log file destination: {logfile.parent}")

    global file_handler
    file_handler = logging.FileHandler(logfile, mode='w', encoding='utf-8', delay=True)

    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    
    if tmpdir_used:
        logger.warning(f'Original path unwritable. Logging to temporary file: {logfile}')
    else:
        logger.debug(f'Logging to file: {logfile}')

logger.debug('Starting log...')


def stdout_simple_format():
    """
    Reconfigures the stdout stream handler to use the simplified formatter.

    This is useful for unit tests or CLI output where timestamps and module paths
    add too much noise.
    """
    stream_handler.setFormatter(simple_formatter)


# We want to both log Exceptions and issue them if they occur
# We also want this to work in both the IPython environment and the default commandline Python environment
try:
    # First, try IPython
    
    # If we're working with IPython, this function will exist and execute.
    # If not, it will issue a NameError which will be caught so we can do the non-IPython setup
    ipython_shell = get_ipython()
        
    # This handler shows the traceback through the normal way AND logs it
    # This will double-up on tracebacks in the stdout, but that's something we can live with for now
    # TODO: only log tracebacks to logfiles
    def ipython_handler(shell, exc_type, exc_value, tb, tb_offset=None):
        exc_info = (exc_type, exc_value, tb)
        shell.showtraceback(exc_info, tb_offset=tb_offset) # Logs to stdout in IPython
        logger.critical("Uncaught Exception", exc_info=exc_info) # Logs to whatever handlers are attached to the root logger
        return traceback.format_tb(tb)

    ipython_shell.set_custom_exc((Exception,), ipython_handler)
    
except NameError:
    # Non-IPython environment
    
    def handle_exception(exc_type, exc_value, tb):
        # Log the exception using the root logger
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, tb))
        
        # Still issue the exception as normal after logging
        sys.__excepthook__(exc_type, exc_value, tb)

    sys.excepthook = handle_exception