import appdaemon.plugins.hass.hassapi as hass


class QListen2(hass.Hass):
    def initialize(self):
        entity = self.args.get("listen_for")
        attribute = self.args.get("attribute")

        self.listen_state(self.state_changed, entity, attribute=attribute)
        # self.listen_state(xt_cb.state_changed, entity, attribute=attribute)
        self.log(f"\n\t*** Listening to entity: {entity}, attribute: {attribute}")
        self.notifier = self.get_app("qextern")

    def state_changed(self, *args, **kwargs):
        self.log("qlisten self state changed in class ...")
        self.notifier.notify("ping!")
