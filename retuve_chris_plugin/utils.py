import logging
import os


# -------------------------------------------------------------------------
# Completely silence fontTools noisy logging before it starts
# -------------------------------------------------------------------------
def suppress_fonttools_logs(level_name: str = None):
    """
    Fully disable or reduce logging for fontTools and submodules.
    Call this before any import of fontTools or libraries that use it.
    """
    if level_name is None:
        level_name = os.getenv("MODULES_LOG_LEVEL", "WARNING")
    level_value = getattr(logging, level_name.upper(), logging.WARNING)

    # Basic config first (prevents root log defaults)
    logging.basicConfig(level=level_value)

    # Fix ANY preexisting fontTools loggers
    for name, logger in logging.root.manager.loggerDict.items():
        if name.startswith("fontTools"):
            # Set level
            logger_obj = logging.getLogger(name)
            logger_obj.setLevel(level_value)
            logger_obj.propagate = False  # prevent bubbling up to root
            # Remove every handler attached by fontTools itself
            for h in list(logger_obj.handlers):
                logger_obj.removeHandler(h)

    # Preemptively guard future submodules from re-adding their handlers
    logging.getLogger("fontTools").setLevel(level_value)
    logging.getLogger("fontTools").propagate = False
