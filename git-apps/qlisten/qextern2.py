import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]


class QExtern2(hass.Hass):  # type: ignore[misc]
  def initialize(self):
      pass

  def notif(self, message: str):
      self.log(f"QExtern2 notif called with message: {message}")
      # Here you can implement the logic to send the notification
      # For example, using a service call or another method
