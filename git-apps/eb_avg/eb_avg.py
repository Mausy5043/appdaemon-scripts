import statistics as stat
import traceback
from collections import deque

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]

"""Calculate moving average of Eigen Bedrijf to dampen peaks."""

VERSION: str = "1.4.1"
QLEN: int = 12
ATTR_EB: dict = {"unit_of_measurement": "W", "friendly_name": "eigen_bedrijf_avg"}


class EigenBedrijf_Avg(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        self.log(f"============================= EigenBedrijf_Avg v{VERSION} ====")
        self.sensor = "sensor.eigen_bedrijf"
        self.avg_sensor = "sensor.eigen_bedrijf_avg"
        self.values: deque[float] = deque(maxlen=QLEN)

        # intialise callbacks
        self.callback_handles: list = []
        self.callback_handles.append(self.listen_state(self.collect_value, self.sensor))
        self.run_every(self.calculate_average, "now", 60)

    def terminate(self):
        """Clean up app."""
        self.log("__Terminating EigenBedrijf_Avg...")
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated EigenBedrijf_Avg.")

    def collect_value(self, entity, attribute, old, new, **kwargs):
        try:
            _insert = float(new)
            _insert = max(0.0, _insert)
        except ValueError:
            _insert = 0.0
        self.values.append(_insert)

    def calculate_average(self, **kwargs):
        med_value: int = 0
        if self.values:
            med_value = int(round(stat.mean(self.values), 0))
            try:
                self.set_state(entity_id=self.avg_sensor, state=med_value, attributes=ATTR_EB)
            except Exception as her:
                self.log(str(type(her)), level="ERROR")
                self.log(str(her), level="ERROR")
                self.log(traceback.format_exc(), level="ERROR")
                self.log(
                    f"Could not update average {med_value} from {self.values} for {self.avg_sensor}",
                    level="ERROR",
                )
