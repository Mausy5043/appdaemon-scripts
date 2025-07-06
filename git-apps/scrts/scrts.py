import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]

"""Access secrets.yaml file for other apps"""
VERSION = "0.2.0"


class Secrets(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"============================== Secret dispenser v{VERSION} ====")
        for _key, _ in self.args.items():
            self.log(f"{_key}")

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

    def get_tibber_url(self) -> str:
        """Get the Tibber API URL from the secrets.yaml."""
        _url: str = ""
        if "tibber_url" not in self.args:
            self.log("*** No 'tibber_url' found in args", level="ERROR")
            return "NO_URL_FOUND"
        _url = self.args["tibber_url"]
        if not _url:
            self.log("**** Empty 'tibber_url' found in args", level="ERROR")
        return _url

    def get_sessy_secrets(self, battery: str) -> dict[str, str]:
        """Get the Sessy API info from the secrets.yaml."""
        _url: str = ""
        _url_secret = f"sessy_{battery}_url"
        if _url_secret not in self.args:
            self.log(f"*** No '{_url_secret}' found in args", level="ERROR")
            return {"error": "NO_URL_FOUND"}
        _url = self.args[_url_secret]
        if not _url:
            self.log(f"**** Empty '{_url_secret}' found in args", level="ERROR")

        _auth: str = ""
        _auth_secret = f"sessy_{battery}_auth"
        if _auth_secret not in self.args:
            self.log(f"*** No '{_auth_secret}' found in args", level="ERROR")
            return {"error": "NO_URL_FOUND"}
        _auth = self.args[_auth_secret]
        if not _url:
            self.log(f"**** Empty '{_auth_secret}' found in args", level="ERROR")
        _auth_user, _auth_pwd = _auth.split(".")
        return {"url": _url, "username": _auth_user, "password": _auth_pwd}

    def get_location(self) -> dict[str, str]:
        # Return location
        loc_info = [
            "latitude",
            "longitude",
            "city",
            "country",
            "timezone",
        ]
        ret_dict = {}
        for _key in loc_info:
            ret_dict[_key] = self.args[_key]
        return ret_dict
