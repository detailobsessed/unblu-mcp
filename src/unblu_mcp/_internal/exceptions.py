class ConfigurationError(Exception):
    """Raised when there's a configuration or setup error.

    This exception is caught by the CLI and displayed as a clean error message
    without a full traceback, making it easier for users to understand what
    went wrong.
    """
