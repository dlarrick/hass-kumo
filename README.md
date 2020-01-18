# Mitsubishi Kumo Cloud

[![Type](https://img.shields.io/badge/Type-Custom_Component-orange.svg)](https://github.com/dlarrick/hass-kumo) [![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

Kumo is a Home Assistant custom_component for control of Mitsubishi mini-split units.

- For US (North American) market mini-splits with KumoCloud WiFi interface (e.g. PAC-USWHS002-WF-2)
- Implements standard Home Assistant climate entities
- Supports Mode (heat/cool etc.), setpoint, fan speed, and vane swing setting
- Native Python version ("kumo" platform) utilizes [pykumo](https://github.com/dlarrick/pykumo) Python library
  - Design & implementation done in compliance with Home Assistant coding guidelines
  - Fully local control except for initial setup (see `prefer_cache` below)
- Based on the [InComfort](https://github.com/royduin/home-assistant-incomfort) unofficial Home Assistant module as an example
- Many thanks to the [KumoJS](https://github.com/sushilks/kumojs) Node.js module author, who did the hard work of reverse-engineering how to access the WiFi interface locally

## Installation
- Kumo is listed in the HACS default store. Click the HACS badge above for details on installing & using HACS.
- For a manual install, put the `custom_components/kumo` directory from here in `custom_components/kumo` within your HomeAssistant configuration directory. 
- Add the following configuration to your configuration.yaml:
```
kumo:
  username: !secret kumo_username
  password: !secret kumo_password
  prefer_cache: [true|false] (optional)
  connect_timeout: [float] (optional, in seconds, default 0.5)
  response_timeout: [float] (optional, in seconds, defaualt 8)
```
- add those secrets to your secrets.yaml as usual
- `prefer_cache`, if present, controls whether to contact the KumoCloud servers on startup or prefer locally cached info on how to communicate with the indoor units. Default is `false`, to accommodate changing unit availability or DHCP leases. If your configuration is static (including the units' IP addresses on your LAN), it's safe to set this to `true`
- `connect_timeout` and `response_timeout`, if present, control network timeouts for each command or status poll from the indoor unit(s). Increase these numbers if you see frequent log messages about timeouts. Decrease these numbers to improve overall HA responsivness if you anticipate your units being offline.

For support, see the [thread](https://community.home-assistant.io/t/mitsubishi-kumo-cloud-integration/121508/128) on the Home Assistant community. For bugs or feature improvements, feel free to create a GitHub issue or pull request.

## HA Sensors

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
- Possible enhancement: allow setup and control of schedules and operating modes on the indoor unit itself
- UI-guided setup in Home Assistant
- Possibly work toward inclusion as an official Home Assistant integration

## Status
- As of June 2019, the legacy module using KumoJS has been working fine for me for several months.
- As of July 20, 2019, the master branch contains a version compatible with the Climate 1.0 API (i.e. Home Assistant 0.96 and later). The `pre-0.96` branch contains the code compatible with older versions.
- In August 2019 I began work to implement and switch to a native Python module.
- As of December 2019 there are a handful of people (including myself) successfully using the native Python module in HomeAssistant.
- As of January 2020, Kumo is available in the HACS default store, and I consider it feature-complete and stable.

## License
[MIT](LICENSE)
