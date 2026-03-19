import pytest
import logging
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# ===================================================================
# :: Import the module to test
# ===================================================================
# We must import the module itself to access classes like ColorFormatter
# and functions like log_to_file.
import tts_tower.split_logging as split_logging_module

# ===================================================================
# :: Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def clean_logger_handlers():
    """
    Automatically run before and after each test.
    This ensures that handlers added in one test (like a FileHandler)
    don't persist and mess up subsequent tests.
    """
    # Access the specific logger instance defined in the module
    logger = split_logging_module.logger
    
    # Setup: Snapshot current handlers
    initial_handlers = logger.handlers[:]
    
    yield
    
    # Teardown: Restore initial handlers and close any file handlers created
    for handler in logger.handlers:
        if handler not in initial_handlers:
            handler.close()
            logger.removeHandler(handler)
    
    # Force restore the list to be safe
    logger.handlers = initial_handlers

# ===================================================================
# :: Unit Tests
# ===================================================================

class TestColorFormatter:
    def test_formatter_adds_colors(self):
        """Verify the formatter injects the specific ANSI codes defined."""
        # Access ColorFormatter from the module, NOT the logger instance
        formatter = split_logging_module.ColorFormatter('%(levelname)s')
        
        # Create a dummy log record
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="test", args=(), exc_info=None
        )
        
        output = formatter.format(record)
        
        # Assert the Red color code is present
        assert split_logging_module.TERM_FG_RED in output
        # Assert the Reset code is present
        assert split_logging_module.TERM_RESET in output

    def test_formatter_debug_formatting(self):
        """Verify DEBUG level usually has different formatting (RESET color)."""
        formatter = split_logging_module.ColorFormatter('%(levelname)s')
        record = logging.LogRecord(
            name="test", level=logging.DEBUG, pathname="", lineno=0,
            msg="test", args=(), exc_info=None
        )
        output = formatter.format(record)
        
        # DEBUG uses TERM_RESET in your defined FORMATS map
        assert split_logging_module.TERM_RESET in output


class TestLoggingSetup:
    def test_root_logger_config(self):
        """Verify basic configuration of the tower logger."""
        # Access the logger instance from the module
        logger = split_logging_module.logger
        assert logger.name == 'tower'
        assert logger.level == logging.DEBUG
        assert logger.propagate is False

    def test_stream_handler_attached(self):
        """Verify the standard output handler is attached by default."""
        logger = split_logging_module.logger
        # Verify the handler defined in the module is attached to the logger
        assert split_logging_module.stream_handler in logger.handlers
        assert split_logging_module.stream_handler.level == logging.INFO


class TestLogToFile:
    def test_log_to_file_success(self, tmp_path):
        """
        Verify logging to a valid writable path.
        """
        log_path = tmp_path / "test.log"
        
        # Call the function from the module
        split_logging_module.log_to_file(log_path)
        
        # 1. Check a FileHandler was added to the logger
        handlers = [h for h in split_logging_module.logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(handlers) == 1
        assert str(handlers[0].baseFilename) == str(log_path)
        
        # 2. emit a log and ensure it exists in the file
        split_logging_module.logger.debug("TEST_FILE_CONTENT")
        
        # We must flush the handler to ensure python writes to disk immediately
        handlers[0].flush()
        
        content = log_path.read_text(encoding='utf-8')
        assert "TEST_FILE_CONTENT" in content

    def test_log_to_file_clears_previous(self, tmp_path):
        """Verify that calling log_to_file clears old file handlers by default."""
        log1 = tmp_path / "log1.log"
        log2 = tmp_path / "log2.log"
        
        split_logging_module.log_to_file(log1)
        split_logging_module.log_to_file(log2, clear_previous_files=True)
        
        handlers = [h for h in split_logging_module.logger.handlers if isinstance(h, logging.FileHandler)]
        
        # Should only have 1 handler (for log2), log1 should be gone
        assert len(handlers) == 1
        assert str(handlers[0].baseFilename) == str(log2)

    def test_log_to_file_fallback_logic(self):
        """
        Verify that if the target directory is NOT writable, 
        it falls back to the system temp directory.
        """
        # We simulate a "Protected" path
        protected_path = Path("/protected/system/dir/log.txt")
        
        # Mock os.access to return False (Permission Denied)
        # Mock Path.exists to return True (The parent folder "exists" but is read-only)
        with patch("os.access", return_value=False), \
             patch.object(Path, "exists", return_value=True):
            
            split_logging_module.log_to_file(protected_path, tmpdir_fallback=True)
            
            handlers = [h for h in split_logging_module.logger.handlers if isinstance(h, logging.FileHandler)]
            assert len(handlers) == 1
            
            # The actual file used should be in the system temp directory, NOT the protected path
            actual_path = Path(handlers[0].baseFilename)
            system_temp = tempfile.gettempdir()
            
            assert str(system_temp) in str(actual_path.parent)
            assert actual_path.name == "log.txt"

    def test_log_to_file_permission_error(self):
        """
        Verify that if fallback is False and path is unwritable, 
        it raises PermissionError.
        """
        protected_path = Path("/protected/system/dir/log.txt")
        
        with patch("os.access", return_value=False), \
             patch.object(Path, "exists", return_value=True):
            
            with pytest.raises(PermissionError) as excinfo:
                split_logging_module.log_to_file(protected_path, tmpdir_fallback=False)
            
            assert "Cannot write to log file destination" in str(excinfo.value)


class TestGlobalExceptionHook:
    def test_handle_exception_exists(self):
        """Verify that the module has defined the exception handler."""
        # Depending on the environment (IPython vs Standard), one of these should exist
        has_std = hasattr(split_logging_module, 'handle_exception')
        has_ipy = hasattr(split_logging_module, 'ipython_handler')
        assert has_std or has_ipy

    def test_handle_exception_logs_critical(self, caplog):
        """
        Directly invoke the module's exception handler and check if it logs to 'tower'.
        """
        # FIX: Enable propagation temporarily so caplog (attached to root) can capture the log
        # The module explicitly sets this to False, causing caplog to see nothing.
        original_propagate = split_logging_module.logger.propagate
        split_logging_module.logger.propagate = True
        
        try:
            # Create a fake exception info tuple
            try:
                raise ValueError("Test Error")
            except ValueError:
                exc_type, exc_value, tb = sys.exc_info()
                
                # Manually call the hook (to avoid crashing the test runner)
                # We wrap in a block to ensure we capture the log
                with caplog.at_level(logging.CRITICAL, logger="tower"):
                    if hasattr(split_logging_module, 'handle_exception'):
                        split_logging_module.handle_exception(exc_type, exc_value, tb)
                    elif hasattr(split_logging_module, 'ipython_handler'):
                        # If running in an environment where IPython logic loaded
                        split_logging_module.ipython_handler(None, exc_type, exc_value, tb)
                    
                # Assert that the logger captured the critical error
                assert "Uncaught exception" in caplog.text or "Uncaught Exception" in caplog.text
                assert "Test Error" in caplog.text
        finally:
            # Restore the original state so we don't break other tests or the logger itself
            split_logging_module.logger.propagate = original_propagate