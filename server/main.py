import asyncio
import json
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    HTTPException,
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
    add_object_detection,
    get_camera_sector,
    camera_direction,
)
from .auto_controller import auto_controller
from .vision import Vision


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DASHBOARD_DIR = BASE_DIR / "dashboard"

TEMPLATE_DIR = DASHBOARD_DIR / "templates"
STATIC_DIR = DASHBOARD_DIR / "static"

VISION_DIR = BASE_DIR / "data" / "vision"
VISION_IMAGE_DIR = VISION_DIR / "images"
VISION_JSON_FILE = VISION_DIR / "detections.json"

VISION_IMAGE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

if not VISION_JSON_FILE.exists():
    VISION_JSON_FILE.write_text(
        "[]",
        encoding="utf-8"
    )

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Multi-Robot RL Explorer"
)

vision = Vision(
    model_path="yolov8n.pt",
    confidence=0.25,
)

async def capture_rover_view(robot_id: int):
    robot = robots.get(robot_id)

    if robot is None:
        print(f"[VISION] ROBOT_{robot_id} not connected")
        return None

    if robot_id == 1:
        return None

    if not getattr(robot, "camera_stream", None):
        print(f"[VISION] ROBOT_{robot_id} has no camera stream")
        return None

    # Current map position + orientation
    x = robot.x
    y = robot.y
    direction = robot.orientation

    # --------------------------------------------------------
    # Check whether this position + direction was already saved
    # --------------------------------------------------------
    try:
        existing = json.loads(
            VISION_JSON_FILE.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, FileNotFoundError):
        existing = []

    for record in existing:
        if (
            record.get("robot_id") == robot_id
            and record.get("robot_position", {}).get("x") == x
            and record.get("robot_position", {}).get("y") == y
            and record.get("robot_orientation") == direction
        ):
            print(
                f"[VISION] ROBOT_{robot_id}: "
                f"Already captured ({x}, {y}) facing {direction}"
            )
            return record

    # --------------------------------------------------------
    # Open rover camera
    # --------------------------------------------------------
    cap = cv2.VideoCapture(robot.camera_stream)

    if not cap.isOpened():
        print(
            f"[VISION] ✗ Cannot open camera: "
            f"{robot.camera_stream}"
        )
        return None

    try:
        # Give MJPEG stream a moment to provide a valid frame
        frame = None

        for _ in range(10):
            success, temp = await asyncio.to_thread(cap.read)

            if success and temp is not None:
                frame = temp
                break

            await asyncio.sleep(0.1)

        if frame is None:
            print(
                f"[VISION] ✗ Failed to capture "
                f"ROBOT_{robot_id}"
            )
            return None

    finally:
        cap.release()

    # --------------------------------------------------------
    # Save exactly ONE image
    # --------------------------------------------------------
    filename = (
        f"robot_{robot_id}_"
        f"{x}_{y}_"
        f"{direction}.jpg"
    )

    image_path = VISION_IMAGE_DIR / filename

    if not cv2.imwrite(str(image_path), frame):
        print(
            f"[VISION] ✗ Failed to save image: "
            f"{image_path}"
        )
        return None

    print(
        f"[VISION] ✓ Saved ROBOT_{robot_id}: "
        f"({x}, {y}) facing {direction}"
    )

    # --------------------------------------------------------
    # YOLO
    # --------------------------------------------------------
    detections = vision.process(frame)

    map_observations = []

    frame_height, frame_width = frame.shape[:2]

    for detection in detections:

        center_x, center_y = detection["center"]

        relative_direction = get_camera_sector(
            center_x,
            frame_width,
        )

        absolute_direction = camera_direction(
            direction,
            relative_direction,
        )

        observation = add_object_detection(
            robot_id=robot_id,
            class_name=detection["class"],
            confidence=detection["confidence"],
            image=None,
            direction=absolute_direction,
            distance=1,
        )

        if observation is not None:
            observation["relative_direction"] = relative_direction
            observation["camera_position"] = {
                "x": center_x,
                "y": center_y,
            }

            map_observations.append(observation)

    # --------------------------------------------------------
    # Save record
    # --------------------------------------------------------
    record = {
        "robot_id": robot_id,
        "robot_position": {
            "x": x,
            "y": y,
        },
        "robot_orientation": direction,
        "image": str(
            image_path.relative_to(BASE_DIR)
        ),
        "timestamp": datetime.now().isoformat(),
        "detections": map_observations,
    }

    existing.append(record)

    VISION_JSON_FILE.write_text(
        json.dumps(
            existing,
            indent=4,
        ),
        encoding="utf-8",
    )

    return record

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

app.mount(
    "/vision-images",
    StaticFiles(
        directory=str(VISION_IMAGE_DIR)
    ),
    name="vision-images",
)

# ============================================================
# DASHBOARD CLIENTS
# ============================================================

dashboard_clients: set[WebSocket] = set()


# ============================================================
# STATE
# ============================================================

def get_state():

    vision_data = []

    if VISION_JSON_FILE.exists():
        try:
            vision_data = json.loads(
                VISION_JSON_FILE.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            vision_data = []

    return {
        "robots": robot_data(),
        "map": get_map_data(),
        "vision": vision_data,
    }


# ============================================================
# BROADCAST STATE
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
# VISION IMAGE UPLOAD
# ============================================================

@app.post("/vision/{robot_id}")
async def receive_vision_image(
    robot_id: int,
    file: UploadFile = File(...),
):

    # --------------------------------------------------------
    # Only robots other than ROBOT_1 send vision frames.
    # --------------------------------------------------------

    if robot_id == 1:

        raise HTTPException(
            status_code=400,
            detail="ROBOT_1 does not use the server vision upload."
        )

    robot = robots.get(robot_id)

    if robot is None:

        raise HTTPException(
            status_code=404,
            detail=f"ROBOT_{robot_id} is not connected."
        )

    # --------------------------------------------------------
    # Read image
    # --------------------------------------------------------

    image_bytes = await file.read()

    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="Empty image received."
        )

    frame = cv2.imdecode(
        np.frombuffer(
            image_bytes,
            np.uint8
        ),
        cv2.IMREAD_COLOR
    )

    if frame is None:

        raise HTTPException(
            status_code=400,
            detail="Invalid image."
        )

    # --------------------------------------------------------
    # Generate filename
    # --------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    filename = (
        f"robot_{robot_id}_{timestamp}.jpg"
    )

    image_path = (
        VISION_IMAGE_DIR
        / filename
    )

    # --------------------------------------------------------
    # Save original image
    # --------------------------------------------------------

    cv2.imwrite(
        str(image_path),
        frame
    )

    # --------------------------------------------------------
    # Run YOLO
    # --------------------------------------------------------

    detections = vision.process(frame)

    print(
        f"[YOLO] ROBOT_{robot_id} "
        f"({x},{y}) facing {direction}: "
        f"{len(detections)} detections"
    )

    print(f"[YOLO] {detections}")

    # --------------------------------------------------------
    # Convert YOLO detections into map observations
    # --------------------------------------------------------

    map_observations = []

    frame_height, frame_width = frame.shape[:2]

    for detection in detections:

        center_x, center_y = detection["center"]

        # ----------------------------------------------------
        # Determine where the object appears in the camera.
        # ----------------------------------------------------

        relative_direction = get_camera_sector(
            center_x,
            frame_width,
        )

        # ----------------------------------------------------
        # Convert LEFT/CENTER/RIGHT into an absolute
        # NORTH/EAST/SOUTH/WEST direction.
        # ----------------------------------------------------

        absolute_direction = camera_direction(
            robot.orientation,
            relative_direction,
        )

        # ----------------------------------------------------
        # We don't have camera depth yet.
        #
        # Therefore assume the object occupies the
        # adjacent grid cell.
        #
        # Later ultrasonic/depth estimation can replace 1.
        # ----------------------------------------------------

        distance = 1

        observation = add_object_detection(

            robot_id=robot_id,

            class_name=detection["class"],

            confidence=detection["confidence"],

            image=frame,

            direction=absolute_direction,

            distance=distance,
        )

        if observation is not None:

            observation["relative_direction"] = (
                relative_direction
            )

            observation["camera_position"] = {
                "x": center_x,
                "y": center_y,
            }

            map_observations.append(
                observation
            )

    # --------------------------------------------------------
    # Convert detections to JSON-safe data
    # --------------------------------------------------------

    json_detections = map_observations

    # --------------------------------------------------------
    # Create observation
    # --------------------------------------------------------

    observation = {

        "robot_id":
            robot_id,

        "robot_position": {
            "x": robot.x,
            "y": robot.y,
        },

        "robot_orientation":
            robot.orientation,

        "image":
            str(
                image_path.relative_to(
                    BASE_DIR
                )
            ),

        "timestamp":
            datetime.now().isoformat(),

        "detections":
            json_detections,
    }

    # --------------------------------------------------------
    # Store JSON
    # --------------------------------------------------------

    try:

        existing = json.loads(
            VISION_JSON_FILE.read_text(
                encoding="utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        FileNotFoundError,
    ):

        existing = []

    existing.append(
        observation
    )

    VISION_JSON_FILE.write_text(
        json.dumps(
            existing,
            indent=4
        ),
        encoding="utf-8"
    )

    print(
        f"[VISION] ROBOT_{robot_id}: "
        f"{len(json_detections)} objects detected"
    )

    # --------------------------------------------------------
    # Return result to rover
    # --------------------------------------------------------

    return {

        "success":
            True,

        "robot_id":
            robot_id,

        "image":
            str(
                image_path.relative_to(
                    BASE_DIR
                )
            ),

        "position": {
            "x": robot.x,
            "y": robot.y,
        },

        "orientation":
            robot.orientation,

        "detections":
            json_detections,
    }

@app.post("/vision/capture/{robot_id}")
async def capture_vision(robot_id: int):

    record = await capture_rover_view(robot_id)

    if record is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to capture rover image"
        )

    return record

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

    # Send current state immediately
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

        # New ESP32 supports only these commands
        allowed_commands = {
            "FORWARD",
            "BACKWARD",
            "LEFT",
            "RIGHT",
            "STOP",
        }

        if command not in allowed_commands:

            print(
                f"[CONTROL] Invalid command: "
                f"{command}"
            )

            return

        # ------------------------------------------------
        # Don't allow another movement while busy
        # ------------------------------------------------

        if (
            robot.pending_command
            and command != "STOP"
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

        success = await send_command(robot_id, command)

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

                robot = robots.get(
                    robot_id
                )

                # Store camera information
                if robot is not None:

                    robot.camera = data.get(
                        "camera",
                        False
                    )

                    robot.camera_host = data.get(
                        "camera_host"
                    )

                    robot.camera_stream = data.get(
                        "camera_stream"
                    )

                print(
                    f"[ROBOT] ✓ "
                    f"ROBOT_{robot_id} "
                    f"registered"
                )

                if robot is not None:

                    print(
                        f"[CAMERA] ROBOT_{robot_id}: "
                        f"{robot.camera_stream}"
                    )

                await websocket.send_text(
                    json.dumps({
                        "robot_id":
                            robot_id,

                        "type":
                            "REGISTERED",

                        "camera":
                            data.get(
                                "camera",
                                False
                            ),

                        "camera_host":
                            data.get(
                                "camera_host"
                            ),

                        "camera_stream":
                            data.get(
                                "camera_stream"
                            ),
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

                # New robot has only FRONT ultrasonic
                robot.front_distance = (
                    data.get("front")
                )

                # No left/right sensors anymore
                robot.left_distance = None
                robot.right_distance = None

                # Update camera information if supplied
                if "camera" in data:

                    robot.camera = data.get(
                        "camera"
                    )

                if "camera_host" in data:

                    robot.camera_host = data.get(
                        "camera_host"
                    )

                if "camera_stream" in data:

                    robot.camera_stream = data.get(
                        "camera_stream"
                    )

                robot.status = (
                    "SENSORS_UPDATED"
                )

                # Mark only front obstacle
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

                        # Only movement commands affect map
                        if completed_action in {
                            "FORWARD",
                            "BACKWARD",
                            "LEFT",
                            "RIGHT",
                        }:

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

                            if robot_id != 1 and robot.camera_stream:
                                await capture_rover_view(robot_id)

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

                    # Do NOT update position
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