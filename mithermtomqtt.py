#!/usr/bin/env python
import config
import logging
import logging.config
logging.config.dictConfig(config.LOGGING_CONFIG)
import argparse
import binascii
import os
import sys
import paho.mqtt.client as mqtt
import json
from bluepy import btle
import platform

client = mqtt.Client()

class ScanCb(btle.DefaultDelegate):

    def __init__(self, opts, cb):
        btle.DefaultDelegate.__init__(self)
        self.opts = opts
        self.cb = cb

    def handleDiscovery(self, dev, isNewDev, isNewData):
        name = None
        if not(isNewData or isNewDev):
            return
        if not dev.addr.lower().startswith(self.opts.filter.lower()):
            return
        if self.opts.debug:
            logging.debug('Device : %s, %d dBm' % (dev.addr , dev.rssi))
        for (sdid, desc, val) in dev.getScanData():
            if sdid in [8, 9]:
                if self.opts.debug:
                    logging.debug('\t' + desc + ' (' + str(sdid) +'): \'' +  val +  '\'')
                if not name and sdid == 9:
                    name = val
            else:
                if self.opts.debug:
                    logging.debug('\t' + desc + ' (' + str(sdid) +'): <' + val + '>')
                if sdid == 22:
                    logging.debug("%s (%s) %sdBm => %s"%(dev.addr, name, dev.rssi, val))
                    if len(val) != 30:
                        logging.debug("packet does not follows valid format: invalid length")
                        return
                    if val[:4] != '1a18':
                        logging.debug("packet does not follows valid format: invalid start")
                        return
                    if val[4:16] != dev.addr.lower().replace(':', ''):
                        logging.debug("packet does not follows valid format: mac mismatch")
                        return
                    temp = int(val[16:20], 16)/10
                    hum = int(val[20:22], 16)
                    bat_pcent = int(val[22:24], 16)
                    bat_mv = int(val[24:28], 16)
                    cnt = int(val[29], 16)
                    logging.debug("temp=%s hum=%s bat_pcent=%s bat_mv=%s cnt=%s"%(temp, hum, bat_pcent, bat_mv, cnt))
                    
                    data = {
                        'temp': temp,
                        'hum': hum,
                        'bat_pcent': bat_pcent,
                        'bat_mv': bat_mv,
                        'cnt': cnt,
                    }
        data['name'] = name
        data['addr'] = dev.addr
        data['origin'] = platform.node()
        self.cb(data)

def temp_data_cb(data):
    topic = config.MQTT_DEV_TOPIC % (data['addr'].lower().replace(':', ''))
    logging.debug("Publishing %s to %s "%(data, topic))
    try:
        client.publish(topic, payload=json.dumps(data))
    except Exception as e:
        logging.warning("Failed to publish to mqtt", exc_info=True)
    
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--hci', action='store', type=int, default=0,
                        help='Interface number for scan')
    parser.add_argument('-f', '--filter', action='store', type=str, default="a4:c1:38",
                        help='Interface number for scan')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable btle verbose mdoe')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Increase output verbosity')
    arg = parser.parse_args(sys.argv[1:])

    btle.Debugging = arg.verbose


    client.enable_logger()
    # client.on_connect = on_connect
    # client.on_message = on_message
    # client.will_set("topic", payload=json.dumps({'action': 'daemon_died'}), qos=0, retain=False)
    client.connect(config.MQTT_SERVER[0], config.MQTT_SERVER[1], 600)
    client.loop_start()
    
    scanner = btle.Scanner(arg.hci).withDelegate(ScanCb(arg, temp_data_cb))
    devices = scanner.scan(0)

if __name__ == "__main__":
    main()
