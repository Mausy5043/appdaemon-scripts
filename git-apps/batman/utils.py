"""Utility functions for the Batman app."""


def log_entity_attr(hass, entity_id, attribute="all", level="DEBUG"):
    """Log everything we can known about an entity."""
    entity_state = hass.get_state(entity_id, attribute=attribute)
    if isinstance(entity_state, dict):
        for key, value in entity_state.items():
            hass.log(f"____{key}: {value}", level=level)
    else:
        hass.log(f"____{entity_id} ({attribute}): {entity_state}", level=level)


def sort_index(lst, rev=True):
    s = sorted(enumerate(lst), reverse=rev, key=lambda i: lst[i])
    return s
