"""Custom logging module

Interface to the builtin python logging module,
adding some function to differenciate between user and admin logs.
Adds a TRACE level with a numeric value of 5 (below DEBUG).
"""

# -- IMPORTS --

import logging
from typing import Any

# -- GLOBALS --

NAME = "pair_from_sources"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s(%(funcName)s) %(levelname)s: %(message)s",
)
logging.captureWarnings(True)


# -- FUNCTIONS --


class LoggerInterface:
    """Custom interface to logging.Logger

    Overrides Logger's methods to allow for private or public messages.
    Has a trace method shorthand to the custom TRACE log level.
    """

    def __init__(
        self,
        name: str,
        public_prefix: str = "USER || ",
        admin_prefix: str = "",
        level: str | int = "INFO",
    ):
        """Initialize a logger custom interface instance.

        Args:
            name: the name passed to the logger
            public_prefix: public log messages' prefix
            admin_prefix: restricted log messages' prefix
            level: minimal log level name
                As a string, only accept native level names from "logging"

        Raise:
            ValueError: level is a string that doesn't match any know log level
        """
        if isinstance(level, str):
            level_int_value = logging.getLevelName(level)
            if not isinstance(level_int_value, int):
                raise ValueError(f"Unrecognized log level name : '{level}'")
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.public_prefix = public_prefix
        self.admin_prefix = admin_prefix
        self.logger.debug(f"New logger created with name '{self.name}'")
        self.logger.debug(
            f"Level name will be prefixed by '{self.admin_prefix}' "
            + "for messages targetting privileged users. ('private' messages, default)"
        )
        self.logger.debug(
            f"Level name will be prefixed by '{self.public_prefix}' "
            + "for messages targetting unprivileged users. ('public' messages)"
        )

    def setLevel(self, level: str | int) -> None:
        """Set minimal logging level.

        Args:
            level: minimal log level name
                As a string, only accept native level names from "logging"

        Raise:
            ValueError: level is a string that doesn't match any know log level
        """
        if isinstance(level, str):
            level_int_value = logging.getLevelName(level)
            if not isinstance(level_int_value, int):
                raise ValueError(f"Unrecognized log level name : '{level}'")
        self.logger.setLevel(level)
        self.admin_info(f"Minimal logging level set to {self.logger.level}")

    def setPublicPrefix(self, prefix: str) -> None:
        """Set public log messages' prefix

        Args:
            prefix: public log messages' prefix
        """
        self.public_prefix = prefix
        self.admin_debug(f"Public messages' prefix set to '{self.public_prefix}'")

    def setAdminPrefix(self, prefix: str) -> None:
        """Set restricted log messages' prefix

        Args:
            prefix: restricted log messages' prefix
        """
        self.admin_prefix = prefix
        self.admin_debug(f"Restricted messages' prefix set to '{self.admin_prefix}'")

    def log(
        self, level: str | int, msg: str, public: bool = False, *args: Any, **kwargs: Any
    ) -> None:
        """Calls logging.Logger.log() with the modified level name.

        Aside from 'public', the arguments are those for logging.Logger.log()

        Args:
            level: logging level
            msg: message to log
            public: is the message public ?
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        if public:
            new_msg = f"{self.public_prefix}{msg}"
        else:
            new_msg = f"{self.admin_prefix}{msg}"
        self.logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, public: bool = False, *args: Any, **kwargs: Any) -> None:
        """Shorthand to LoggerInterface.log(logging.DEBUG, ...).

        Args:
            msg: message to log
            public: is the message public ?
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.DEBUG, msg, public, *args, **kwargs)

    def user_debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a public DEBUG message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.debug(msg=msg, public=True, *args, **kwargs)

    def admin_debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a restricted DEBUG message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.debug(msg=msg, public=False, *args, **kwargs)

    def info(self, msg: str, public: bool = False, *args: Any, **kwargs: Any) -> None:
        """Shorthand to LoggerInterface.log(logging.INFO, ...).

        Args:
            msg: message to log
            public: is the message public ?
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.INFO, msg, public, *args, **kwargs)

    def user_info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a public INFO message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.info(msg=msg, public=True, *args, **kwargs)

    def admin_info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a restricted INFO message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.info(msg=msg, public=False, *args, **kwargs)

    def warning(self, msg: str, public: bool = False, *args: Any, **kwargs: Any) -> None:
        """Shorthand to LoggerInterface.log(logging.WARNING, ...).

        Args:
            msg: message to log
            public: is the message public ?
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.WARNING, msg, public, *args, **kwargs)

    def user_warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a public WARNING message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.warning(msg=msg, public=True, *args, **kwargs)

    def admin_warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a restricted WARNING message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.warning(msg=msg, public=False, *args, **kwargs)

    def error(self, msg: str, public: bool = False, *args: Any, **kwargs: Any) -> None:
        """Shorthand to LoggerInterface.log(logging.ERROR, ...).

        Args:
            msg: message to log
            public: is the message public ?
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.ERROR, msg, public, *args, **kwargs)

    def user_error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a public ERROR message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.error(msg=msg, public=True, *args, **kwargs)

    def admin_error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a restricted ERROR message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.error(msg=msg, public=False, *args, **kwargs)

    def critical(self, msg: str, public: bool = False, *args: Any, **kwargs: Any) -> None:
        """Shorthand to LoggerInterface.log(logging.CRITICAL, ...).

        Args:
            msg: message to log
            public: is the message public ?
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.log(logging.CRITICAL, msg, public, *args, **kwargs)

    def user_critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a public CRITICAL message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.critical(msg=msg, public=True, *args, **kwargs)

    def admin_critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Send a restricted CRITICAL message

        Args:
            msg: message to log
            *args: other logging.Logger.log() positional arguments reference
            **kwargs: other logging.Logger.log() keyword arguments reference
        """
        self.critical(msg=msg, public=False, *args, **kwargs)
