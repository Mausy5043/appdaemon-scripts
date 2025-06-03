import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]


class QExtern2(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        pass

    def notify(self, message):
        self.log(f"qextern notified : {message}")


# def state_changed(fles, *args, **kwargs):
#     # {entity} ({attribute}): {old} -> {new}
#     try:
#         fles.log(f"fles state changed in external ...")
#     except:
#         pass
#     try:
#         hass.log(f"hass state changed in external ...")
#     except:
#         pass
