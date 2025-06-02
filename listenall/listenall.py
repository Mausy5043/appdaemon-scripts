import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingImports]

"""ListenAll App
Listen to changes in an entity's state or attribute, or to a specific event.

Args:
    entity: The entity to listen to.
    attribute: The attribute of the entity to listen to.
    event: The event to listen for.
"""


class ListenAll(hass.Hass):
    def initialize(self):
        """Listen to everything"""
        self.listen_state(self.state_change)

    def state_change(self, entity, attribute, old, new, kwargs):
        self.log(f"State changed for {entity} ({attribute}): {old} -> {new}")

    def event_triggered(self, event_name, data, kwargs):
        self.log(f"Event triggered: {event_name} with data: {data}")
