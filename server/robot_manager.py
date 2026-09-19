import json

from .state import (
    robots,
    RobotState,
    INITIAL_POSITIONS,
)


# ============================================================
# SEND COMMAND TO ROBOT
# ============================================================

async def send_command(
    robot_id: int,
    command: str,
):

    robot = robots.get(
        robot_id
    )

    if robot is None:

        print(
            f"[TX] ERROR: ROBOT_{robot_id} "
            f"does not exist"
        )

        return False


    if robot.websocket is None:

        print(
            f"[TX] ERROR: ROBOT_{robot_id} "
            f"has no active WebSocket"
        )

        return False


    message = {
        "robot_id": robot_id,
        "command": command,
    }


    payload = json.dumps(
        message
    )


    print(
        f"[TX] ROBOT_{robot_id} <- "
        f"{payload}"
    )


    try:

        await robot.websocket.send_text(
            payload
        )

    except Exception as error:

        print(
            f"[TX ERROR] ROBOT_{robot_id}: "
            f"{error}"
        )

        return False


    robot.pending_command = command

    robot.current_action = command

    robot.status = "COMMAND_SENT"


    return True


# ============================================================
# REGISTER ROBOT
# ============================================================

def register_robot(
    robot_id: int,
    websocket,
):

    existing = robots.get(
        robot_id
    )

    # --------------------------------------------------------
    # Robot already known.
    #
    # Keep its previous position, orientation and path.
    # --------------------------------------------------------

    if existing is not None:

        existing.websocket = websocket

        existing.status = "CONNECTED"

        existing.current_action = "IDLE"

        existing.pending_command = None

        existing.mode = "MANUAL"

        print(
            f"[REGISTER] ROBOT_{robot_id} "
            f"reconnected"
        )

        print(
            f"[REGISTER] Position: "
            f"({existing.x}, {existing.y})"
        )

        print(
            f"[REGISTER] Direction: "
            f"{existing.orientation}"
        )

        return existing

    # --------------------------------------------------------
    # New robot
    # --------------------------------------------------------

    x, y = INITIAL_POSITIONS.get(
        robot_id,
        (0, 0)
    )

    robot = RobotState(
        robot_id=robot_id,
        websocket=websocket,
        x=x,
        y=y,
        path=[(x, y)]
    )

    robots[robot_id] = robot

    print(
        f"[REGISTER] ROBOT_{robot_id} "
        f"registered"
    )

    print(
        f"[REGISTER] Position: "
        f"({robot.x}, {robot.y})"
    )

    print(
        f"[REGISTER] Direction: "
        f"{robot.orientation}"
    )

    return robot
# ============================================================
# REMOVE ROBOT
# ============================================================

def remove_robot(
    robot_id: int,
    websocket,
):

    robot = robots.get(
        robot_id
    )


    if robot is None:

        return


    # --------------------------------------------------------
    # Only remove the connection if this is still the
    # WebSocket belonging to this robot.
    #
    # The RobotState itself is intentionally preserved.
    # --------------------------------------------------------

    if robot.websocket is websocket:

        robot.websocket = None

        robot.status = "DISCONNECTED"

        robot.current_action = "IDLE"

        robot.pending_command = None


        print(
            f"[DISCONNECT] ROBOT_{robot_id}"
        )


# ============================================================
# ROBOT DATA FOR DASHBOARD
# ============================================================

def robot_data():

    result = []


    for robot in robots.values():

        result.append({

            "id":
                robot.robot_id,

            "x":
                robot.x,

            "y":
                robot.y,

            "orientation":
                robot.orientation,

            "status":
                robot.status,

            "action":
                robot.current_action,

            "pending_command":
                robot.pending_command,

            "mode":
                robot.mode,

            "sensors": {

                "left":
                    robot.left_distance,

                "front":
                    robot.front_distance,

                "right":
                    robot.right_distance,
            },

            "path": [

                {
                    "x": x,
                    "y": y,
                }

                for x, y in robot.path
            ],
        })


    return result