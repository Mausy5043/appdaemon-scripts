#!/usr/bin/env python
"""Control the Sessy Battery"""

from typing import Any

import const3 as cs
import requests

requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]


class Sessy:
    """Class to interact with the Sessy Battery API."""

    def __init__(self, url: str, username, password, taip: str) -> None:
        """Initialize the Sessy class."""
        self.taip = taip
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.bat_ip: str = url
        self.api_call: dict[str, str] = cs.BATTALK["api_calls"]
        self.strat: dict[str, str] = cs.BATTALK["api_strats"]
        self.headers: dict[str, str] = {"accept": "application/json"}
        self.status: dict[str, Any] = self.get_status()
        self.strategy: str = self.get_strategy()
        self.pwr_sp: str = self.get_setpoint()

    def set_strategy(self, stance: str) -> dict:
        """Set strategy on battery"""
        ret = {}
        if self.taip == "bat":
            _url = f"{self.bat_ip}/{self.api_call['strategy']}"
            _cmd = {"strategy": self.strat[stance]}
            response = self.session.post(_url, headers=self.headers, json=_cmd, auth=self.session.auth)
            response.raise_for_status()
            ret: dict = response.json()
        return ret

    def get_strategy(self) -> str:
        """Get current battery strategy"""
        ret = "unsupported"
        if self.taip == "bat":
            _url = f"{self.bat_ip}/{self.api_call['strategy']}"
            response = self.session.get(_url, headers=self.headers, auth=self.session.auth)
            response.raise_for_status()
            ret: str = response.json()["strategy"]
        return ret

    def update_strategy(self):
        """Update strategy of battery"""
        self.strategy = self.get_strategy()

    def set_setpoint(self, setpoint: int) -> dict:
        """Set API setpoint on the battery"""
        _url = f"{self.bat_ip}/{self.api_call['setpoint']}"
        _cmd = {"setpoint": setpoint}
        response = self.session.post(_url, headers=self.headers, json=_cmd, auth=self.session.auth)
        response.raise_for_status()
        ret: dict = response.json()
        return ret

    def get_setpoint(self) -> str:
        """Get current battery setpoint"""
        ret = "unsupported"
        if self.taip == "bat":
            _url = f"{self.bat_ip}/{self.api_call['status']}"
            response = self.session.get(_url, headers=self.headers, auth=self.session.auth)
            response.raise_for_status()
            ret: str = response.json()["sessy"]["power_setpoint"]
        return ret

    def update_setpoint(self) -> None:
        """Update the API setpoint on the battery."""
        self.pwr_sp = self.get_setpoint()

    def set_xom_setpoint(self, setpoint: int) -> dict:
        """Set XOM setpoint on the P1 meter"""
        ret = {}
        if self.taip == "p1":
            _url = f"{self.bat_ip}/{self.api_call['grid_target']}"
            _cmd = {"grid_target": setpoint}
            response = self.session.post(_url, headers=self.headers, json=_cmd, auth=self.session.auth)
            response.raise_for_status()
            ret: dict = response.json()
        return ret

    def get_xom_setpoint(self) -> int:
        """Set XOM setpoint on the P1 meter"""
        ret: int = -1
        if self.taip == "p1":
            _url = f"{self.bat_ip}/{self.api_call['grid_target']}"
            response = self.session.get(_url, headers=self.headers, auth=self.session.auth)
            response.raise_for_status()
            ret = int(response.json()["grid_target"])
        return ret

    def get_status(self) -> dict[str, Any]:
        """Get current battery status"""
        if self.taip == "bat":
            _url = f"{self.bat_ip}/{self.api_call['status']}"
        else:
            _url = f"{self.bat_ip}/{self.api_call['details']}"
        response = self.session.get(_url, headers=self.headers, auth=self.session.auth)
        response.raise_for_status()
        ret: dict[str, Any] = response.json()
        self.update_setpoint()
        self.update_strategy()
        return ret

    def update_status(self):
        """Update status of battery"""
        self.status = self.get_status()
