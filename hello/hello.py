import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]

"""Hello World App
Log a simple "Hello World" message when initialized.

Args:
    None
"""


class HelloWorld(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        self.set_namespace("hello")
        self.log("Hello World from AppDaemon")
