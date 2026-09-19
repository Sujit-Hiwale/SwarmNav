from .state import (
    robots,
    map_cells,
)


# ============================================================
# DIRECTIONS
# ============================================================

DIRECTIONS = {
    "NORTH": (0, 1),
    "EAST":  (1, 0),
    "SOUTH": (0, -1),
    "WEST":  (-1, 0),
}


# ============================================================
# ROTATION
# ============================================================

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

    robot = robots.get(
        robot_id
    )


    if robot is None:

        return


    # ========================================================
    # LEFT
    #
    # Turning does NOT change position.
    # ========================================================

    if action == "LEFT":

        robot.orientation = LEFT_TURN[
            robot.orientation
        ]

        return


    # ========================================================
    # RIGHT
    #
    # Turning does NOT change position.
    # ========================================================

    if action == "RIGHT":

        robot.orientation = RIGHT_TURN[
            robot.orientation
        ]

        return


    # ========================================================
    # FORWARD
    # ========================================================

    if action == "FORWARD":

        dx, dy = DIRECTIONS[
            robot.orientation
        ]

        new_x = robot.x + dx
        new_y = robot.y + dy


        robot.x = new_x
        robot.y = new_y


    # ========================================================
    # BACKWARD
    #
    # Backward movement is opposite to current orientation.
    # ========================================================

    elif action == "BACKWARD":

        dx, dy = DIRECTIONS[
            robot.orientation
        ]

        robot.x -= dx
        robot.y -= dy


    else:

        return


    # ========================================================
    # RECORD PATH
    # ========================================================

    robot.path.append(
        (
            robot.x,
            robot.y,
        )
    )


    # ========================================================
    # MARK NEW CELL VISITED
    # ========================================================

    mark_visited(
        robot.x,
        robot.y,
        robot_id,
    )


# ============================================================
# MARK SURROUNDING CELLS FROM ULTRASONIC DATA
# ============================================================

def mark_obstacles(
    robot_id: int,
):

    robot = robots.get(
        robot_id
    )


    if robot is None:

        return


    # --------------------------------------------------------
    # Distance readings
    # --------------------------------------------------------

    readings = {

        "left":
            robot.left_distance,

        "front":
            robot.front_distance,

        "right":
            robot.right_distance,
    }


    # --------------------------------------------------------
    # Relative directions from robot orientation
    # --------------------------------------------------------

    relative_directions = {

        "NORTH": {

            "left":  "WEST",
            "front": "NORTH",
            "right": "EAST",
        },

        "EAST": {

            "left":  "NORTH",
            "front": "EAST",
            "right": "SOUTH",
        },

        "SOUTH": {

            "left":  "EAST",
            "front": "SOUTH",
            "right": "WEST",
        },

        "WEST": {

            "left":  "SOUTH",
            "front": "WEST",
            "right": "NORTH",
        },
    }


    directions = relative_directions[
        robot.orientation
    ]


    # ========================================================
    # PROCESS EACH SENSOR
    # ========================================================

    for sensor_direction, distance in readings.items():

        if distance is None:

            continue


        absolute_direction = directions[
            sensor_direction
        ]


        dx, dy = DIRECTIONS[
            absolute_direction
        ]


        cell_x = robot.x + dx
        cell_y = robot.y + dy


        # ----------------------------------------------------
        # Obstacle
        # ----------------------------------------------------

        if distance < 20:

            # Don't overwrite a robot's current cell.
            if (
                cell_x == robot.x
                and
                cell_y == robot.y
            ):

                continue


            map_cells[
                (cell_x, cell_y)
            ] = {

                "type": "obstacle",

                "visited": False,

                "last_robot": None,
            }


        # ----------------------------------------------------
        # Free / discovered cell
        # ----------------------------------------------------

        else:

            cell = map_cells.setdefault(
                (cell_x, cell_y),
                {
                    "type": "free",
                    "visited": False,
                    "last_robot": None,
                },
            )


            # Never turn an already-known obstacle into
            # a free cell just because of another reading.
            if cell["type"] != "obstacle":

                cell["type"] = "free"


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
        })


    return result