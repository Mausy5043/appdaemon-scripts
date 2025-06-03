import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]

"""Listen App
Listen to changes in an entity's state or attribute, or to a specific event.

Args:
    entity: The entity to listen to.
    attribute: The attribute of the entity to listen to.
    event: The event to listen for.
"""


class Listen(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        self.set_namespace("listen")
        entity = self.args.get("listen_for")
        attribute = self.args.get("attribute")
        event = self.args.get("event")
        _e = self.get_state(entity_id=entity, attribute="all", namespace="default")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}")

        # Check if entity, attribute, or event is provided
        if entity and attribute:
            self.listen_state(self.state_change, entity, attribute=attribute, namespace="default")
            self.log(f"\n\t*** Listening to entity: {entity}, attribute: {attribute}")
        elif entity:
            self.listen_state(self.state_change, entity, namespace="default")
            self.log(f"\n\t*** Listening to entity: {entity}")
        elif event:
            self.listen_event(self.event_triggered, event, namespace="default")
        else:
            self.log("No valid entity or event specified.")

    def state_change(self, entity, attribute, old, new, kwargs):
        self.log(f"State changed for {entity} ({attribute}): {old} -> {new}")

    def event_triggered(self, event_name, data, kwargs):
        self.log(f"Event triggered: {event_name} with data: {data}")
