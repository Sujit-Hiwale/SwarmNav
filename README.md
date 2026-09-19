# SwarmNav

SwarmNav is a multi-robot exploration and navigation system in which a laptop acts as the central server for coordinating multiple ESP32-based robots.

Each robot provides movement and ultrasonic sensing, while the server maintains the robot states, exploration map, movement paths, and autonomous exploration logic. A web dashboard provides real-time monitoring and manual control.

The system is designed to support multiple robots operating cooperatively in the same environment and provides a foundation for future multi-agent reinforcement learning.

---

## System Architecture

```text
                         ┌──────────────────────────┐
                         │          Laptop          │
                         │                          │
                         │      FastAPI Server      │
                         │                          │
                         │  ┌────────────────────┐  │
                         │  │ Robot Manager      │  │
                         │  │ State Management   │  │
                         │  │ Map Manager        │  │
                         │  │ Auto Controller    │  │
                         │  └────────────────────┘  │
                         │                          │
                         │       Web Dashboard      │
                         └────────────┬─────────────┘
                                      │
                               Wi-Fi / WebSocket
                                      │
                  ┌───────────────────┼───────────────────┐
                  │                   │                   │
           ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
           │   Robot 1   │     │   Robot 2   │     │   Robot N   │
           │    ESP32    │     │    ESP32    │     │    ESP32    │
           │             │     │             │     │             │
           │   Motors    │     │   Motors    │     │   Motors    │
           │ Ultrasonic  │     │ Ultrasonic  │     │ Ultrasonic  │
           │    Servo    │     │    Servo    │     │    Servo    │
           └─────────────┘     └─────────────┘     └─────────────┘
```

The laptop and robots communicate over the same local Wi-Fi network. The current setup can use a phone hotspot as the local network.

---

## Features

* Multi-robot WebSocket communication
* Dynamic robot registration
* Configurable robot IDs
* Robot reconnection handling
* Server-side robot state management
* Server-authoritative logical position and orientation
* Robot movement history and path tracking
* Shared exploration map
* Ultrasonic obstacle detection
* Servo-based directional scanning
* Manual robot control
* Autonomous exploration mode
* Per-robot MANUAL/AUTO control
* Real-time web dashboard
* Real-time sensor information
* Robot path visualization
* Dynamic exploration map
* Architecture prepared for multi-agent reinforcement learning

---

## Repository Structure

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
├── robots/
│   └── robots.ino
│
├── server/
│   ├── auto_controller.py
│   ├── main.py
│   ├── map_manager.py
│   ├── robot_manager.py
│   └── state.py
│
├── requirements.txt
└── README.md
```

### `server/`

Contains the central server-side logic.

#### `main.py`

The main FastAPI application.

It handles:

* Web dashboard
* Robot WebSocket connections
* Robot registration
* Sensor updates
* Robot commands
* Manual/Auto mode switching
* Dashboard state updates

#### `state.py`

Contains the central state representation.

It stores:

* Connected robots
* Robot positions
* Robot orientations
* Robot modes
* Sensor readings
* Pending commands
* Robot paths
* Global map cells

#### `robot_manager.py`

Responsible for robot communication and lifecycle management.

It handles:

* Robot registration
* Reconnection
* Disconnection
* Command transmission
* Dashboard robot data

Robot state is preserved when a robot temporarily disconnects.

#### `map_manager.py`

Maintains the global exploration map.

It tracks:

* Visited cells
* Free cells
* Obstacles
* Robot locations
* Exploration paths

#### `auto_controller.py`

Contains the autonomous exploration controller.

It uses the available sensor information and the shared map to determine movement for robots operating in `AUTO` mode.

The current controller is a baseline exploration implementation and is intended to be extended with more advanced multi-robot planning and reinforcement learning.

---

## Robot Hardware

Each robot currently uses:

* ESP32
* L298N motor driver
* Four DC motors
* Ultrasonic distance sensor
* Servo motor

The four motors are controlled as two sides:

```text
Left side  → 2 motors
Right side → 2 motors
```

This provides differential-style movement:

```text
FORWARD
BACKWARD
LEFT
RIGHT
```

The robot currently moves in discrete movement blocks. Since wheel encoders are not currently used, the physical movement distance is approximated using motor runtime.

---

## Ultrasonic Scanning

The ultrasonic sensor is mounted on a servo.

The servo performs a three-direction scan:

```text
45°   → Left
90°   → Front
135°  → Right
```

The resulting distances are sent to the server as sensor information.

Example:

```json
{
    "robot_id": 1,
    "type": "SENSOR",
    "left": 35.2,
    "front": 72.5,
    "right": 18.4
}
```

The server uses these measurements to update its representation of the environment.

---

## Communication

The robots communicate with the server using WebSockets.

The network currently follows:

```text
Phone Hotspot
     │
     ├── Laptop
     │
     ├── ESP32 Robot 1
     ├── ESP32 Robot 2
     └── ESP32 Robot N
```

Each robot identifies itself when connecting.

Example registration message:

```json
{
    "robot_id": 1,
    "type": "REGISTER"
}
```

The server sends commands in the following format:

```json
{
    "robot_id": 1,
    "command": "FORWARD"
}
```

---

## Robot IDs

Each ESP32 is assigned a unique integer ID.

The ID is configured in:

```text
robots/robots.ino
```

For example:

```cpp
#define ROBOT_ID 1
```

Another robot can use:

```cpp
#define ROBOT_ID 2
```

The server does not require a fixed number of connected robots. Robots can connect and disconnect dynamically.

---

## Control Modes

Every newly connected robot starts in:

```text
MANUAL
```

This prevents a robot from moving autonomously immediately after connecting.

### Manual Mode

In `MANUAL` mode, movement commands are issued from the web dashboard.

```text
FORWARD
BACKWARD
LEFT
RIGHT
```

### Auto Mode

In `AUTO` mode, the autonomous exploration controller determines the robot's movement.

A robot must explicitly be switched to `AUTO` through the dashboard.

If a robot reconnects, it is placed back into `MANUAL` mode.

---

## Exploration Map

The server maintains a global grid-based representation of the explored environment.

Each discovered cell can contain information such as:

```text
START
FREE
OBSTACLE
VISITED
```

The map expands as robots discover new locations.

The coordinate system is:

```text
             NORTH
               ↑
               │
       WEST ←──┼──→ EAST
               │
               ↓
             SOUTH
```

Robot positions and movement paths are maintained using these logical coordinates.

---

## Autonomous Exploration

The current autonomous controller follows a sensor-driven exploration process:

```text
       Sensor Scan
            │
            ▼
      Update Map
            │
            ▼
   Determine Available
      Directions
            │
            ▼
   Find Unexplored Area
            │
            ▼
      Select Movement
            │
            ▼
       Move Robot
            │
            ▼
       Scan Again
```

Multiple robots can independently operate in `AUTO` mode while sharing the server's global state.

The current implementation provides the foundation for cooperative exploration but does not yet implement the final multi-agent planning/RL system.

---

## Dashboard

The web dashboard provides a centralized interface for operating the swarm.

It provides information including:

* Robot ID
* Position
* Orientation
* Connection status
* Current action
* Control mode
* Ultrasonic measurements
* Robot paths
* Global exploration map

It also provides:

* Manual movement controls
* MANUAL/AUTO switching

---

## Installation

Clone the repository:

```bash
git clone https://github.com/Sujit-Hiwale/SwarmNav.git
cd SwarmNav
```

Create a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the tested dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the Server

Start the FastAPI server from the project root:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

The server will listen on:

```text
http://0.0.0.0:8000
```

Open the dashboard from a browser using the laptop's local network IP address:

```text
http://<LAPTOP_IP>:8000
```

The ESP32 robots must be connected to the same network.

---

## Requirements

The server requires Python and the dependencies listed in:

```text
requirements.txt
```

The requirements file contains the versions installed and tested during development.

To reproduce the environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Current Limitations

The current implementation has several deliberate limitations:

* No wheel encoders
* No IMU-based odometry
* Physical distance is estimated using motor runtime
* Ultrasonic sensing provides local obstacle information
* Current map representation is grid-based
* Autonomous exploration is currently a baseline controller
* Advanced multi-robot frontier assignment is not yet implemented
* Collision avoidance between robots is not yet implemented
* Reinforcement learning is not yet integrated
* Camera-based perception is not currently part of the system

These limitations leave clear areas for future development.

---

## Future Development

### Navigation and Mapping

* Improved grid/graph representation
* Frontier detection
* BFS/A* path planning
* Exploration target assignment
* Robot collision avoidance
* Deadlock detection
* Backtracking
* Complete reachable-area coverage

### Multi-Robot Intelligence

* Cooperative exploration
* Multi-robot task allocation
* Exploration load balancing
* Shared exploration rewards
* Multi-agent reinforcement learning
* PPO/MAPPO-based exploration policies

### Perception

* Camera integration
* Object detection
* Object classification
* Semantic mapping
* Vision-assisted navigation

---

## Project Direction

The long-term objective of SwarmNav is to develop a cooperative robotic system capable of exploring an unknown environment using multiple low-cost mobile robots.

The architecture separates:

```text
Hardware
   ↓
Communication
   ↓
Robot State
   ↓
Mapping
   ↓
Navigation
   ↓
Decision Making / RL
```

This separation allows the hardware and communication infrastructure to be developed and tested independently from higher-level navigation and learning algorithms.

---

## License

This project is currently under development.

License information will be added when the project is prepared for public release.
