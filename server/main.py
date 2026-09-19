import asyncio
import json
from pathlib import Path

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .state import robots
from .robot_manager import (
    register_robot,
    remove_robot,
    send_command,
    robot_data,
)
from .map_manager import (
    update_robot_position,
    mark_obstacles,
    get_map_data,
)
from .auto_controller import auto_controller

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DASHBOARD_DIR = BASE_DIR / "dashboard"

TEMPLATE_DIR = DASHBOARD_DIR / "templates"
STATIC_DIR = DASHBOARD_DIR / "static"


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Multi-Robot RL Explorer"
)

@app.on_event("startup")
async def start_auto_controller():
    asyncio.create_task(
        auto_controller.run()
    )


app.mount(
    "/static",
    StaticFiles(
        directory=str(STATIC_DIR)
    ),
    name="static",
)


# ============================================================
# DASHBOARD CLIENTS
# ============================================================

dashboard_clients: set[WebSocket] = set()


# ============================================================
# STATE
# ============================================================

def get_state():

    return {
        "robots": robot_data(),
        "map": get_map_data(),
    }


# ============================================================
# BROADCAST STATE TO ALL BROWSERS
# ============================================================

async def broadcast_state():

    if not dashboard_clients:
        return

    message = json.dumps(
        get_state()
    )

    disconnected = []

    for client in list(dashboard_clients):

        try:

            await client.send_text(
                message
            )

        except Exception:

            disconnected.append(
                client
            )

    for client in disconnected:

        dashboard_clients.discard(
            client
        )


# ============================================================
# HOME PAGE
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
async def dashboard():

    index_file = (
        TEMPLATE_DIR
        / "index.html"
    )

    return index_file.read_text(
        encoding="utf-8"
    )


# ============================================================
# DASHBOARD WEBSOCKET
# ============================================================

@app.websocket(
    "/ws/dashboard"
)
async def dashboard_websocket(
    websocket: WebSocket
):

    await websocket.accept()

    dashboard_clients.add(
        websocket
    )

    print(
        "[DASHBOARD] Browser connected"
    )

    # Send current state immediately.
    await websocket.send_text(
        json.dumps(
            get_state()
        )
    )

    try:

        while True:

            raw_message = (
                await websocket.receive_text()
            )

            print(
                f"[DASHBOARD] Received: "
                f"{raw_message}"
            )

            try:

                data = json.loads(
                    raw_message
                )

            except json.JSONDecodeError:

                print(
                    "[DASHBOARD] Invalid JSON"
                )

                continue


            message_type = data.get(
                "type"
            )


            # =================================================
            # ROBOT CONTROL
            # =================================================

            if message_type == "CONTROL":

                await handle_dashboard_control(
                    data
                )

                continue


            print(
                f"[DASHBOARD] Unknown message "
                f"type: {message_type}"
            )


    except WebSocketDisconnect:

        pass

    finally:

        dashboard_clients.discard(
            websocket
        )

        print(
            "[DASHBOARD] Browser disconnected"
        )


# ============================================================
# DASHBOARD CONTROL HANDLER
# ============================================================

async def handle_dashboard_control(
    data: dict
):

    robot_id = data.get(
        "robot_id"
    )

    action = data.get(
        "action"
    )


    if robot_id is None:

        print(
            "[CONTROL] Missing robot_id"
        )

        return


    try:

        robot_id = int(
            robot_id
        )

    except (
        TypeError,
        ValueError
    ):

        print(
            f"[CONTROL] Invalid robot ID: "
            f"{robot_id}"
        )

        return


    robot = robots.get(
        robot_id
    )


    if robot is None:

        print(
            f"[CONTROL] ROBOT_{robot_id} "
            f"is not connected"
        )

        return


    # ========================================================
    # SET MODE
    # ========================================================

    if action == "SET_MODE":

        mode = data.get(
            "mode"
        )

        if mode not in {
            "MANUAL",
            "AUTO"
        }:

            print(
                f"[CONTROL] Invalid mode: "
                f"{mode}"
            )

            return


        robot.mode = mode

        print(
            f"[CONTROL] ROBOT_{robot_id} "
            f"mode -> {mode}"
        )

        await broadcast_state()

        return


    # ========================================================
    # ROBOT COMMAND
    # ========================================================

    if action == "COMMAND":

        command = data.get(
            "command"
        )


        allowed_commands = {
            "FORWARD",
            "BACKWARD",
            "LEFT",
            "RIGHT",
            "STOP",
            "SCAN",
        }


        if command not in allowed_commands:

            print(
                f"[CONTROL] Invalid command: "
                f"{command}"
            )

            return


        # -----------------------------------------------
        # Don't allow a second movement while the first
        # one is still executing.
        # -----------------------------------------------

        if (
            robot.pending_command
            and command not in {"STOP"}
        ):

            print(
                f"[CONTROL] ROBOT_{robot_id} "
                f"is busy with "
                f"{robot.pending_command}"
            )

            return


        print(
            f"[CONTROL] Sending "
            f"{command} "
            f"-> ROBOT_{robot_id}"
        )


        success = await send_command(
            robot_id,
            command
        )


        if success:

            print(
                f"[CONTROL] ✓ Command sent "
                f"to ROBOT_{robot_id}: "
                f"{command}"
            )

        else:

            print(
                f"[CONTROL] ✗ Failed to send "
                f"command to ROBOT_{robot_id}"
            )


        await broadcast_state()

        return


    print(
        f"[CONTROL] Unknown action: "
        f"{action}"
    )


# ============================================================
# ROBOT WEBSOCKET
# ============================================================

@app.websocket(
    "/ws/robot"
)
async def robot_websocket(
    websocket: WebSocket
):

    await websocket.accept()

    robot_id = None

    print(
        "[ROBOT] WebSocket connection opened"
    )

    try:

        while True:

            raw_message = (
                await websocket.receive_text()
            )


            print(
                f"[ROBOT RX] {raw_message}"
            )


            try:

                data = json.loads(
                    raw_message
                )

            except json.JSONDecodeError:

                print(
                    "[ROBOT] Invalid JSON"
                )

                continue


            robot_id_value = data.get(
                "robot_id"
            )


            if robot_id_value is None:

                print(
                    "[ROBOT] Message has no "
                    "robot_id"
                )

                continue


            try:

                robot_id = int(
                    robot_id_value
                )

            except (
                TypeError,
                ValueError
            ):

                print(
                    "[ROBOT] Invalid robot ID"
                )

                continue


            # =================================================
            # REGISTRATION
            # =================================================

            if data.get(
                "type"
            ) == "REGISTER":

                register_robot(
                    robot_id,
                    websocket
                )


                print(
                    f"[ROBOT] ✓ "
                    f"ROBOT_{robot_id} "
                    f"registered"
                )


                await websocket.send_text(
                    json.dumps({
                        "robot_id":
                            robot_id,

                        "type":
                            "REGISTERED",
                    })
                )


                await broadcast_state()

                continue


            robot = robots.get(
                robot_id
            )


            if robot is None:

                print(
                    f"[ROBOT] Unknown "
                    f"ROBOT_{robot_id}"
                )

                continue


            # =================================================
            # SENSOR DATA
            # =================================================

            if data.get(
                "type"
            ) == "SENSOR":

                robot.left_distance = (
                    data.get("left")
                )

                robot.front_distance = (
                    data.get("front")
                )

                robot.right_distance = (
                    data.get("right")
                )

                if robot.pending_command == "SCAN":
                    robot.pending_command = None
                    robot.current_action = "IDLE"
                    robot.status = "READY"

                robot.status = (
                    "SENSORS_UPDATED"
                )


                print(
                    f"[SENSOR] ROBOT_{robot_id} "
                    f"L={robot.left_distance} "
                    f"F={robot.front_distance} "
                    f"R={robot.right_distance}"
                )


                mark_obstacles(
                    robot_id
                )


                await broadcast_state()

                continue


            # =================================================
            # STATUS
            # =================================================

            if data.get(
                "type"
            ) == "STATUS":

                status = data.get(
                    "status",
                    "UNKNOWN"
                )


                robot.status = status


                print(
                    f"[ROBOT STATUS] "
                    f"ROBOT_{robot_id}: "
                    f"{status}"
                )


                # ---------------------------------------------
                # ACTION COMPLETED
                # ---------------------------------------------

                if status == "ACTION_COMPLETE":

                    completed_action = (
                        robot.pending_command
                    )


                    if completed_action:

                        update_robot_position(
                            robot_id,
                            completed_action
                        )


                        print(
                            f"[MAP] ROBOT_{robot_id} "
                            f"completed "
                            f"{completed_action} | "
                            f"Position="
                            f"({robot.x},{robot.y}) | "
                            f"Direction="
                            f"{robot.orientation}"
                        )


                    robot.pending_command = None

                    robot.current_action = (
                        "IDLE"
                    )


                # ---------------------------------------------
                # BLOCKED
                # ---------------------------------------------

                elif status == "BLOCKED":

                    print(
                        f"[MAP] ROBOT_{robot_id} "
                        f"was BLOCKED"
                    )


                    # Do NOT update position.
                    robot.pending_command = None

                    robot.current_action = (
                        "BLOCKED"
                    )


                await broadcast_state()

                continue


            print(
                f"[ROBOT] Unknown message: "
                f"{data}"
            )


    except WebSocketDisconnect:

        pass

    except Exception as error:

        print(
            f"[ROBOT] Error: {error}"
        )

    finally:

        if robot_id is not None:

            remove_robot(
                robot_id,
                websocket
            )

            print(
                f"[ROBOT] ROBOT_{robot_id} "
                f"disconnected"
            )


        await broadcast_state()