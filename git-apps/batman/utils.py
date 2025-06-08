"""Utility functions for the Batman app."""


def log_entity_attr(hass, entity_id, attribute="all", level="DEBUG"):
    """Log everything we can known about an entity."""
    entity_state = hass.get_state(entity_id, attribute=attribute)
    if isinstance(entity_state, dict):
        for key, value in entity_state.items():
            hass.log(f"____{key}: {value}", level=level)
    else:
        hass.log(f"____{entity_id} ({attribute}): {entity_state}", level=level)


def sort_index(lst: list, rev=True):
    s: list = [i[0] for i in sorted(enumerate(lst), key=lambda x:x[1], reverse=rev)]
    return s
