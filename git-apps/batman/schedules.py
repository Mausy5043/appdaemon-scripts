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

        self.the_batman = self.get_app("batman")
        # Initialize current schedule and today's and tomorrow's list of schedules
        self.now_schedule: int = cs.ACT_SCHEDULE
        self.todays_schedules: list[int] = []
        self.tomorrows_schedules: list[int] = []
        self.log(f"================================= Schedules v{cs.VERSION} ====")
        # when debugging & first run: log everything
        _e: dict[str, Any] = self.get_state(entity_id=cs.ENT_SCHEDULE, attribute="all")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}", level="INFO")
        # Initialize today's and tomorrow's schedules
        self.schedules_changed("schedules", "", "none", "new")
        _s = self.get_state(entity_id=cs.ENT_SCHEDULE, attribute=cs.CUR_SCHEDULE_ATTR)
        self.schedule_changed("schedule", cs.CUR_SCHEDULE_ATTR, "none", _s)

        self.callback_handles.append(
            self.listen_state(self.schedule_current_cb, cs.ENT_SCHEDULE, attribute=cs.CUR_SCHEDULE_ATTR)
        )
        self.callback_handles.append(
            self.listen_state(self.schedule_list_cb, cs.ENT_SCHEDULE, attribute=cs.LST_SCHEDULE_ATTR)
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
        try:
            old = f"{int(old)}"
            new = f"{int(new)}"
        except (ValueError, TypeError):
            pass
        # self.log(f"{entity} ({attribute}) changed : {old} -> {new}")
        self.now_schedule = int(new)
        proposal: str = "nom"
        self.log(f"__New schedule = {self.now_schedule}")
        if self.now_schedule > 0:
            proposal = "discharge"
        if self.now_schedule < 0:
            proposal = "charge"
        self.batman.tell(f"Current schedule is {self.now_schedule} ({proposal})")

    def schedules_changed(self, entity, attribute, old, new, **kwargs):
        """Handle changes in the energy schedules."""
        # self.log(f"Schedules changed: {old} -> {new}")
        # Update today's and tomorrow's schedules
        today = dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        self.todays_schedules = self.get_schedules(today)
        self.tomorrows_schedules = self.get_schedules(tomorrow)
        charge_today = ut.sort_index(self.todays_schedules)[-3:]
        discharge_today = ut.sort_index(self.todays_schedules)[:3]
        charge_tomorrow = ut.sort_index(self.tomorrows_schedules)[-3:]
        discharge_tomorrow = ut.sort_index(self.tomorrows_schedules)[:3]
        self.log(f"__Today's schedules    :\n{self.todays_schedules} \n : {charge_today} {discharge_today}.")
        self.log(
            f"__Tomorrow's schedules :\n{self.tomorrows_schedules} \n : {charge_tomorrow} {discharge_tomorrow}."
        )

    def get_schedules(self, date) -> list[int]:
        """Get the energy schedules for a specific date."""
        no_schedules: list[int] = [0] * 24
        _s: list[int] = no_schedules
        if isinstance(date, dt.date):
            date_str: str = date.strftime("%Y-%m-%d")
            attr: dict = self.get_state(entity_id=cs.ENT_SCHEDULE, attribute=cs.LST_SCHEDULE_ATTR)
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


# schedule
#  0 = nom
#  (+)  || SoC > 75% || summerday |-> = discharge to 25%
#  (-)  || SoC < 32% || winterday |-> = charge to 100%
# definition of summerday is

# summerday = 1st of May to 30th of September
# sensors that detect summerday or winterday:
#  - sensor.batman_summerday
#  - sensor.batman_winterday
#  - sensor.batman_tommorow_summerday
#  - sensor.batman_tommorow_winterday
#  winterday = 1st of October to 30th of April
