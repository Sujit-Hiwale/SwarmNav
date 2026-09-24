import asyncio

from .state import robots
from .robot_manager import send_command
from .map_manager import (
    mark_visited,
    mark_obstacles,
    get_map_data,
    DIRECTIONS,
    LEFT_TURN,
    RIGHT_TURN,
)


SAFE_DISTANCE = 20.0

MOVE_COMMANDS = {
    "NORTH": "FORWARD",
    "EAST": "FORWARD",
    "SOUTH": "FORWARD",
    "WEST": "FORWARD",
}


class AutoController:

    def __init__(self):
        self.running = True

    async def run(self):
        print("[AUTO] Autonomous exploration controller started")

        while self.running:

            try:
                active_robots = [
                    robot
                    for robot in robots.values()
                    if robot.websocket is not None
                    and robot.mode == "AUTO"
                ]

                # No robots connected
                if not active_robots:
                    await asyncio.sleep(0.5)
                    continue

                for robot in active_robots:

                    # Wait until previous command finishes
                    if robot.pending_command is not None:
                        continue

                    await self.control_robot(robot)

                await asyncio.sleep(0.2)

            except Exception as error:
                print(f"[AUTO ERROR] {error}")
                await asyncio.sleep(1)

    async def control_robot(self, robot):

        robot_id = robot.robot_id

        print(
            f"[AUTO] ROBOT_{robot_id} | "
            f"POS=({robot.x},{robot.y}) | "
            f"DIR={robot.orientation}"
        )

        mark_visited(
            robot.x,
            robot.y,
            robot_id
        )

        mark_obstacles(robot_id)

        available = self.get_available_directions(robot)

        print(
            f"[AUTO] ROBOT_{robot_id}: "
            f"available={available}"
        )

        unexplored = []

        for direction in available:

            dx, dy = DIRECTIONS[direction]

            nx = robot.x + dx
            ny = robot.y + dy

            cell = self.get_cell(nx, ny)

            if cell is None:
                unexplored.append(direction)

            elif not cell.get("visited", False):
                unexplored.append(direction)

        if unexplored:

            direction = self.choose_direction(
                robot,
                unexplored
            )

            print(
                f"[AUTO] ROBOT_{robot_id}: "
                f"Exploring {direction}"
            )

            await self.move_toward(
                robot,
                direction
            )

            return

        frontier = self.find_nearest_frontier(robot)

        if frontier is not None:

            direction = frontier

            print(
                f"[AUTO] ROBOT_{robot_id}: "
                f"Moving toward known frontier {direction}"
            )

            await self.move_toward(
                robot,
                direction
            )

            return

        print(
            f"[AUTO] ROBOT_{robot_id}: "
            f"No unexplored area detected"
        )

        robot.current_action = "EXPLORATION_COMPLETE"

    def get_available_directions(self, robot):
        available = []

        if robot.front_distance is not None and robot.front_distance >= SAFE_DISTANCE:
            available.append(robot.orientation)

        return available

    # =====================================================
    # DIRECTION SELECTION
    # =====================================================

    def choose_direction(self, robot, directions):

        """
        Prefer directions that have not been visited.

        Forward is preferred when it is unexplored,
        otherwise choose another unexplored direction.
        """

        if robot.orientation in directions:
            return robot.orientation

        # Deterministic order prevents random wandering
        preferred_order = [
            LEFT_TURN[robot.orientation],
            RIGHT_TURN[robot.orientation],
        ]

        for direction in preferred_order:

            if direction in directions:
                return direction

        return directions[0]

    # =====================================================
    # MOVEMENT
    # =====================================================

    async def move_toward(self, robot, target_direction):

        current = robot.orientation

        # Already facing target
        if current == target_direction:

            print(
                f"[AUTO] ROBOT_{robot.robot_id}: "
                f"FORWARD"
            )

            await send_command(
                robot.robot_id,
                "FORWARD"
            )

            return

        # One 90-degree left turn
        if LEFT_TURN[current] == target_direction:

            print(
                f"[AUTO] ROBOT_{robot.robot_id}: "
                f"LEFT"
            )

            await send_command(
                robot.robot_id,
                "LEFT"
            )

            return

        # One 90-degree right turn
        if RIGHT_TURN[current] == target_direction:

            print(
                f"[AUTO] ROBOT_{robot.robot_id}: "
                f"RIGHT"
            )

            await send_command(
                robot.robot_id,
                "RIGHT"
            )

            return

        await send_command(robot.robot_id, "RIGHT")

    # =====================================================
    # MAP HELPERS
    # =====================================================

    def get_cell(self, x, y):

        for cell in get_map_data():

            if cell["x"] == x and cell["y"] == y:
                return cell

        return None

    def find_nearest_frontier(self, robot):

        """
        Find a known free cell that has an unexplored
        neighboring direction.

        This is the beginning of frontier-based exploration.
        """

        best_direction = None
        best_distance = None

        for cell in get_map_data():

            if cell["type"] != "free":
                continue

            x = cell["x"]
            y = cell["y"]

            if not cell.get("visited", False):
                continue

            distance = abs(x - robot.x) + abs(y - robot.y)

            if best_distance is not None and distance >= best_distance:
                continue

            for direction, (dx, dy) in DIRECTIONS.items():

                nx = x + dx
                ny = y + dy

                neighbor = self.get_cell(nx, ny)

                if neighbor is None:

                    if distance == 0:
                        best_direction = direction

                    else:
                        best_direction = self.direction_from_position(
                            robot.x,
                            robot.y,
                            x,
                            y
                        )

                    best_distance = distance
                    break

        return best_direction

    def direction_from_position(
        self,
        robot_x,
        robot_y,
        target_x,
        target_y
    ):

        dx = target_x - robot_x
        dy = target_y - robot_y

        if abs(dx) > abs(dy):

            if dx > 0:
                return "EAST"

            return "WEST"

        if dy > 0:
            return "NORTH"

        if dy < 0:
            return "SOUTH"

        return "NORTH"


auto_controller = AutoController()