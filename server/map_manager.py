from .state import (
    robots,
    map_cells,
)

import cv2
import os
import time


# ============================================================
# DIRECTIONS
# ============================================================

DIRECTIONS = {
    "NORTH": (0, 1),
    "EAST":  (1, 0),
    "SOUTH": (0, -1),
    "WEST":  (-1, 0),
}


RIGHT_TURN = {
    "NORTH": "EAST",
    "EAST": "SOUTH",
    "SOUTH": "WEST",
    "WEST": "NORTH",
}


LEFT_TURN = {
    "NORTH": "WEST",
    "WEST": "SOUTH",
    "SOUTH": "EAST",
    "EAST": "NORTH",
}


# ============================================================
# OBJECT STORAGE
#
# One object can have observations from multiple robots.
# ============================================================

objects = {}


OBJECT_IMAGE_DIR = "data/target_images"

os.makedirs(
    OBJECT_IMAGE_DIR,
    exist_ok=True
)


# ============================================================
# MARK CELL AS VISITED
# ============================================================

def mark_visited(
    x: int,
    y: int,
    robot_id: int,
):

    cell = map_cells.setdefault(
        (x, y),
        {
            "type": "free",
            "visited": False,
            "last_robot": None,

            "objects": [],
            "observations": [],
        },
    )

    cell["visited"] = True
    cell["last_robot"] = robot_id


# ============================================================
# UPDATE ROBOT POSITION / DIRECTION
# ============================================================

def update_robot_position(
    robot_id: int,
    action: str,
):

    robot = robots.get(robot_id)

    if robot is None:
        return

    # --------------------------------------------------------
    # LEFT
    # --------------------------------------------------------

    if action == "LEFT":

        robot.orientation = LEFT_TURN[
            robot.orientation
        ]

        return

    # --------------------------------------------------------
    # RIGHT
    # --------------------------------------------------------

    if action == "RIGHT":

        robot.orientation = RIGHT_TURN[
            robot.orientation
        ]

        return

    # --------------------------------------------------------
    # FORWARD
    # --------------------------------------------------------

    if action == "FORWARD":

        dx, dy = DIRECTIONS[
            robot.orientation
        ]

        robot.x += dx
        robot.y += dy

    # --------------------------------------------------------
    # BACKWARD
    # --------------------------------------------------------

    elif action == "BACKWARD":

        dx, dy = DIRECTIONS[
            robot.orientation
        ]

        robot.x -= dx
        robot.y -= dy

    else:

        return

    # --------------------------------------------------------
    # RECORD PATH
    # --------------------------------------------------------

    robot.path.append(
        (
            robot.x,
            robot.y,
        )
    )

    # --------------------------------------------------------
    # MARK CELL
    # --------------------------------------------------------

    mark_visited(
        robot.x,
        robot.y,
        robot_id,
    )


# ============================================================
# MARK OBSTACLES FROM ULTRASONIC
# ============================================================

def mark_obstacles(robot_id: int):
    robot = robots.get(robot_id)

    if robot is None or robot.front_distance is None:
        return

    dx, dy = DIRECTIONS[robot.orientation]

    cell_x = robot.x + dx
    cell_y = robot.y + dy

    cell = map_cells.setdefault(
        (cell_x, cell_y),
        {
            "type": "free",
            "visited": False,
            "last_robot": None,
            "objects": [],
            "observations": [],
        },
    )

    if robot.front_distance < 20:
        cell["type"] = "obstacle"
    elif cell["type"] != "obstacle":
        cell["type"] = "free"

# ============================================================
# ADD OBJECT DETECTION
# ============================================================

def add_object_detection(
    robot_id: int,
    class_name: str,
    confidence: float,
    image,
    direction,
    distance,
    target=False,
):
    """
    Record an object detected by a particular robot.

    direction:
        Direction from robot toward object.

    distance:
        Estimated distance in grid/cell units or meters,
        depending on your vision system.
    """

    robot = robots.get(robot_id)

    if robot is None:
        return None

    robot_position = (
        robot.x,
        robot.y,
    )

    # --------------------------------------------------------
    # Estimate object grid position.
    #
    # For now this assumes distance is measured in grid
    # cells. We'll later replace this with proper camera
    # geometry.
    # --------------------------------------------------------

    dx, dy = DIRECTIONS.get(
        robot.orientation,
        (0, 0)
    )

    object_x = round(
        robot.x + dx * distance
    )

    object_y = round(
        robot.y + dy * distance
    )

    object_position = (
        object_x,
        object_y,
    )

    # --------------------------------------------------------
    # Object ID
    #
    # For now class + position.
    # Later we can add actual object tracking.
    # --------------------------------------------------------

    object_id = (
        f"{class_name}_"
        f"{object_x}_"
        f"{object_y}"
    )

    # --------------------------------------------------------
    # New object
    # --------------------------------------------------------

    if object_id not in objects:

        image_path = None

        if image is not None:

            image_path = os.path.join(
                OBJECT_IMAGE_DIR,
                f"{object_id}_{int(time.time())}.jpg"
            )

            cv2.imwrite(
                image_path,
                image
            )

        objects[object_id] = {

            "id":
                object_id,

            "class":
                class_name,

            "position":
                object_position,

            "image":
                image_path,

            "confidence":
                confidence,

            "target":
                target,

            "observations":
                [],
        }

    # --------------------------------------------------------
    # Existing object
    # --------------------------------------------------------

    else:

        existing = objects[
            object_id
        ]

        # Keep highest confidence.
        if confidence > existing["confidence"]:

            existing["confidence"] = confidence

    # --------------------------------------------------------
    # Record observation
    # --------------------------------------------------------

    observation = {

        "robot_id":
            robot_id,

        "robot_position":
            robot_position,

        "robot_orientation":
            robot.orientation,

        "direction":
            direction,

        "distance":
            distance,

        "confidence":
            confidence,

        "timestamp":
            time.time(),
    }

    objects[
        object_id
    ][
        "observations"
    ].append(
        observation
    )

    # --------------------------------------------------------
    # Store object reference in target cell
    # --------------------------------------------------------

    cell = map_cells.setdefault(
        object_position,
        {
            "type": "free",
            "visited": False,
            "last_robot": None,
            "objects": [],
            "observations": [],
        },
    )

    if object_id not in cell["objects"]:

        cell["objects"].append(
            object_id
        )

    # --------------------------------------------------------
    # Store observation in the robot's cell.
    #
    # This is what allows your UI to show:
    #
    # "Target was seen from here."
    # --------------------------------------------------------

    robot_cell = map_cells.setdefault(
        robot_position,
        {
            "type": "free",
            "visited": True,
            "last_robot": robot_id,
            "objects": [],
            "observations": [],
        },
    )

    robot_cell[
        "observations"
    ].append({

        "object_id":
            object_id,

        "robot_id":
            robot_id,

        "direction":
            direction,

        "distance":
            distance,

        "timestamp":
            time.time(),
    })

    return object_id


# ============================================================
# GET MAP FOR DASHBOARD
# ============================================================

def get_map_data():

    result = []

    for (
        (x, y),
        cell,
    ) in map_cells.items():

        result.append({

            "x":
                x,

            "y":
                y,

            "type":
                cell.get(
                    "type",
                    "free",
                ),

            "visited":
                cell.get(
                    "visited",
                    False,
                ),

            "last_robot":
                cell.get(
                    "last_robot",
                ),

            "objects":
                cell.get(
                    "objects",
                    [],
                ),

            "observations":
                cell.get(
                    "observations",
                    [],
                ),
        })
    return result


# ============================================================
# GET OBJECT DATA
# ============================================================

def get_object_data():

    return list(
        objects.values()
    )