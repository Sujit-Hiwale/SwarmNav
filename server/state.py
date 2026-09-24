from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RobotState:

    robot_id: int
    websocket: object

    # --------------------------------------------------------
    # SERVER-AUTHORITATIVE POSITION
    # --------------------------------------------------------

    x: int = 0
    y: int = 0

    # NORTH, EAST, SOUTH, WEST
    orientation: str = "NORTH"

    # --------------------------------------------------------
    # ROBOT STATUS
    # --------------------------------------------------------

    status: str = "CONNECTED"

    current_action: str = "IDLE"

    # Command currently waiting for ESP32 completion.
    pending_command: str | None = None

    # --------------------------------------------------------
    # CONTROL MODE
    # --------------------------------------------------------

    # MANUAL = dashboard controls robot
    # AUTO   = automatic exploration controller controls robot
    mode: str = "MANUAL"

    front_distance: float | None = None

    # --------------------------------------------------------
    # MOVEMENT HISTORY
    # --------------------------------------------------------

    path: list[tuple[int, int]] = field(
        default_factory=lambda: [(0, 0)]
    )

    connected_at: datetime = field(
        default_factory=datetime.now
    )


robots: dict[int, RobotState] = {}


# ============================================================
# GLOBAL EXPLORATION MAP
# ============================================================

# (x, y) -> cell information
map_cells: dict[tuple[int, int], dict] = {

    (0, 0): {

        "type": "start",

        "visited": True,

        "last_robot": None
    }
}

INITIAL_POSITIONS = {
    1: (0, 0),
    2: (1, 0),
    3: (0, 1),
    4: (1, 1),
}