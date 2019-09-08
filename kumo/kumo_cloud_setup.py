#!/usr/bin/env python3
""" Fetch required info from KumoCloud and produce HomeAssistant configuration
    section for the units found there
"""

import json
import getpass
import requests

def main():
    """ Entry point
    """
    username = input("KumoCloud username:")
    password = getpass.getpass(prompt="KumoCloud password:")

    url = "https://geo-c.kumocloud.com/login"
    headers = {'Accept': 'application/json, text/plain, */*',
               'Accept-Encoding': 'gzip, deflate, br',
               'Accept-Language': 'en-US,en',
               'Content-Type': 'application/json' }
    body = '{"username":"%s","password":"%s","appVersion":"2.2.0"}' % (username, password)
    response = requests.post(url, headers=headers, data=body)

    KumoDict = response.json()

    print("# Configuration for Kumo units '%s' for %s" %
          (KumoDict[2]['label'],KumoDict[0]['username']))
    print("climate:")
    for child in KumoDict[2]['children']:
        for serial, zone in child['zoneTable'].items():
            print('  - platform: kumo')
            print('    name: "%s"' % zone['label'])
            print('    address: "%s"' % zone['address'])
            print('    config: \'{"password": "%s", "crypto_serial":"%s"}\'' %
                  (zone['password'], zone['cryptoSerial']))
 
if __name__ == '__main__':
    main()
