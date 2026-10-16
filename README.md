# SwarmNav

SwarmNav is a multi-robot exploration and navigation system built around a centralized server and multiple ESP32-based mobile robots.

The system allows multiple robots to connect over a local Wi-Fi network, communicate with a central FastAPI server through WebSockets, receive movement commands, report ultrasonic sensor information, maintain logical positions and orientations, and participate in autonomous exploration.

The project is designed as a modular foundation for cooperative multi-robot exploration, with support for robotic perception, mapping, navigation, and multi-robot operation.

---

## Overview

SwarmNav separates the robotic system into several layers:

```text
┌──────────────────────────────────────────────┐
│                 Web Dashboard                │
│        Monitoring • Manual • Auto            │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│              FastAPI Central Server          │
│                                              │
│  Robot Manager • State • Mapping             │
│  Autonomous Controller • WebSocket Server    │
└──────────────────────┬───────────────────────┘
                       │
                 Wi-Fi / WebSocket
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     ┌─────────┐  ┌─────────┐  ┌─────────┐
     │ Robot 1 │  │ Robot 2 │  │ Robot N │
     │  ESP32  │  │  ESP32  │  │  ESP32  │
     │         │  │         │  │         │
     │ Motors  │  │ Motors  │  │ Motors  │
     │Ultrasonic│ │Ultrasonic│ │Ultrasonic│
     └─────────┘  └─────────┘  └─────────┘
```

The laptop acts as the central coordination and decision-making system, while the ESP32 robots handle low-level motor control and local obstacle sensing.

---

## Key Features

- Multi-robot WebSocket communication
- Dynamic robot registration
- Unique robot IDs
- Wi-Fi-based robot communication
- mDNS-based server discovery
- Automatic WebSocket reconnection
- Server-side robot state management
- Logical position and orientation tracking
- Grid-based exploration map
- Robot movement history and path tracking
- Ultrasonic obstacle detection
- Forward movement safety stop
- Manual robot control
- Per-robot MANUAL/AUTO modes
- Autonomous exploration controller
- Real-time sensor reporting
- Real-time web dashboard
- Robot path visualization
- Shared exploration state
- YOLO-based object detection
- Camera-equipped robot support

---

# System Architecture

SwarmNav follows a centralized architecture.

```text
                        ┌─────────────────────────┐
                        │         Laptop          │
                        │                         │
                        │      FastAPI Server     │
                        │                         │
                        │  ┌───────────────────┐  │
                        │  │ Robot Manager     │  │
                        │  │ State Management  │  │
                        │  │ Map Manager       │  │
                        │  │ Auto Controller   │  │
                        │  │ Vision            │  │
                        │  └───────────────────┘  │
                        │                         │
                        │     Web Dashboard       │
                        └────────────┬────────────┘
                                     │
                               Wi-Fi / WebSocket
                                     │
                   ┌─────────────────┼─────────────────┐
                   │                 │                 │
                   ▼                 ▼                 ▼
             ┌──────────┐      ┌──────────┐      ┌──────────┐
             │ Robot 1  │      │ Robot 2  │      │ Robot N  │
             │  ESP32   │      │  ESP32   │      │  ESP32   │
             │          │      │          │      │          │
             │  Motors  │      │  Motors  │      │  Motors  │
             │Ultrasonic│      │Ultrasonic│      │Ultrasonic│
             └──────────┘      └──────────┘      └──────────┘
```

The server is responsible for high-level coordination, mapping, robot state, vision processing, and autonomous decisions.

The ESP32 is responsible for low-level robot operation such as:

- Motor control
- Ultrasonic measurement
- Local forward obstacle protection
- WebSocket communication
- Receiving and executing movement commands
- Robot registration

This separation keeps the embedded firmware lightweight while allowing the server to perform more complex processing.

---

# Repository Structure

```text
SwarmNav/
│
├── dashboard/
│   ├── static/
│   │   ├── app.js
│   │   └── style.css
│   │
│   └── templates/
│       └── index.html
│
├── data/
│   └── vision/
│       ├── detections.json
│       └── images/
│
├── image/
│   ├── test.py
│   ├── test_yolo.py
│   └── test_yolo_img.py
│
├── robots/
│   ├── cam.ino
│   └── robots.ino
│
├── runs/
│   └── vision/
│
├── server/
│   ├── auto_controller.py
│   ├── main.py
│   ├── map_manager.py
│   ├── robot_manager.py
│   ├── state.py
│   └── vision.py
│
├── requirements.txt
└── README.md
```

Generated files, caches, model weights, and other development artifacts may not be included in the repository depending on the `.gitignore` configuration.

---

# Server

The `server/` directory contains the central intelligence and communication layer.

## `main.py`

The main FastAPI application.

It handles:

- Web dashboard
- Robot WebSocket connections
- Robot registration
- Sensor updates
- Robot commands
- MANUAL/AUTO mode switching
- Dashboard state updates
- Server-side coordination

---

## `state.py`

Contains the central representation of the swarm state.

It maintains information such as:

- Connected robots
- Robot positions
- Robot orientations
- Robot modes
- Sensor readings
- Pending commands
- Robot paths
- Global map cells

The central state allows information from multiple robots to be maintained consistently by the server.

---

## `robot_manager.py`

Responsible for the robot communication lifecycle.

It handles:

- Robot registration
- Robot reconnection
- Robot disconnection
- Command transmission
- Robot information exposed to the dashboard

Robot state can be maintained by the server even when a robot temporarily disconnects.

---

## `map_manager.py`

Maintains the logical exploration map.

The map tracks information such as:

- Visited cells
- Free cells
- Obstacles
- Robot locations
- Exploration paths

The map uses logical grid coordinates rather than relying on continuous physical positioning.

---

## `auto_controller.py`

Contains the autonomous exploration logic.

The controller uses available robot state, sensor information, and the shared map to select movement for robots operating in `AUTO` mode.

The current implementation provides a sensor-driven baseline exploration controller.

---

## `vision.py`

Contains the server-side vision functionality and processing used by the project's vision pipeline.

The vision system can process camera input and perform object detection using YOLO.

Vision is treated as an additional perception layer alongside the core navigation system.

---

# Robot Firmware

The robot firmware is located in:

```text
robots/
├── robots.ino
└── cam.ino
```

## `robots.ino`

`robots.ino` is the firmware for the main rover and other regular ESP32 robots that do not use a camera module.

The regular ESP32 firmware provides:

- Wi-Fi connection
- mDNS
- WebSocket communication
- Motor control
- Ultrasonic sensing
- Movement timing
- Forward obstacle protection
- Robot registration
- Sensor reporting

The **main rover is currently configured as Robot ID 1**.

Other regular ESP32 robots can use different IDs.

---

## `cam.ino`

`cam.ino` is intended for ESP32 robots equipped with camera modules.

Camera-equipped robots can participate in the same robot communication architecture while additionally providing camera data for the vision pipeline.

---

# Robot Hardware

The current mobile robot uses:

- ESP32
- L298N motor driver
- DC motors
- Ultrasonic distance sensor
- Robot chassis
- External motor power supply

The motors are controlled as left and right sides to provide differential-style movement.

```text
Left side  → Motor group
Right side → Motor group
```

The robot supports:

```text
FORWARD
BACKWARD
LEFT
RIGHT
STOP
```

Movement is currently implemented using timed motor commands.

Because wheel encoders are not currently used, the physical distance travelled is approximated using movement duration rather than measured wheel displacement.

---

# Ultrasonic Obstacle Detection

The ultrasonic sensor provides local distance information to the robot.

The current firmware continuously checks the front distance while the robot is moving forward.

If an obstacle is detected within the configured safety distance, the ESP32 immediately stops the motors.

Example logic:

```text
         Front
           │
           ▼
      ┌─────────┐
      │Ultrasonic│
      │  Sensor  │
      └────┬────┘
           │
           ▼
      Distance Check
           │
      ┌────┴────┐
      │         │
   Safe      Obstacle
      │         │
      ▼         ▼
   Continue    STOP
```

The current firmware uses a configurable threshold:

```cpp
#define OBSTACLE_DISTANCE_CM 20.0
```

This provides a local safety mechanism independent of the server's autonomous decision-making.

---

# Robot Communication

The robots communicate with the central server using WebSockets.

The communication architecture is:

```text
Local Wi-Fi Network
       │
       ├── Laptop / Server
       │
       ├── ESP32 Robot 1
       │
       ├── ESP32 Robot 2
       │
       └── ESP32 Robot N
```

A phone hotspot can also be used as the local network during development and testing.

---

# Robot Registration

Each robot has a unique ID.

For example:

```cpp
#define ROBOT_ID 2
```

The ID must be changed when configuring different physical robots.

The current primary rover uses:

```cpp
#define ROBOT_ID 1
```

When a robot establishes a WebSocket connection, it registers itself with the server.

Example:

```json
{
    "robot_id": 2,
    "type": "REGISTER",
    "camera": false
}
```

The server can therefore identify individual robots and maintain separate state for each one.

Example robot configuration:

```text
Robot 1 → ROBOT_ID 1 → Main rover
Robot 2 → ROBOT_ID 2 → Additional rover
Robot 3 → ROBOT_ID 3 → Additional rover
```

Each robot should use a unique `ROBOT_ID`.

---

# Sensor Messages

The ESP32 periodically reports ultrasonic information.

Example:

```json
{
    "robot_id": 2,
    "type": "SENSOR",
    "front": 34.5
}
```

If a valid ultrasonic measurement is unavailable, the front distance is reported as unavailable.

---

# Movement Commands

The server sends movement commands to individual robots.

Example:

```json
{
    "robot_id": 2,
    "command": "FORWARD"
}
```

Supported commands:

```text
FORWARD
BACKWARD
LEFT
RIGHT
STOP
```

The ESP32 receives the command and executes the corresponding motor operation.

---

# Movement Safety

Forward movement has an additional local safety check.

Before starting a forward movement:

```text
Server
  │
  ▼
FORWARD command
  │
  ▼
ESP32 checks ultrasonic distance
  │
  ├── Safe ───────► Move Forward
  │
  └── Obstacle ───► Reject command
```

While moving forward, the ESP32 continues checking the ultrasonic sensor.

If an obstacle enters the configured safety range, the motors are stopped immediately.

This provides a hardware-level safety layer even if the server's navigation decision is not aware of the obstacle yet.

---

# Control Modes

Each robot can operate in one of two modes:

```text
MANUAL
AUTO
```

## Manual Mode

In `MANUAL` mode, movement commands are issued from the dashboard.

Available commands:

```text
FORWARD
BACKWARD
LEFT
RIGHT
STOP
```

Manual mode is primarily used for:

- Testing hardware
- Testing movement
- Verifying sensors
- Debugging robot communication
- Manually exploring the environment

---

## Auto Mode

In `AUTO` mode, the server's autonomous controller determines movement.

The general process is:

```text
Sensor Information
       │
       ▼
   Update State
       │
       ▼
   Update Map
       │
       ▼
Determine Available
   Directions
       │
       ▼
Select Exploration
    Movement
       │
       ▼
   Send Command
       │
       ▼
    ESP32
       │
       ▼
   Move Robot
       │
       ▼
    Sense Again
```

Multiple robots can operate in `AUTO` mode while sharing the server's global state.

---

# Exploration Map

SwarmNav maintains a grid-based logical representation of the explored environment.

Cells can represent information such as:

```text
START
FREE
OBSTACLE
VISITED
```

The map expands as robots discover new areas.

The logical coordinate system follows:

```text
                NORTH
                  ↑
                  │
          WEST ←──┼──→ EAST
                  │
                  ↓
                SOUTH
```

Robot position and movement history are represented using these logical coordinates.

This allows the server to reason about the environment independently of the physical dimensions of the robot chassis.

---

# Autonomous Exploration

The current exploration system follows a sensor-driven approach:

```text
            ┌───────────────┐
            │ Sensor Update │
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │   Update Map  │
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │ Find Available│
            │  Directions   │
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │ Find Unexplored│
            │     Area      │
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │ Select Action │
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  Move Robot   │
            └───────┬───────┘
                    │
                    ▼
                Sense Again
```

Multiple robots can operate in `AUTO` mode while sharing the server's global state.

---

# Dashboard

The web dashboard provides a centralized interface for monitoring and controlling the robot swarm.

It provides information such as:

- Robot ID
- Connection status
- Position
- Orientation
- Current action
- Control mode
- Ultrasonic measurements
- Robot paths
- Exploration map
- Robot state

The dashboard also provides:

- Manual movement controls
- MANUAL/AUTO switching
- Real-time robot monitoring
- Exploration visualization

The dashboard files are located in:

```text
dashboard/
├── static/
│   ├── app.js
│   └── style.css
│
└── templates/
    └── index.html
```

---

# Vision Pipeline

SwarmNav contains a YOLO-based vision pipeline for object detection.

Relevant files include:

```text
image/
├── test.py
├── test_yolo.py
└── test_yolo_img.py
```

The server-side vision implementation is located at:

```text
server/vision.py
```

The default object detection model used by most of the application is **YOLOv8n**.

Model weights are kept outside the repository rather than being committed directly.

The model can be changed according to the requirements of the application.

Vision-related output is stored under:

```text
data/vision/
```

The vision pipeline can provide object detection information that can be associated with the exploration environment.

A general perception flow is:

```text
Camera
  │
  ▼
Object Detection
  │
  ▼
Object / Location Association
  │
  ▼
Exploration Map
```

The core navigation system can operate using ultrasonic sensing without requiring camera perception.

---

# Network Discovery

The system uses mDNS to simplify local network communication.

The ESP32 can identify itself using a hostname such as:

```text
rover-2.local
```

The server can also be discovered using its local hostname.

This avoids requiring a fixed IP address for every robot during development.

---

# Installation

Clone the repository:

```bash
git clone https://github.com/Sujit-Hiwale/SwarmNav.git
cd SwarmNav
```

Create a Python virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

---

# ESP32 Setup

Open the appropriate robot firmware:

```text
robots/robots.ino
```

for regular ESP32 robots, or:

```text
robots/cam.ino
```

for camera-equipped robots.

Configure the Wi-Fi credentials:

```cpp
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASSWORD = "YOUR_PASSWORD";
```

Configure the robot identity:

```cpp
#define ROBOT_ID 1
#define ROBOT_HOSTNAME "rover-1"
```

Each physical robot must use a unique `ROBOT_ID` and hostname.

For example:

```text
Robot 1 → ROBOT_ID 1 → rover-1
Robot 2 → ROBOT_ID 2 → rover-2
Robot 3 → ROBOT_ID 3 → rover-3
```

The firmware can be uploaded using the Arduino IDE or another supported ESP32 development environment.

---

# Server Configuration

The ESP32 firmware contains the server hostname and WebSocket configuration:

```cpp
const char* SERVER_HOST = "sujit";
const uint16_t SERVER_PORT = 8000;
const char* SERVER_WS_PATH = "/ws/robot";
```

`SERVER_HOST` should be changed to the hostname of the computer running the FastAPI server when deploying the project on another machine.

The laptop running the server and the ESP32 robots must be connected to the same local network.

---

# Running the Server

From the project root:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

The server runs on:

```text
http://0.0.0.0:8000
```

Open the dashboard from another device using the laptop's local IP address:

```text
http://<LAPTOP_IP>:8000
```

For example:

```text
http://192.168.x.x:8000
```

The ESP32 robots must be connected to the same network.

---

# Typical Startup Sequence

A typical deployment follows this sequence:

```text
1. Start local Wi-Fi network
            │
            ▼
2. Start FastAPI server
            │
            ▼
3. Power on ESP32 robots
            │
            ▼
4. ESP32 connects to Wi-Fi
            │
            ▼
5. ESP32 starts mDNS
            │
            ▼
6. ESP32 discovers server
            │
            ▼
7. WebSocket connection established
            │
            ▼
8. Robot registers
            │
            ▼
9. Dashboard displays robot
            │
            ▼
10. MANUAL or AUTO operation
```