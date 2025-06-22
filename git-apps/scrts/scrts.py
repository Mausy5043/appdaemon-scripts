import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]

"""Access secrets.yaml file for other apps"""
VERSION = "0.1.0"


class Secrets(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"============================== Secret dispenser v{VERSION} ====")

    def get_tibber_token(self) -> str:
        """Get the Tibber token from the secrets.yaml."""
        _scrt: str = ""
        if "tibber_token" not in self.args:
            self.log("*** No 'tibber_token' found in args", level="ERROR")
            return "NO_TOKEN_FOUND"
        _scrt = self.args["tibber_token"]
        if not _scrt:
            self.log("**** Empty 'tibber_token' found in args", level="ERROR")
        return _scrt
