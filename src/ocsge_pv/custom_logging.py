"""Custom logging module

Adds prefix to messages.
"""

# -- IMPORTS


## from stdlib
import logging

# -- CLASSES --


class LoggerInterface(logging.LoggerAdapter):
    """Custom interface to logging.Logger

    Overrides Logger's methods to allow for private or public messages.
    """

    def __init__(self, logger: logging.Logger, prefix: str = ""):
        """Initialize a logger custom interface instance.

        Args:
            logger: the targeted logger
            prefix: log messages' prefix
        """
        super().__init__(
            logger,
            {
                "prefix": prefix,
            },
        )

    def process(self, msg: str, kwargs: dict) -> (str, dict):
        """Adds the prefix to the message

        Overrides super().process(msg, kwargs)
        """
        new_msg = f"{self.extra['prefix']}{msg}"
        return new_msg, kwargs

    def set_prefix(self, prefix: str) -> None:
        self.extra["prefix"] = prefix
