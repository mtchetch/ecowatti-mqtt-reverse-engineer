import paho.mqtt.client as mqtt
import json
from pydantic import BaseModel
from datetime import datetime, timedelta

import serial
from datetime import datetime
import sys
from crc import Calculator, Configuration
import time

debugmode = False
# CRC Configuration
crc_config = Configuration(
    width=8,
    polynomial=0x81,
    init_value=0xe4,
    reverse_input=True,
    reverse_output=True,
    final_xor_value=0x98
)
crc_calculator = Calculator(crc_config)

# Packet parameters
length = "07"
sender = "FD"  # or "FE"
start_packet_id = 0x40 #40 for main unit
end_packet_id = 0x7F #7F for main unit

# Define ser globally
ser = None

class Config(BaseModel):
    mqtt_client_name: str
    mqtt_topic_header: str
    mqtt_host: str
    mqtt_port: int
    mqtt_timeout: int
    mqtt_username: str
    mqtt_password: str
    serial_device: str
    serial_timeout: int
    config_update_interval: int
    sensor_update_interval: int


def parse_config() -> Config:
    with open("config.json", "rb") as cfg_file:
        json_data = json.load(cfg_file)

    return Config(**json_data)


def on_connect(client, userdata, flags, rc):
    # callback for CONNACK response from the server.
    print("Connected with result code "+str(rc))

# callback for received messages


def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))

def send_data_packet(packet_data):
    """
    Send a data packet over a serial connection.

    Args:
    ser (serial.Serial): The serial connection.
    packet_data (str): The data packet in hex format as a string.

    Returns:
    bool: True if the packet was sent successfully, False otherwise.
    """
    global ser  # Declare ser as global
    try:
        # Convert the hex string to bytes
        packet_bytes = bytes.fromhex(packet_data)

        # Calculate CRC checksum
        crc_checksum = crc_calculator.checksum(packet_bytes)
        packet_bytes += crc_checksum.to_bytes(1, byteorder='little')

        # Send the packet over the serial connection
        ser.write(packet_bytes)
        if debugmode:
            print("sent the packet:" + packet_bytes.hex())

        return True
    except Exception as e:
        print(f"Error sending data packet: {e}")
    return False


def process_packet(packet):
    if len(packet) < 6:
        return None
    communicator_id = packet[2:4]
    packet_size = int(packet[4:6], 16)
    if packet_size == 0:
        return None  # Skip printing if packet size is zero
    packet_data = packet[6:6 + 2*packet_size]
    return {
        'id': communicator_id,
        'size': packet_size,
        'data': packet_data
    }

def read_result():
    buffer = ''
    start_time = time.time()  # Record the start time
    sensor_result = []
    global ser  # Declare ser as global
    while True:
        # Check if 2 seconds have passed
        if time.time() - start_time > 2.5:
            break

        # Read data in chunks and convert to hex
        reading = ser.read(100).hex().upper()
        buffer += reading

        # Process the buffer
        while 'A3' in buffer and len(buffer) >= 6:
            start_index = buffer.index('A3')
            if len(buffer) > start_index + 6:  # Check for enough length for size and ID
                packet_size = int(buffer[start_index+4:start_index+6], 16)
                end_index = start_index + 6 + 2 * packet_size
                if len(buffer) >= end_index:  # Check if full packet data is available
                    packet = buffer[start_index:end_index]
                    processed_packet = process_packet(packet)
                    if processed_packet:
                        #If packet contains measurement data - starts with A28083
                        if processed_packet['data'].startswith("A28083"):
                            # Convert the relevant part of packet data from hex string to bytes
                            data_bytes = bytes.fromhex(processed_packet['data'])
                            # Interpret the bytes as an integer
                            int_value = int.from_bytes(data_bytes[6:8], "little", signed=True) / 10
                            if debugmode:
                                print(f"Sensor data {int_value}")
                            #The value of 3276.7 means a sensor is not connected and should be replaced with None
                            if int_value != 3276.7:
                                sensor_result.append(int_value)
                        sys.stdout.flush()
                    buffer = buffer[end_index:]
                else:
                    break
            else:
                break
    #print(sensor_result)
    if len(sensor_result) > 0:
        sensor_result = round(sum(sensor_result) / len(sensor_result), 1)
    else:
        sensor_result = None
    return sensor_result

def get_sensor_data(memory_location):
    global ser  # Declare ser as global
    min_value = -40
    max_value = 100
    attempt = 0
    while attempt < 3:
        for packet_id in range(start_packet_id, end_packet_id + 1):
            # Constructing the packet
            packet = "A3{}{}A28181{}AA{}".format(sender, length, format(packet_id, '02X'), memory_location)
            # Send the packet
            send_data_packet(packet)
            # Wait for 250ms between packets for more stable results
            time.sleep(0.250)

        result = read_result()

        # Check if result is within predefined range
        if result is not None and min_value <= result <= max_value:
            return result

        # Increment attempt counter and retry
        attempt += 1
        #print(f"Attempt {attempt}: Invalid data received, retrying...")

    # Return None if valid data is not received after 3 attempts
    return None


def main():
    config = parse_config()
    global ser  # Declare ser as global
    client = mqtt.Client(config.mqtt_client_name)
    client.on_connect = on_connect
    client.on_message = on_message

    client.username_pw_set(config.mqtt_username, config.mqtt_password)
    client.connect(config.mqtt_host, config.mqtt_port, config.mqtt_timeout)

    client.loop_start()

    # Initialize serial communication
    ser = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=1)


    # Temperature sensor information
    #Memory location - name - description
    temp_sensors = {
        "00": ("T1", "Lämmityspiirin menovesi"),
        "01": ("T2", "Ulkolämpötila"),
        # "02": ("T3", "Muu lämmönlähde"),  # Uncomment if needed
        "03": ("T4", "Lataussäiliön alaosa"),
        "04": ("T5", "Lataussäiliön yläosa"),
        "05": ("T6", "Lämmityspiirien paluuvesi"),
        # "06": ("T7", "Lämmityspiirin 2 menovesi"),  # Uncomment if needed
        # "07": ("T8", "Aurinkojärjestelmän varaajan anturi"),
        "08": ("T9", "Käyttövesi"),
        # "09": ("T10", "Aurinkokeräimet")  # Uncomment if needed
        "13": ("Target", "Pyyntilämpö")
    }
    # Current sensor information
    current_sensors = {
        "0C": ("L1", "Current Sensor L1"),
        "0D": ("L2", "Current Sensor L2"),
        "0E": ("L3", "Current Sensor L3")
    }
    sensor_data = {}

    last_config_update = datetime.now()
    last_sensor_update = datetime.now()

    while True:
        if datetime.now() > last_config_update + timedelta(minutes=config.config_update_interval):
            # Update temperature sensors config
            print("updating temperature sensors config")
            for sensor_id, (name, description) in temp_sensors.items():
                topic = f"{config.mqtt_topic_header}/sensor-{name}/config"
                payload = {
                    "unique_id": f"sensor-{name}",
                    "device_class": "temperature",
                    "name": f"{name} - {description}",
                    "state_topic": f"{config.mqtt_topic_header}/sensor-{name}/state",
                    "unit_of_measurement": "°C",
                    "icon": "hass:thermometer",
                    "value_template": "{{ value_json.value }}"
                }

                client.publish(topic, json.dumps(payload))
            print("updating current sensors config")
            # Update current sensors
            for sensor_id, (name, description) in current_sensors.items():
                topic = f"{config.mqtt_topic_header}/sensor-{name}/config"
                payload = {
                    "unique_id": f"sensor-{name}",
                    "device_class": "current",
                    "name": f"{name} - {description}",
                    "state_topic": f"{config.mqtt_topic_header}/sensor-{name}/state",
                    "unit_of_measurement": "A",
                    "icon": "hass:flash",
                    "value_template": "{{ value_json.value }}"
                }

                client.publish(topic, json.dumps(payload))

            last_config_update = datetime.now()

        if datetime.now() > last_sensor_update + timedelta(minutes=config.sensor_update_interval):
        # Update data for temperature sensors
            for sensor_id, (name, _) in temp_sensors.items():
                sensor_data[name] = get_sensor_data(sensor_id)
                topic = f"{config.mqtt_topic_header}/sensor-{name}/state"
                data = {'value': sensor_data[name]}  # Assuming temperature data
                client.publish(topic, json.dumps(data))

            # Update data for current sensors
            for sensor_id, (name, _) in current_sensors.items():
                sensor_data[name] = get_sensor_data(sensor_id)
                topic = f"{config.mqtt_topic_header}/sensor-{name}/state"
                data = {'value': sensor_data[name]}  # Assuming current data in amperes
                client.publish(topic, json.dumps(data))

            last_sensor_update = datetime.now()
if __name__ == "__main__":
    main()
