# Mitsubishi Kumo Cloud

[![Type](https://img.shields.io/badge/Type-Custom_Component-orange.svg)](https://github.com/dlarrick/hass-kumo) [![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)


# **Current Status PLEASE READ**

## **Quick Update (December 31, 2025)**

[EnumC](https://github.com/EnumC) has discovered the missing unit password field in a WebSocket response. See discussion under [#58](https://github.com/dlarrick/pykumo/issues/58). We're not out of the woods yet, but this is promising.

## Breakage announcement (June 6, 2025)

The release of the Mitsubishi Comfort app and its Kumo v3 server-side API has broken the ability for some users to retrieve necessary information from the Kumo server APIs. New users, or anyone whose indoor units change in any way (add/replace hardware, change IP address assignment, change Mitsubishi password) will be unable to use the hass-kumo integration. Suggested options:

1. *It's working fine! Do I need to change anything?* No, not as of this writing. I (author/maintainer of hass-kumo and pykumo) am in this situation. But **DON'T CHANGE** your IP address assignment or reset your adapters, or reset your Mitsubishi password. In fact I recommend staying out of the Comfort app entirely.
2. *Why did this happen? I need reliable local control!* Yeah, you're not wrong. Those who want to avoid the cloud entirely for their HVAC might want to check out the [ESP32](https://github.com/dlarrick/hass-kumo/issues/190) route instead of continuing to use the Kumo adapters. **Note** if someone has a better link to a canonical ESP32 writeup, drop me a note and I'll update this link. TBH if & when my units stop working, and we haven't fixed hass-kumo, this is what I'll do.
3. *Is there a way for HomeAssistant to use the cloud service from instead?* Yes! [J. Justin Wilson](https://github.com/jjustinwilson/comfort_HA) has stepped up and made a Home Assistant integration that uses the new cloud API directly. This is a brand new integration so there are sure to be issues, and of course cloud control will never be as snappy as local. But folks are successfully using it. Kudos!
4. *I like the current software! What can we do?* Yeah, me too. I have two remaining thoughts on possible ways to restore local control, and also I think long term it would be nice to retrofit cloud control into pykumo as a fallback. I've made 3 tickets over there, and PRs or discussion are more than welcome.
   - Implement cloud-based control in pykumo via V3 API: https://github.com/dlarrick/pykumo/issues/56
   - Investigate if the missing unit password can be derived from things we know: https://github.com/dlarrick/pykumo/issues/57
   - Investigate if the missing unit password is indeed available from the v3 API and we just haven't found it: https://github.com/dlarrick/pykumo/issues/58

----------------------

> [!CAUTION]
> ## New Mitsubish Comfort app breakage
>
> **TL;DR: Mitsubishi has changed their cloud components. DO NOT uninstall/reinstall or reconfigure the Kumo integration or you will lose access.**
>
> Adapting to these changes is a goal, but PyKumo / Hass-Kumo is a side / weekend project for the primary maintainer. Assistance greatly appreciated! Leave a comment in one of the 3 PyKumo tickets listed below if you're able & willing to help. Many thanks to the folks who have stepped up thus far.
>
> ### Summary
> - Mitsubishi rolled out a new Comfort app (replacing Kumo Cloud) and corresponding server-side cloud infrastructure (Kumo V3 API). It appears there's a new firmware version for the indoor unit WiFi adapters as well.
> - The old Kumo server-side infrastructure still exists, at least for now, but it appears its database is not being updated
> - The new server-side cloud infrastructure appears to not present all the information needed to achieve access to the indoor units' local API that PyKumo depends on.
> - The local indoor unit API has not changed substantially and still works OK for some users whose local configuration has not changed.
> - Anyone who loses their hass-kumo local configuration, or adds indoor units, or whose indoor units' IP address changes, will be unable to access those units via pykumo/hass-kumo.
> - It's possible the old solution could stop working at any time, especially if Mitsubishi intends to fully abandon the use of local control.
>
> Also see the long discussion in [189](https://github.com/dlarrick/hass-kumo/issues/189)
>
> ### Unknowns
> - Can we get access to the last piece of missing information (unit password) in some way?
> - Are there changes to the local API that we can take advantage of?
>
> ### Plan
> - See the 3 PyKumo tickets:
>  - Implement cloud-based control in pykumo via V3 API: https://github.com/dlarrick/pykumo/issues/56
>  - Investigate if the missing unit password can be derived from things we know: https://github.com/dlarrick/pykumo/issues/57
>  - Investigate if the missing unit password is indeed available from the v3 API and we just haven't found it: https://github.com/dlarrick/pykumo/issues/58

--------------------------------------

## Home Assistant component
Mitubishi Kumo Cloud (Kumo for short) is a custom component for Home Assistant that allows you to control Mitsubishi mini-split units that are connected to the Mitsubishi KumoCloud service.

- For US (North American) market mini-splits with a KumoCloud WiFi interface (for example, PAC-USWHS002-WF-2).
- Implements standard Home Assistant [`climate`](https://www.home-assistant.io/integrations/climate/) entities.
- Supports reading and setting the mode (heat/cool/etc.), setpoint, fan speed, and vane swing.
- Supports fully local control, except for initial setup. (See `prefer_cache` in Configuration for details.)
- Supports displaying the Outdoor Temperature for Kumo Station.
- Supports displaying Wi-Fi signal strength (RSSI) of each unit (disabled by default).

## Installation

**Note**: Kumo is not included in Home Assistant as an official integration. Instead, the recommended way to install it is through the [Home Assistant Community Store](https://hacs.xyz/docs/setup/download/) (HACS) add-in.

You can install Kumo in one of two ways.

- **Automatic Installation.** Kumo is available in the HACS default store. Search for "Kumo" in the Integrations panel, and then click the **Mitsubishi Kumo Cloud** item in the results. Click the Install link, and then restart Home Assistant.
- **Manual Installation.** To control your installation yourself, download the hass-kumo repo, and then copy the `custom_components/kumo` directory into a corresponding `custom_components/kumo` within your Home Assistant configuration directory. Then restart Home Assistant.

We recommend using the HACS installation method, which makes future updates to Kumo easy to track and install. Click the HACS badge above for details on installing and using HACS.

## Configuration

Configure Kumo using the Home Assistant user interface.

1. In Home Assistant, go to Settings ➤ Devices & Services ➤ Integrations, and click **➕ Add Integration**.
2. Search for "Kumo" and select the **Kumo** item.
3. When prompted, enter your KumoCloud username (email address) and password.
4. You can also enable the `prefer_cache` setting in this dialog. See details below.
5. Click **Submit** to enable the integration and begin device discovery.
6. Once discovery is complete:
   - You'll be prompted to assign a room (Area in Home Assistant terminology) for all discovered devices.
   - You _might_ be prompted to assign IP addresses for devices where Kumo didn’t receive an IP address from the KumoCloud service. See details below.

Once the Kumo integration is added, you'll have a card for it on the Integrations page. (Integrations are sorted by name, and the name of this integration is "Kumo".) The Kumo integration card includes a "Configure" link. The configuration panel lets you change the default timeout values for device connections, or update IP addresses for configured units. **Important:** New values don't take effect until you restart Home Assistant.

- `prefer_cache`, if set, controls whether to contact the KumoCloud servers on startup, or to prefer locally cached info on how to communicate with the indoor units. Default is `false`, to accommodate changing unit availability or DHCP leases. If your configuration is static (including the units' IP addresses on your LAN), it's safe to set this to `true`. This will allow you to control your system even if KumoCloud or your Internet connection suffer an outage. The cache is in `config/kumo_cache.json`.
- `connect_timeout` and `response_timeout`, if set, control network timeouts for each command or status poll from the indoor unit(s). Increase these numbers if you see frequent log messages about timeouts. Decrease these numbers to improve overall Home Assistant responsiveness if you anticipate your units being offline.

### IP Addresses

Kumo accesses your indoor units directly on the local LAN using their IP address, discovered at setup time (or at Home Assistant startup, if `prefer_cache` is False) from the Kumo Cloud web service. It is **strongly** recommended that you set a fixed IP address for your indoor unit(s), using something like a DHCP reservation.

In some cases, Kumo is unable to retrieve the indoor units' addresses from the Kumo Cloud web service. If this happens, you will be prompted to supply the address(es) as part of setup. To obtain these addresses, you will need to find the MAC address of each indoor unit; it should be on a sticker on the outside of the WiFi interface.

Given each MAC address, go into your WiFi router's admin interface and write down the IP address assigned to each one. It should be in dotted-quad notation e.g. `192.168.1.141`. **Note:** Depending on your router, this is likely to be where you can permanently reserve an IP address, which is **highly recommended**

For example, for an EERO system, go to `Network Settings / Advanced settings / Reservations and Port Forwarding / Add a reservation`. Then select the device and click save. If you changed the IP address, just restart that indoor unit and it’ll come back with the IP you reserved for it.

Back in Home Assistant, it will show you the MAC address and ask you for the corresponding IP address. Use what you wrote down to fill in this info.

It's also possible to edit the IP address of existing units through the UI using the **Configure** link on Kumo's tile in the Integrations section of Settings.

If you continue to have connection issues with your units, try using the Kumo Cloud app to force a refresh of your devices with KumoCloud. Quoting @rhasselbaum's [Gist](https://gist.github.com/rhasselbaum/2e528ca6efc0c8adc765c0117d2c9389):
> So back into **Installer Settings**. I clicked on the unit there, and under **Advanced**, there is a **Refresh Settings** option. Bingo! This resynchronizes the state of the device with Kumo Cloud, apparently. Clicked that, restarted HA again, and finally, it shows up!

## Troubleshooting
### Unable to set up / indoor units not found
This integration retrieves critical information (such as IP address and local security keys) from the Kumo Cloud service run by Mitsubishi. This service seems to take a while (even up to several days) to update after network changes or on a fresh install. If you're impatient or the integration is still not setting up after several days, try the suggestions under the "IP Addresses" section above.

### WiFi
The most common cause of flaky behavior is weak WiFi signal at the indoor unit. Try measuring WiFi strength (2.4 GHz only) with a phone app. Also try repositioning the Mitsubishi WiFi adapter within the unit, positioning it close to the plastic exterior rather than metal interior components.

### API errors
In early 2023 Mitsubishi appears to have made some change that makes the WiFi adapter less reliable. My educated guess is that it has a memory leak. See [Issue 105](https://github.com/dlarrick/hass-kumo/issues/105) in the hass-kumo repository for discussion.

As a result of this issue, if you are seeing `serializer_error` or (especially) `__no_memory` errors consistently in your HA logs, it's likely that your indoor unit needs power-cycling. Unfortunately the easiest way is probably at the circuit breaker for the entire mini-split system.

## Home Assistant Entities and Control

Each indoor unit appears as a separate [`climate`](https://www.home-assistant.io/integrations/climate/) entity in Home Assistant. Entity names are derived from the name you created for the unit in KumoCloud. For example, `climate.bedroom` or `climate.living_room`.

Entity attributes can tell you more about the current state of the indoor unit, as well as the unit's capabilities. Attributes can include the following:

- `hvac_modes`: The different modes of operation supported by the unit. For example: `off, cool, dry, heat, fan_only`.
- `min_temp`: The minimum temperature the unit can be set to. For example, `45`.
- `max_temp`: The maximum temperature the unit can be set to: For example, `95`.
- `fan_modes`: The different modes supported for the fan. This corresponds to fan speed, and noise. For example: `superQuiet, quiet, low, powerful, superPowerful, auto`.
- `swing_modes`: The different modes supported for the fan vanes. For example: `horizontal, midhorizontal, midpoint, midvertical, vertical, auto, swing`.
- `current_temperature`: The current ambient temperature, as sensed by the indoor unit. For example, `73`.
- `temperature`: The target temperature. For example, `77`.
- `fan_mode`: The current mode for the fan. For example, `auto`.
- `hvac_action`: The current mode for the unit. For example, `cooling`.
- `swing_mode`: The current mode for the fan vanes. For example, `auto`.
- `filter_dirty`: Indicates whether the indoor unit's filter is dirty. For example, `false`. (Not sure how dirty the filter needs to be for this to read `true`, but we've never seen it ourselves.)
- `defrost`: Whether the unit is in defrost mode. For example, `false`.
- `friendly_name`: The KumoCloud name for the indoor unit, usually the room. For example, `Bedroom`.

## Home Assistant Services and Control

Use the standard `climate` service calls to control or automate each unit. Available services can include:

- `climate.set_temperature`
- `climate.set_fan_mode`
- `climate.set_hvac_mode`
- `climate.set_swing_mode`
- `climate.turn_off`

Specific support and behavior can vary, depending on the capabilities of your indoor unit.

## Home Assistant Sensors

Useful information from indoor units is provided as attributes on the associated `climate` entity. This data can be turned into sensors in one of two ways: sensors provided by the integration, or template sensors from the main entity's attributes.

### Sensors
By default a sensor for current temperature is enabled. It's possible to enable sensors for a few other values, if available:
- WiFi RSSI signal strength
- Current Humidity (provided by a linked PAC-USWHS003 or MHK2 device)
- PAC sensor battery level
- Sensor RSSI signal strength
- Outdoor temperature (provided by Kumo Station)

To enable these optional sensors, click on the Kumo tile in Settings -> Devices and Services, go into the Devices section, click on the indoor unit (or Kumo Station) and enable them under Sensors.

**Note** that you will need to restart HmomeAssistant after enabling a new sensor type, due to [Issue 120](https://github.com/dlarrick/hass-kumo/issues/120).

### Template Sensors

For additional attributes not covered above, or if you require more customization, you can convert attributes to sensors using [templates](https://community.home-assistant.io/t/using-attributes-in-lovelace/72672). For example, here's a simple sensor for the target temperature.

```yaml
# Get attribute of climate state in form of sensor
- platform: template
  sensors:
    thermostat_target_temperature_bedroom:
      friendly_name: "Target Temperature"
      unit_of_measurement: '°F'
      value_template: "{{ state_attr('climate.bedroom', 'temperature') }}"
```

Here's a more complex template that sets additional entity attributes and takes certain error conditions into consideration:

```yaml
- platform: template
  sensors:
    temperature_bedroom_current:
      friendly_name: "Bedroom Temperature"
      device_class: temperature
      unit_of_measurement: "°F"
      value_template: >-
        {%- if state_attr('climate.bedroom', 'current_temperature') != None %}
          {{state_attr('climate.bedroom','current_temperature') | float }}
        {%- endif %}
      availability_template: >-
        {%- if not is_state('climate.bedroom', 'unavailable') %}
          true
        {%- endif %}
```

This template was suggested in the community thread (see Support, below). It can be especially useful if, for example, you're experiencing connection issues with the integration due to problems with your wireless network.

## Support

For support, see the [Kumo integration thread](https://community.home-assistant.io/t/mitsubishi-kumo-cloud-integration/121508) on the Home Assistant community. (To skip early development discussions, start with [the official availability announcement](https://community.home-assistant.io/t/mitsubishi-kumo-cloud-integration/121508/128) in that thread.)

For bugs or feature improvements, feel free to create a GitHub issue or pull request.

## Implementation Notes

- Native Python version ("kumo" platform) utilizes the [pykumo](https://github.com/dlarrick/pykumo) Python library.
- Design and implementation done in compliance with Home Assistant coding guidelines.
- Based on the [InComfort](https://github.com/royduin/home-assistant-incomfort) unofficial Home Assistant module as an example.
- Many thanks to the [KumoJS](https://github.com/sushilks/kumojs) Node.js module author, who did the hard work of reverse-engineering how to access the Wi-Fi interface locally.

## TODO

- Debugging for different types of indoor units.
- Explore if other local APIs are available to provide additional useful information (whether a unit is calling, etc.).
- Code cleanup. Code reviews welcome!
- Implement `climate.turn_on` action (service).
- Possible enhancement: allow setup and control of schedules and operating modes on the indoor unit itself.
- Possibly work toward inclusion as an official Home Assistant integration.

## Status

- As of June 2019, the legacy module using KumoJS has been working fine for me for several months.
- As of July 20, 2019, the master branch contains a version compatible with the Climate 1.0 API (i.e. Home Assistant 0.96 and later). The `pre-0.96` branch contains the code compatible with older versions.
- In August 2019 I began work to implement and switch to a native Python module.
- As of December 2019 there are a handful of people (including myself) successfully using the native Python module in Home Assistant.
- As of January 2020, Kumo is available in the HACS default store, and I consider it feature-complete and stable.
- April 2020, updated this README documentation file.
- July 2022, updated this README file again for changed Home Assistant user interface elements, and other clarifications.

## License

[MIT](LICENSE)
