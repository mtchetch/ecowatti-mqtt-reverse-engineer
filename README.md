# ecowatti-mqtt-reverse-engineer

Integrate Jäspi Ecowatti boiler temperatures to Home Assistant using MQTT and RS-485 reverse engineering

This is a fork of https://github.com/lemanjo/ecowatti2mqtt

## Credits

https://github.com/lemanjo

https://bbs.io-tech.fi/threads/ecowatti-reverse-engineering.322217/

https://lampopumput.info/foorumi/threads/j%C3%A4spi-ecowatti-homeassistant-tuki.35121/

Special thanks to: Lema and Maz

## Intro

I am rather new to hardware hackering and this project has been a challenge. The Ecowatti library built by Lemanjo did not work for me so there was no other way as to figure out how everything worked and try to find a solution. It has been a frustrating journey since there were no tools available to ease the development process.

I rolled my own rudimentary Python based traffic analyzer based on the information provided by Lema and Maz on the forums. This can be used as a starting point for othe RS-485 based work in the future.
## How does it work

The Ecowatti is an electric hybrid boiler system made by the Finnish company Jäspi. It is (Or at least the version I am using) from around 2010. The electric boiler is of a hybrid type where it is possible to hook up water heatpumps and solar accumulators to it as an alternative source of heating energy.


The model I have and that the work is based on is the Jäspi Ecowatti K. The model is from around 2010 and it has the control electronics marked "Eco M09". The control board uses its own protocol and is not based on modbus even though it has similarities.
### Electronics

My system consists of the boiler with the control card. All the sensors and control mechatronics are connected to the control card. The boiler unit has a control panel that is hooked up to the RS-485 serial bus and I have an additional room unit that is located in side the house does room temperature measurement and compensation and is also hooked up to the RS485 bus.

A Raspberry Pi 3B is connected to the control card with a USB RS-485 adapter.

On the control card there are terminals used for connecting room units marked with the pin numbers:
```
51 = GND
52 = RS485/B
53 = RS485/A
54 = +5DC - left unconnected
```

During development an additional computer was used to monitor the traffic on the serial bus because RS-485 is half duplex and cannot transmit and read at the same time.

## What you need to do to make it work
- Get yourself a Raspberry Pi or a computer that can run an RS-485 serial interface. Linux is probably a good choice but python works on Windows too.
- Get a USB to RS-485 adapter with reasonable quality
- Connect the serial wiring to the Ecowatti control board. **Do this when the board is powered off** for electric safety
- Install the required packages with pip
- Run the packet capture utility (packetcapture.py) with python and see that it captures traffic
- Figure out your CRC parameters and add them to both py files
- Figure out the packet ID range for your system and add the values to both py files
- Add a user to Home Assistant for mqtt
- Install Mosquito broker for Home Assistant (settings -> addons)
- Enable collecting data via MQTT (settings -> integrations)
- Configure the mqtt upload via config.json
- Run the ecowatti2mqtt.py with python either inside screen or via a service

## The communications protocol

### packet structure
The communication protocol is packet-based. When getting information like sensor readings a request packet must be sent over serial. 

Example of a request packet A3FD07A281816FAA13C0

The packet structure is:

```
A3 - static
FD - sender ID - In my case FD is the control panel unit on the boiler and FE is the room unit
07 - packet length - Calculated from the packet length - Debugging has shown requests are often 7 bytes long but can be 6 bytes.
A2 - static
81 81 - request type packets have these static bytes
6F - packet ID - This needs to match up to what the control card is expecting - see notes
AA - static
13 - sensor memory adress
C0 - calculated CRC that is added to the packet
```

At the moment the code is brute forcing the packet ID by sendind a request packet with all possible id numbers to get responses. This is very far from optimal and should be fixed. This causes instability when viewing the info on the control panels since the sensor readings are not matched and it is assumed that the sensor readings visible in the data stream after sendind all possible requests are the ones that were requested. The system will log incorrect data if the info screen is used while data collection is in progress.  ** Please help **

Example of a response packet: A32409A280834781AA0101B6


```
A3 - static
24 - sender ID - In my case FD is the control panel unit on the boiler and FE is the room unit 24 might be the control card but this sometimes changes
09 - packet length - Calculated from the packet length - Debugging has shown requests are often 9 bytes long but can be longer bytes.
A2 - static
80 83 - request type packets have these static bytes
47 - packet ID - This matches up with the request packet ID
81 - static
AA - static
01 01 - The data from the requested memory address
B6 - calculated CRC that is added to the packet
```

### Finding out the packet ID range

In order to capture packets and be able to generate them correctly you need to know the packet ID range

The packet ID is a looping value that generates an ID that is between the start and end value. It is incremented by one each time a packet is sent and resets to the start value when it exceeds the end value.

Run the packet capture script and go into the info menu. Monitor the packet ID numbers for sent packets and note the max and min values where it resets and starts over.

Add these to the python file config section

```
# Packet parameters
length = "07"
sender = "FD"  # or "FE"
start_packet_id = 0x40 #40 for main unit
end_packet_id = 0x7F #7F for main unit
```

These values will be used for generating packets and looping over all possibilities.

### Calculating CRC correctly - This is different on different Ecowatti models.

In order to figure out the CRC parameters for your system you need to capture some request packets. This is done by running the python script for capturing traffic and while it is capturing you need to activate the control panel on the Jäspi boiler unit and go to the info menu that displays sensor values.

You should get an output similar to this with plausible sensor values:


```
2024-01-13 16:14:28 - ID: 24, Size: 9, Data: A280048310041008EB, Packet ID: 83
206.4
2024-01-13 16:14:28 - ID: 24, Size: 9, Data: A280048318041008AF, Packet ID: 83
206.4
2024-01-13 16:14:28 - ID: FD, Size: 7, Data: A2818143A70206, Packet ID: 43
0.6
2024-01-13 16:14:28 - ID: 20, Size: 8, Data: A280824381A70125, Packet ID: 43
947.3
2024-01-13 16:14:28 - ID: FD, Size: 7, Data: A2818144A70034, Packet ID: 44
5.2
2024-01-13 16:14:29 - ID: 20, Size: 8, Data: A280824481A70061, Packet ID: 44
2483.2
2024-01-13 16:14:29 - ID: FD, Size: 7, Data: A2818145A70152, Packet ID: 45
8.2
2024-01-13 16:14:29 - ID: 20, Size: 8, Data: A280824581A700E8, Packet ID: 45
-614.4
2024-01-13 16:14:29 - ID: FD, Size: 6, Data: A2818046BD55, Packet ID: 46
0.0
2024-01-13 16:14:29 - ID: 20, Size: 8, Data: A280824681BD0223, Packet ID: 46
896.2
2024-01-13 16:14:29 - ID: 24, Size: 9, Data: A280048310041008EB, Packet ID: 83
206.4
2024-01-13 16:14:29 - ID: 24, Size: 9, Data: A280048318041008AF, Packet ID: 83
206.4
2024-01-13 16:14:30 - ID: FE, Size: 8, Data: A28103C200E90081, Packet ID: C2
-3251.2
2024-01-13 16:14:30 - ID: 24, Size: 9, Data: A280048310041008EB, Packet ID: 83
206.4
2024-01-13 16:14:30 - ID: FD, Size: 7, Data: A2818147AA00C9, Packet ID: 47
-5.5
2024-01-13 16:14:30 - ID: 24, Size: 9, Data: A280834781AA0101B6, Packet ID: 47
25.7
2024-01-13 16:14:30 - ID: FD, Size: 7, Data: A2818148AA0136, Packet ID: 48
5.4
2024-01-13 16:14:30 - ID: 24, Size: 9, Data: A280048318041008AF, Packet ID: 83
206.4
2024-01-13 16:14:30 - ID: 24, Size: 9, Data: A280834881AABAFF91, Packet ID: 48
-7.0
2024-01-13 16:14:30 - ID: FD, Size: 7, Data: A2818149AA02AF, Packet ID: 49
-8.1
2024-01-13 16:14:30 - ID: 24, Size: 9, Data: A280834981AAFF7F29, Packet ID: 49
3276.7
2024-01-13 16:14:30 - ID: FD, Size: 7, Data: A281814AAA03FA, Packet ID: 4A
-0.6
2024-01-13 16:14:30 - ID: 24, Size: 9, Data: A280834A81AA6601A7, Packet ID: 4A
35.8
2024-01-13 16:14:30 - ID: FD, Size: 7, Data: A281814BAA049E, Packet ID: 4B
-9.8
2024-01-13 16:14:30 - ID: 24, Size: 9, Data: A280834B81AA6D0188, Packet ID: 4B
36.5
2024-01-13 16:14:30 - ID: FD, Size: 7, Data: A281814CAA05AD, Packet ID: 4C
-8.3
2024-01-13 16:14:30 - ID: 24, Size: 9, Data: A280834C81AAF100CD, Packet ID: 4C
24.1
```

Now pick out 4 request packets with the A28181 beginning and note them down.

Add A3FD07 to the beginning of each packet. 

```
2024-01-13 16:14:30 - ID: FD, Size: 7, Data: A281814CAA05AD, Packet ID: 4C
-8.3

becomes

A3FD07A281814CAA05AD
```

Now open the online tool reveng https://crc-reveng.septs.app/

Enter the command and fill in the 4 packets you captured. This will give you the CRC parameters needed for calculating the CRC bytes correctly


```
 reveng -s -w 8 A3FD07A2818179AA11F1 A3FD07A281807A91BC A3FD07A281807BA5FA A3FD07A281817CAA0C04
width=8  poly=0x81  init=0xe4  refin=true  refout=true  xorout=0x98  check=0xca  residue=0x89  name=(none)

```

Edit these in the python code to match up with what you got from reveng. The example shows how the values match up.


```
# CRC Configuration

crc_config = Configuration(
    width=8,
    polynomial=0x81,
    init_value=0xe4,
    reverse_input=True,
    reverse_output=True,
    final_xor_value=0x98
)
```



### Known memory addresses for sensors
|  |  |  |  |
| ---- | ---- | ---- | ---- |
| Memory address | sensor | Explanation | Huom |
| 00 | T1 | Menovesi / Heating circuit output |  |
| 01 | T2 | Ulkolämpötila / Outside temp |  |
| 02 | T3 | Muu lämmönlähde / Other heatsource |  |
| 03 | T4 | Lataussäiliön alaosa / Watertank bottom | Samassa kolossa T8  / Same place as T8 |
| 04 | T5 | Lataussäiliön yläosa / Watertank top |  |
| 05 | T6 | Lämmityspiirien paluuvesi / Heating circuit return |  |
| 06 | T7 | Lämmityspiiri 2 menovesi / Heating circuit 2 output |  |
| 07 | T8 | Aurinkojärjestelmän varaajan anturi / Solar heater | Samassa kolossa T4 / Same place as T4 |
| 08 | T9 | Käyttövesi / Hot water |  |
| 09 | T10 | Aurinkokeräimet / Solar accumulators |  |
| 0A |  |  |  |
| 0B |  |  |  |
| 0C | L1 | Virta L1 (A) / Whole house current sensor L1 |  |
| 0D | L2 | Virta L2 (A) / Whole house current sensor L2 |  |
| 0E | L3 | Virta L3 (A) / Whole house current sensor L3 |  |
| 13 | - | Requested flow temperature for circuit 1 |  |

## Making additional helper sensors in Home Assistant based on the collected data

It is helpful to have additional calculated sensors that can for instance show total energy usage and the difference for floor heating output and return temperatures

This can be done through settings -> Devices -> add device -> Template (helper)

For the floor heating delta you can input:


```
{{ states('sensor.t1_lammityspiirin_menovesi') | float - states('sensor.t6_lammityspiirien_paluuvesi') | float }}
```


## Requirements

Hardware capable of running python >3.8 and connecting to Serial interface.
Example Raspberry Pi + USB Serial dongle

Either Home Assistant with Mosquitto or separate MQTT broker instance.

## Config (The mqtt part)

| **Config**             	| **Type** 	| **Explanation**                                                                 	|
|------------------------	|----------	|---------------------------------------------------------------------------------	|
| mqtt_client_name       	| string   	| Client name for MQTT. Default: Ecowatti                                         	|
| mqtt_topic_header      	| string   	| Header for the MQTT topic. Default: homeassistant/sensor                        	|
| mqtt_host              	| string   	| Host ip for the MQTT Broker                                                     	|
| mqtt_port              	| int      	| Port for the MQTT Broker. Default: 1883                                         	|
| mqtt_timeout           	| int      	| Timeout in seconds for the MQTT communication. Default: 60                      	|
| mqtt_username          	| string   	| MQTT Username                                                                   	|
| mqtt_password          	| string   	| MQTT Password                                                                   	|
| serial_device          	| string   	| Device that is connected to the Ecowatti RS485 port. Example: /dev/ttyUSB0      	|
| serial_timeout         	| int      	| Serial communication timeout in seconds. Default: 1                             	|
| config_update_interval 	| int      	| Inteval in minutes in which the config topic is send. Default: 15               	|
| sensor_update_interval 	| int      	| Interval in minutes in which the temperatures are measured and sent. Default: 5 	|

## Installation

Download & unzip the repository

```
|> wget https://github.com/mtchetch/ecowatti-mqtt-reverse-engineer/archive/refs/heads/master.zip
|> unzip master.zip
```

Move to the downloaded directory

```
|> cd ecowatti-mqtt-reverse-engineer-master
```

Install the requirements

```
|> pip install -r requirements.txt
```

Create config file from the example config

```
|> cp config.example.json config.json
```

Edit the file with nano

```
|> nano config.json
```

Set permissions for the python file

```
|> sudo chmod +x ecowatti2mqtt.py
```

Check the full path for the file and store it

```
|> pwd
/home/pi/ecowatti2mqtt-master
```

Create service file to run the program after boot

```
|> sudo nano /lib/systemd/system/ecowatti.service
```

Copy paste following config. Note that you need to specify the path to the script based on your environment.
Save (CTRL+O) and exit (CTRL+X).

```
[Unit]
Description=Ecowatti2mqtt service
After=multi-user.target

[Service]
Type=idle
User=pi
WorkingDirectory=/home/pi/ecowatti2mqtt-master
ExecStart=/usr/bin/python3 /home/pi/ecowatti2mqtt-master/ecowatti2mqtt.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Set permissions for the service file

```
|> sudo chmod 644 /lib/systemd/system/ecowatti.service
```

Update the systemd configuration

```
|> sudo systemctl daemon-reload
|> sudo systemctl enable ecowatti.service
```

Now its all done and you can reboot the system.
After reboot, the program should load on the background and Home Assistant discovery should find the new mqtt sensors.

```
|> sudo reboot
```
