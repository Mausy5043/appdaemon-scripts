import appdaemon.plugins.hass.hassapi as hass
import qextern_cb as xt_cb


class QListen(hass.Hass):
    def initialize(self):
        entity = self.args.get("listen_for")
        attribute = self.args.get("attribute")

        self.listen_state(self.state_changed, entity, attribute=attribute)
        self.listen_state(xt_cb.state_changed, entity, attribute=attribute)
        self.log(f"\n\t*** Listening to entity: {entity}, attribute: {attribute}")

    def state_changed(self, *args, **kwargs):
        self.log("self state changed in class ...")
