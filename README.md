# Home Assistant module interfacing with KumoJS
Home Assistant control of Mitsubishi mini-split units

- For US (North American) market mini-splits with KumoCloud WiFi interface
- Implements standard Home Assistant climate entities
- Supports Mode (heat/cool etc.), setpoint, fan speed, and vane swing setting
- Interfaces with [KumoJS](https://github.com/sushilks/kumojs) Node.js module, which actually communicates with the KumoCloud adapter.
  - You should have KumoJS running as a server on a locally-accessible machine.
  - Note: Node.js on Raspbian seems to be too old to run this server as of this writing (March 2019)
- Based on the [InComfort](https://github.com/royduin/home-assistant-incomfort) unofficial Home Assistant module as an example

## Installation
Put the `climate.py` file in `custom_components/KumoJS` within your configuration directory. On Ubuntu or Raspbian for example: `~/.homeassistant/custom_components/KumoJS`. After that configure it in the `configuration.yaml` file:
```
climate:
  - platform: KumoJS
    name: "Master BR"
    host: 192.168.1.123
```
And change the `name` and `host` as needed.

## TODO
- Auto-discovery of mini-split units from KumoJS's list
- Reverse-engineer what KumoJS is doing into a Python module, and interface with it directly
- Code cleanup. Code reviews welcome!

## Status
- As of June 2019, this module has been working fine for me for several months. I have no current plans to implement the TODO list but will accept patches.

## License
[MIT](LICENSE)
