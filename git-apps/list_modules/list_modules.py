import os
import platform
import sys

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
from pip._internal.operations.freeze import freeze as pip_freeze

"""List Modules App
List all installed Python modules in the AppDaemon environment on start-up.

Args:
    None
"""


class ListModules(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        self.list_modules()
        self.list_system_details()

    def list_modules(self) -> None:
        """Provide some basic info about the Python environment."""
        self.log(f"Running Python {sys.version} on {sys.platform}")

        self.log("===============List of Modules===============")
        for bi in sys.builtin_module_names:
            self.log(bi)
        self.log("---------------------------------------------")
        for requirement in pip_freeze(local_only=True):
            self.log(requirement)

        self.log("=============================================^")

    def list_system_details(self) -> None:
        """Provide some basic system info for reference."""
        self.log(f"OS               : {os.uname()}")
        self.log(f"platform info    : {platform.platform()}")
        self.log(f"                 : {platform.uname()}")
        self.log(f"environment path : {sys.path}")
        self.log(f"home folder      : {os.environ['HOME']}")
        self.log(f"path to me       : {os.path.realpath(__file__)}")
