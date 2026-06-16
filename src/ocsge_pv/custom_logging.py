"""Custom logging module

Interface to the builtin python logging module,
adding some function to differenciate between user and admin logs.
Adds a TRACE level with a numeric value of 5 (below DEBUG).
"""

# -- IMPORTS --

import logging

# -- GLOBALS --

NAME = "pair_from_sources"
TRACE = 5
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s(%(funcName)s) %(prefix)s%(levelname)s: %(message)s",
)
logging.addLevelName(TRACE, "TRACE")
logging.captureWarnings(True)


# -- FUNCTIONS --


class LoggerInterface:
    """Custom interface to logging.Logger

    Overrides Logger's methods to allow for private or public messages.
    Has a trace method shorthand to the custom TRACE log level.
    """

    def __init__(self, name: str, public_prefix: str = "USER", private_prefix: str = ""):
        """Initialize a logger custom interface instance.

        Args:
            name (str): the name passed to the logger
            public_prefix (str, opt): string prefixed to the log level name
                in case of public messages (default: "USER")
                example from default:  "INFO" becomes "USERINFO"
            private_prefix (str, opt): string prefixed to the log level name
                in case of private messages (default: "")
                example from default:  "INFO" remains "INFO"
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.public_prefix = public_prefix
        self.private_prefix = private_prefix
        self.logger.debug(f"New logger created with name '{self.name}'")
        self.logger.debug(
            f"Level name will be prefixed by '{self.private_prefix}' "
            + "for messages targetting privileged users. ('private' messages, default)"
        )
        self.logger.debug(
            f"Level name will be prefixed by '{self.public_prefix}' "
            + "for messages targetting unprivileged users. ('public' messages)"
        )

    def log(self, level: int, msg: str, public: bool = False, *args, **kwargs):
        """Calls logging.Logger.log() with the modified level name.

        Aside from 'public', the arguments are those for logging.Logger.log()

        Args:
            level (int): logging level
            msg (str): message to log
            public (bool, opt): is the message public ? (default: False)
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        if kwargs is None:
            kwargs = {}
        if public:
            kwargs["extra"] = {"prefix": self.public_prefix}
        else:
            kwargs["extra"] = {"prefix": self.public_prefix}
        self.logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, public: bool = False, *args, **kwargs):
        """Shorthand to LoggerInterface.log(logging.DEBUG, ...).

        Args:
            level (int): logging level
            msg (str): message to log
            public (bool, opt): is the message public ? (default: False)
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.DEBUG, msg, public, *args, **kwargs)

    def info(self, msg: str, public: bool = False, *args, **kwargs):
        """Shorthand to LoggerInterface.log(logging.INFO, ...).

        Args:
            level (int): logging level
            msg (str): message to log
            public (bool, opt): is the message public ? (default: False)
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.INFO, msg, public, *args, **kwargs)

    def warning(self, msg: str, public: bool = False, *args, **kwargs):
        """Shorthand to LoggerInterface.log(logging.WARNING, ...).

        Args:
            level (int): logging level
            msg (str): message to log
            public (bool, opt): is the message public ? (default: False)
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.WARNING, msg, public, *args, **kwargs)

    def error(self, msg: str, public: bool = False, *args, **kwargs):
        """Shorthand to LoggerInterface.log(logging.ERROR, ...).

        Args:
            level (int): logging level
            msg (str): message to log
            public (bool, opt): is the message public ? (default: False)
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.ERROR, msg, public, *args, **kwargs)

    def critical(self, msg: str, public: bool = False, *args, **kwargs):
        """Shorthand to LoggerInterface.log(logging.CRITICAL, ...).

        Args:
            level (int): logging level
            msg (str): message to log
            public (bool, opt): is the message public ? (default: False)
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.CRITICAL, msg, public, *args, **kwargs)

    # Custom level
    def trace(self, msg: str, public: bool = False, *args, **kwargs):
        """Shorthand to LoggerInterface.log(TRACE, ...).

        Args:
            level (int): logging level
            msg (str): message to log
            public (bool, opt): is the message public ? (default: False)
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.TRACE, msg, public, *args, **kwargs)
