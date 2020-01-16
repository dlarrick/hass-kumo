# Kumo

[![Type](https://img.shields.io/badge/Type-Custom_Component-orange.svg)](https://github.com/dlarrick/hass-kumo)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Kumo is a Home Assistant custom_component for control of Mitsubishi mini-split units.

- For US (North American) market mini-splits with KumoCloud WiFi interface (e.g. PAC-USWHS002-WF-2)
- Implements standard Home Assistant climate entities
- Supports Mode (heat/cool etc.), setpoint, fan speed, and vane swing setting
- Native Python version ("kumo" platform) utilizes [pykumo](https://github.com/dlarrick/pykumo) Python library
  - Design & implementation done to hopefully be accepted into Home Assistant natively, eventually
  - Fully local control except for initial setup (see `prefer_cache` below)
- Based on the [InComfort](https://github.com/royduin/home-assistant-incomfort) unofficial Home Assistant module as an example
- Many thanks to the [KumoJS](https://github.com/sushilks/kumojs) Node.js module author, who did the hard work of reverse-engineering how to access the WiFi interface locally

## Installation
- You may install Kumo as a HACS Custom Component. Under HACS settings, add custom repository https://github.com/dlarrick/hass-kumo as an Integration.
- Or, put the `kumo` directory from here in `custom_components/kumo` within your configuration directory. Be sure to monitor the thread in the HA commumity forums and/or this GitHub repo, since this component is still undergoing development.
- Add the following lines to your configuration.yaml:
```
kumo:
  username: !secret kumo_username
  password: !secret kumo_password
  prefer_cache: [True|False] (optional)
  connect_timeout: [float] (optional, in seconds, default 0.5)
  response_timeout: [float] (optional, in seconds, defaualt 8)
```
- add those secrets to your secrets.yaml as usual
- `prefer_cache`, if present, controls whether to contact the KumoCloud servers on startup or prefer locally cached info on how to communicate with the indoor units. Default is False.
- `connect_timeout` and `response_timeout`, if present, control network timeouts for each command or status poll from the indoor unit(s). Increase these numbers if you see frequent log messages about timeouts. Decrease these numbers to improve overall HA responsivness if you anticipate your units being offline.

## Sensors

Some useful information from indoor units is published as attributes on the climate entity. You can convert these attributes to sensors using [templates](https://community.home-assistant.io/t/using-attributes-in-lovelace/72672). Notable information available this way:
- current temperature
- humidity (if your unit has a remote sensor)
- battery level of remote sensor (if any)
- filter dirty (I've never seen this; I suspect it has to be pretty much clogged)
- defrost mode indication

## TODO
- Debugging for different types of indoor units
- Explore if other local APIs are available to provide additional useful information (whether unit is calling, etc.)
- Code cleanup. Code reviews welcome!
- Proper documentation

## Status
- As of June 2019, the legacy module has been working fine for me for several months.
- As of July 20, 2019, the master branch contains a version compatible with the Climate 1.0 API (i.e. Home Assistant 0.96 and later). The `pre-0.96` branch contains the code compatible with older versions.
- In August 2019 I began work to implement and switch to a native Python module.
- As of December 2019 there are a handful of people (including myself) successfully using the native Python module in HomeAssistant.

## License
[MIT](LICENSE)
