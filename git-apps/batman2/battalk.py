#!/usr/bin/env python
"""Control the Sessy Battery"""

import const2 as cs
import requests

requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]


class Sessy:
    """Class to interact with the Sessy Battery API."""

    def __init__(self, url: str, username: str = "", password: str = "") -> None:
        """Initialize the Sessy class."""
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.bat_ip = url
        self.api_call = cs.BATTALK["api_calls"]
        self.strat = cs.BATTALK["api_strats"]
        self.headers: dict = {"accept": "application/json"}

    def set_strategy(self, stance: str) -> dict:
        """Set strategy on battery"""
        _url = f"{self.bat_ip}/{self.api_call['strategy']}"
        _cmd = {"strategy": self.strat[stance]}
        response = self.session.post(_url, headers=self.headers, json=_cmd, auth=self.session.auth)
        response.raise_for_status()
        return response.json()

    def get_strategy(self) -> dict:
        """Get current battery strategy"""
        _url = f"{self.bat_ip}/{self.api_call['strategy']}"
        response = self.session.get(_url, headers=self.headers, auth=self.session.auth)
        response.raise_for_status()
        ret = response.json()["strategy"])
        return ret

    def set_setpoint(self, setpoint: int) -> dict:
        """Set setpoint on the battery"""
        _url = f"{self.bat_ip}/{self.api_call['setpoint']}"
        _cmd = {"setpoint": setpoint}
        response = self.session.post(_url, headers=self.headers, json=_cmd, auth=self.session.auth)
        response.raise_for_status()
        return response.json()

    def get_setpoint(self) -> dict:
        """Get current battery setpoint"""
        _url = f"{self.bat_ip}/{self.api_call['status']}"
        response = self.session.get(_url, headers=self.headers, auth=self.session.auth)
        response.raise_for_status()
        ret = response.json()["sessy"]["power_setpoint"]
        return ret
