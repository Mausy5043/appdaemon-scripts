import contextlib
import statistics as stat
from collections import deque

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]

"""Calculate moving average of Eigen Bedrijf to dampen peaks."""

VERSION = "1.0.0"

class EigenBedrijf_Avg(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        self.log(f"===================================== EigenBedrijf_Avg v{VERSION} ====")
        self.sensor = "sensor.eigen_bedrijf"
        self.avg_sensor = "sensor.eigen_bedrijf_avg"
        self.values = deque(maxlen=6)  # Stores up to 60 values
        self.listen_state(self.collect_value, self.sensor)
        self.run_every(self.calculate_average, "now", 60)

    def collect_value(self, entity, attribute, old, new, **kwargs):
        with contextlib.suppress(ValueError):
            self.values.append(float(new))

    def calculate_average(self, **kwargs):
        if self.values:
            # avg_value = round(sum(self.values) / len(self.values), 1)
            med_value = int(round(stat.median(self.values), 0))
            self.set_state(self.avg_sensor, state=med_value)
        else:
            self.set_state(self.avg_sensor, state=0)
