# Mitsubishi Kumo Cloud

[![Type](https://img.shields.io/badge/Type-Custom_Component-orange.svg)](https://github.com/dlarrick/hass-kumo) [![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

Mitubishi Kumo Cloud (Kumo for short) is a custom component for Home Assistant that allows you to control Mitsubishi mini-split units that are connected to the Mitsubishi KumoCloud service.

- For US (North American) market mini-splits with a KumoCloud WiFi interface (for example, PAC-USWHS002-WF-2).
- Implements standard Home Assistant [`climate`](https://www.home-assistant.io/integrations/climate/) entities.
- Supports reading and setting the mode (heat/cool/etc.), setpoint, fan speed, and vane swing.
- Supports fully local control, except for initial setup. (See `prefer_cache` in Configuration for details.)

## Installation

You can install Kumo in one of two ways. 

- **Automatic Installation.** Kumo is available in the HACS default store. Search for "Kumo" in the Integrations panel, and then click the **Mitsubishi Kumo Cloud** item in the results. Click the Install link, and then restart Home Assistant. 
- **Manual Installation.** To control your installation yourself, download the hass-kumo repo, and then copy the `custom_components/kumo` directory into a corresponding `custom_components/kumo` within your Home Assistant configuration directory. Then restart Home Assistant.

We recommend using the HACS installation method, which makes future updates to Kumo easy to track and install. Click the HACS badge above for details on installing and using HACS.

## Configuration

Configuration for Kumo is currently YAML only. Add the following configuration to your configuration.yaml:

```
kumo:
  username: !secret kumo_username
  password: !secret kumo_password
  prefer_cache: [true|false] (optional)
  connect_timeout: [float] (optional, in seconds, default 0.5)
  response_timeout: [float] (optional, in seconds, default 8.0)
```

Add the referenced secrets to your secrets.yaml.

- `prefer_cache`, if present, controls whether to contact the KumoCloud servers on startup, or to prefer locally cached info on how to communicate with the indoor units. Default is `false`, to accommodate changing unit availability or DHCP leases. If your configuration is static (including the units' IP addresses on your LAN), it's safe to set this to `true`. This will allow you to control your system even if KumoCloud or your Internet connection suffer an outage. 
- `connect_timeout` and `response_timeout`, if present, control network timeouts for each command or status poll from the indoor unit(s). Increase these numbers if you see frequent log messages about timeouts. Decrease these numbers to improve overall HA responsivness if you anticipate your units being offline.

## Home Assistant Entities and Control

Each indoor unit appears as a separate [`climate`](https://www.home-assistant.io/integrations/climate/) entity in Home Assistant. Entity names are derived from the name you created for the unit in KumoCloud. For example, `climate.bedroom` or `climate.living_room`. 

Entity attributes can tell you more about the current state of the indoor unit, as well as the unit's capabilities. Attributes may include the following:

- `hvac_modes`: The different modes of operation supported by the unit. For example: `off, cool, dry, heat, fan_only`.
- `min_temp`: The minimum temperature the unit can be set to. For example, `45`.
- `max_temp`: The maximum temperature the unit can be set to: For exampoe, `95`.
- `fan_modes`: The different modes supported for the fan. This corresponds to fan speed, and noise. For example: `superQuiet, quiet, low, powerful, superPowerful, auto`. 
- `swing_modes`: The different modes supported for the fan vanes. For example: `horizontal, midhorizontal, midpoint, midvertical, auto, swing`.
- `current_temperature`: The current ambient temperature, as sensed by the indoor unit. For example, `73`.
- `temperature`: The target temperature. For example, `77`.
- `fan_mode`: The current mode for the fan. For example, `auto`.
- `hvac_action`: The current mode for the unit. For example, `cooling`.
- `swing_mode`: The current mode for the fan vanes. For example, `auto`.
- `filter_dirty`: Indicates whether the indoor unit's filter is dirty. For example, `false`. (Not sure how dirty the filter needs to be for this to read `true`, but we've never seen it ourselves.)
- `defrost`: Whether the unit is in defrost mode. For example, `false`.
- `friendly_name`: The KumoCloud name the indoor unit, usually the room. For example, `Bedroom`.

## Home Assistant Services and Control

Use the standard `climate` service calls to control or automate each unit. Available services may include:

- `climate.set_temperature`
- `climate.set_fan_mode`
- `climate.set_hvac_mode`
- `climate.set_swing_mode`
- `climate.turn_on`
- `climate.turn_off`

Specific support and behavior can vary, depending on the capabilities of your indoor unit.

## Home Assistant Sensors

Useful information from indoor units is published as attributes on the associated `climate` entity. It's easier to use these attributes if you convert them to sensors using [templates](https://community.home-assistant.io/t/using-attributes-in-lovelace/72672). For example, here's a sensor for the target temperature.

```yaml
# Get attribute of climate state in form of sensor
- platform: template
  sensors:
    thermostat_target_temperature_bedroom:
      friendly_name: "Target Temperature"
      unit_of_measurement: '°F'
      value_template: "{{ state_attr('climate.bedroom', 'temperature') }}"
```

## Support

For support, see the [thread](https://community.home-assistant.io/t/mitsubishi-kumo-cloud-integration/121508/128) on the Home Assistant community. For bugs or feature improvements, feel free to create a GitHub issue or pull request.

## Implementation Notes

- Native Python version ("kumo" platform) utilizes the [pykumo](https://github.com/dlarrick/pykumo) Python library.
- Design and implementation done in compliance with Home Assistant coding guidelines.
- Based on the [InComfort](https://github.com/royduin/home-assistant-incomfort) unofficial Home Assistant module as an example.
- Many thanks to the [KumoJS](https://github.com/sushilks/kumojs) Node.js module author, who did the hard work of reverse-engineering how to access the Wi-Fi interface locally.


## TODO

- Debugging for different types of indoor units.
- Explore if other local APIs are available to provide additional useful information (whether a unit is calling, etc.).
- Code cleanup. Code reviews welcome!
- Possible enhancement: allow setup and control of schedules and operating modes on the indoor unit itself.
- UI-guided setup in Home Assistant.
- Possibly work toward inclusion as an official Home Assistant integration.

## Status

- As of June 2019, the legacy module using KumoJS has been working fine for me for several months.
- As of July 20, 2019, the master branch contains a version compatible with the Climate 1.0 API (i.e. Home Assistant 0.96 and later). The `pre-0.96` branch contains the code compatible with older versions.
- In August 2019 I began work to implement and switch to a native Python module.
- As of December 2019 there are a handful of people (including myself) successfully using the native Python module in Home Assistant.
- As of January 2020, Kumo is available in the HACS default store, and I consider it feature-complete and stable.
- April 2020, updated this README documentation file.

## License

[MIT](LICENSE)
