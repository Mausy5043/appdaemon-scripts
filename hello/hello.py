import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingImports]

"""Hello World App
Log a simple "Hello World" message when initialized.

Args:
    None
"""


class HelloWorld(hass.Hass):
    def initialize(self):
        self.set_namespace("hello")
        self.log("Hello World from AppDaemon")
