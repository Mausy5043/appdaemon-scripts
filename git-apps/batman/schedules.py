import contextlib
import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs
import utils as ut

"""Handle battery schedules for Batman app."""


class Schedules(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"================================= Schedules v{cs.VERSION} ====")
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []

        self.schdl = cs.SCHEDULES
        self.mgr = self.get_app(self.schdl["manager"])
        if not self.mgr:
            self.log(f"__ERROR: {self.schdl['manager']} app not found!", level="ERROR")
            return

        # when debugging & first run: log everything
        _e: dict[str, Any] = self.get_state(entity_id=self.schdl["entity"], attribute="all")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}", level="DEBUG")
        # Initialize today's and tomorrow's schedules
        self.schedules_changed("schedules", "", "none", "new")
        _s = self.get_state(entity_id=self.schdl["entity"], attribute=self.schdl["attr"]["actual"])
        self.schedule_changed("schedule", self.schdl["attr"]["actual"], "none", _s)

        self.callback_handles.append(
            self.listen_state(
                callback=self.schedule_current_cb,
                entity_id=self.schdl["entity"],
                attribute=self.schdl["attr"]["actual"],
            )
        )
        self.callback_handles.append(
            self.listen_state(
                callback=self.schedule_list_cb,
                entity_id=self.schdl["entity"],
                attribute=self.schdl["attr"]["list"],
            )
        )

    def terminate(self):
        """Clean up app."""
        self.log("__Terminating Schedules...")
        # some cleanup code goes here
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated Schedules.")

    def schedule_changed(self, entity, attribute, old, new, **kwargs):
        """Log change of current schedule."""
        new_schedule: int = -1
        with contextlib.suppress(ValueError, TypeError):
            new_schedule = int(new)
        self.schdl["actual"] = new_schedule
        _v = ["NOM"]
        if self.schdl["actual"] > 0:
            _v = [f"API,{self.schdl['actual']}"]  # DISCHARGE
        if self.schdl["actual"] < 0:
            _v = [f"API,{self.schdl['actual']}"]  # CHARGE

        now_hour = dt.datetime.now().hour
        if now_hour in self.schdl["cheap_hour"]:
            _v += ["API,-2201"]
        if now_hour in self.schdl["expen_hour"]:
            _v += ["API,1701"]

        self.mgr.tell(caller=self.schdl["name"], message=f"Current schedule is {self.schdl['actual']}.")
        # `schedules` does not participate in the voting
        # Sessy schedule is sometimes less accurate. `prices` is more accurate at predicting the best hours.
        # self.mgr.vote(self.schdl["name"], _v)
        self.mgr.tell(self.schdl["name"], f"My vote would have been: {_v}")

    def schedules_changed(self, entity, attribute, old, new, **kwargs):
        """Handle changes in the energy schedules."""
        # Update today's and tomorrow's schedules
        today = dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        self.schdl["today"] = self.get_schedules(today)
        self.schdl["tomor"] = self.get_schedules(tomorrow)
        charge_today = ut.sort_index(self.schdl["today"], rev=True)[-3:]
        charge_today.sort()
        discharge_today = ut.sort_index(self.schdl["today"], rev=True)[:3]
        discharge_today.sort()
        charge_tomorrow = ut.sort_index(self.schdl["tomor"], rev=True)[-3:]
        charge_tomorrow.sort()
        discharge_tomorrow = ut.sort_index(self.schdl["tomor"], rev=True)[:3]
        discharge_tomorrow.sort()

        self.schdl["cheap_hour"] = charge_today
        self.schdl["expen_hour"] = discharge_today

        self.mgr.tell(
            self.schdl["name"],
            f"Today's schedules    :\n{self.schdl['today']} \n : {charge_today} {discharge_today}.",
        )
        if min(self.schdl["tomor"]) < max(self.schdl["tomor"]):
            self.mgr.tell(
                self.schdl["name"],
                f"Tomorrow's schedules :\n{self.schdl['tomor']} \n : {charge_tomorrow} {discharge_tomorrow}.",
            )

    def get_schedules(self, date) -> list[int]:
        """Get the energy schedules for a specific date."""
        no_schedules: list[int] = [0] * 24
        _s: list[int] = no_schedules
        if isinstance(date, dt.date):
            date_str: str = date.strftime("%Y-%m-%d")
            attr: dict = self.get_state(entity_id=self.schdl["entity"], attribute=self.schdl["attr"]["list"])
            _s = attr.get(date_str, no_schedules)
        else:
            self.log(f"Invalid date: {date}", level="ERROR")
        return _s

    # CALLBACKS

    def schedule_current_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for current schedule change."""
        self.schedule_changed(entity, attribute, old, new, **kwargs)

    def schedule_list_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for schedule list change."""
        self.schedules_changed(entity, attribute, old, new, **kwargs)


"""
Voting:

(1)
  0     = NOM
 (+)-ve = DISCHARGE
 (-)-ve = CHARGE

(2)
cheap hour = CHARGE
expensive hour = DISCHARGE
"""
