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

def send_data_packet(ser, packet_data):
    """
    Send a data packet over a serial connection.

    Args:
    ser (serial.Serial): The serial connection.
    packet_data (str): The data packet in hex format as a string.

    Returns:
    bool: True if the packet was sent successfully, False otherwise.
    """
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

def read_from_port(ser):
    buffer = ''
    while True:
        # Read data in chunks and convert to hex
        reading = ser.read(100).hex().upper()
        buffer += reading

        # Process when we have at least the smallest valid packet ('A3' + 4 characters)
        while 'A3' in buffer and len(buffer) >= 6:
            start_index = buffer.index('A3')
            if len(buffer) > start_index + 6:  # Check for enough length for size and ID
                packet_size = int(buffer[start_index+4:start_index+6], 16)
                end_index = start_index + 6 + 2 * packet_size
                if len(buffer) >= end_index:  # Check if full packet data is available
                    packet = buffer[start_index:end_index]
                    processed_packet = process_packet(packet)
                    if processed_packet:
                        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        #test if a packet is a request and create a variable for adding memory location processing for requests
                        sensor_memory_address = ""
                        if processed_packet['data'].startswith("A28181"):
                            sensor_memory_address = ", Sensor memory address is " + processed_packet['data'][-4:-2]
                        print(f"{current_datetime} - ID: {processed_packet['id']}, Size: {processed_packet['size']}, Data: {processed_packet['data']}{sensor_memory_address}, Packet ID: {processed_packet['data'][6:8]}")
                        #If packet contains measurement data - starts with A28083
                        if processed_packet['data'].startswith("A28083"):
                            # Convert the relevant part of packet data from hex string to bytes
                            data_bytes = bytes.fromhex(processed_packet['data'])
                            # Interpret the bytes as an integer
                            int_value = int.from_bytes(data_bytes[6:8], "little", signed=True) / 10
                            print(f"Sensor data {int_value}")
                        sys.stdout.flush()
                    buffer = buffer[end_index:]
                else:
                    break
            else:
                break
def read_result(ser):
    buffer = ''
    start_time = time.time()  # Record the start time
    sensor_result = []

    while True:
        # Check if 2 seconds have passed
        if time.time() - start_time > 2:
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
    for packet_id in range(start_packet_id, end_packet_id + 1):
        # Constructing the packet
        #print("doing something")
        packet = "A3{}{}A28181{}AA{}".format(sender, length, format(packet_id, '02X'), memory_location)
        # Send the packet
        send_data_packet(ser, packet)
        # Wait for 250ms between packets for more stable results
        time.sleep(0.250)
    return read_result(ser)

try:
    # Open serial port with baudrate set to 115200
    ser = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=1)
    
    # T1 = get_sensor_data("00")
    # print(T1)
    # T2 = get_sensor_data("01")
    # print(T2)
    # #T3 = get_sensor_data("02")
    # #print(T3)
    # T4 = get_sensor_data("03")
    # print(T4)
    # T5 = get_sensor_data("04")
    # print(T5)
    # T6 = get_sensor_data("05")
    # print(T6)
    # #T7 = get_sensor_data("06")
    # #print(T7)
    # T8 = get_sensor_data("07")
    # print(T8)
    # T9 = get_sensor_data("08")
    # print(T9)
    # #T10 = get_sensor_data("09")
    # #print(T10)
    
    # L1 = get_sensor_data("0C")
    # print(L1) 
    # L2 = get_sensor_data("0D")
    # print(L2) 
    # L3 = get_sensor_data("0E")
    # print(L3) 

    # Continuously read and process data
    read_from_port(ser)

except serial.SerialException as e:
    print(f"Error: {e}")
