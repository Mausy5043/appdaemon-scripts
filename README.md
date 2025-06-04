<h1 align="center">
  <a name="logo" href=""><img src="images/logo-round-192x192.png" alt="Home Assistant Logo" width="192"></a>
  <br>
  mausy5043's Appdaemon Scripts
</h1>

## About

This is the repository containing all my Appdaemon apps.


Link the appdaemon folder to the homeassistant folder

```
ln -s /addon_configs/a0d7b954_appdaemon/ /homeassistant/appdaemon
```

Clone the apps and link the apps folder to the appdaemon folder:

Backup any existing apps as below code will delete them!
```
rm -r /addon_configs/a0d7b954_appdaemon/apps  # this will delete ALL existing apps!!!
cd addon_configs
mkdir git
cd git
git clone <appdaemon-scripts>
ln -s /addon_configs/git/appdaemon-scripts/git-apps/ /addon_configs/a0d7b954_appdaemon/apps
```

