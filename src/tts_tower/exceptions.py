# ===================================================================
# :: Base Exception
# ===================================================================
class TowerException(Exception):
    """
    Base exception class for all Tower-related errors.

    All custom exceptions in the Tower library should inherit from this class
    to allow for coarse-grained error handling of library-specific issues.
    """
    pass

# ===================================================================
# :: Checker
# ===================================================================
class CheckerStepFailure(TowerException):
    """
    Exception raised when a specific step within a Checker fails.

    This indicates that a discrete logical step within a checker could not be
    completed, typically due to missing data or calculation errors, without
    necessarily crashing the entire application.
    """
    pass