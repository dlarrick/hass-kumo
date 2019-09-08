# Home Assistant module interfacing with KumoJS
Home Assistant control of Mitsubishi mini-split units

- For US (North American) market mini-splits with KumoCloud WiFi interface
- Implements standard Home Assistant climate entities
- Supports Mode (heat/cool etc.), setpoint, fan speed, and vane swing setting
- Legacy version ("kumojs" platform) interfaces with [KumoJS](https://github.com/sushilks/kumojs) Node.js module, which actually communicates with the KumoCloud adapter.
  - This version is working fine for several people
  - You should have KumoJS running as a server on a locally-accessible machine.
  - Note: KumoJS works fine under Node.js on Raspbian Buster
  - This version will never be accepted into Home Assistant because it does
    not meet the architectural guidelines
- New version ("kumo" platform) utilizes [pykumo](https://github.com/dlarrick/pykumo) Python library
  - Currently experimental, under development (August 2019)
  - Design & implementation done to hopefully be accepted into Home Assistant natively
- Both are based on the [InComfort](https://github.com/royduin/home-assistant-incomfort) unofficial Home Assistant module as an example

## Installation (Native Python version)
- Put the [pykumo](https://github.com/dlarrick/pykumo) library where HA can find it. On my install that's `/srv/homeassistant/lib/python3.7/site-packages`. Note: eventually we'll submit this library to PyPI and won't need this step.
- Put the `kumo` directory from here in `custom_components/kumo` within your configuration directory.
- Run the `kumo_cloud_setup.py` script, which will prompt for your KumoCloud username and password and
  print out entries for your configuration.yaml

## TODO (New version)
- Debugging
- Cleanup and submission of pykumo module to PyPI
- Auto creation of climate entities from KumoCloud account
- Provide some sensors (current temp, filterDirty, etc.)
- Explore if other local APIs are available to provide additional useful information (remote sensor readings, whether unit is calling, etc.)
- Use async web requests to prevent HA warnings "Updating state for [KumoThermostat] took 0.468 seconds. Please report platform to the developers at https://goo.gl/Nvioub"
- Code cleanup. Code reviews welcome!

## Status
- As of June 2019, this module has been working fine for me for several months. I have no current plans to implement the TODO list but will accept patches.
- As of July 20, 2019, the master branch contains a version compatible with the Climate 1.0 API (i.e. Home Assistant 0.96 and later). The `pre-0.96` branch contains the code compatible with older versions.
- In August 2019 I began work to implement and switch to a native Python module.

## License
[MIT](LICENSE)
