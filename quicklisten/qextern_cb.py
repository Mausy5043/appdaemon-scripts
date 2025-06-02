import appdaemon.plugins.hass.hassapi as hass

def state_changed(fles, *args, **kwargs):
    # {entity} ({attribute}): {old} -> {new}
    try:
        fles.log(f"fles state changed in external ...")
    except:
        pass
    try:
        hass.log(f"hass state changed in external ...")
    except:
        pass
