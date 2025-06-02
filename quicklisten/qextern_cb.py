import contextlib

import appdaemon.plugins.hass.hassapi as hass


def state_changed(fles, *args, **kwargs):
    # {entity} ({attribute}): {old} -> {new}
    with contextlib.suppress(BaseException):
        fles.log("fles state changed in external ...")
    with contextlib.suppress(BaseException):
        hass.log("hass state changed in external ...")
