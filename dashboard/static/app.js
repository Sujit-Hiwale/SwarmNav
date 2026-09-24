const connectionElement =
    document.getElementById("connection");

const mapElement =
    document.getElementById("map");

const robotsElement =
    document.getElementById("robots");

const visitedElement =
    document.getElementById("visited");

const discoveredElement =
    document.getElementById("discovered");

const obstaclesElement =
    document.getElementById("obstacles");

const mapSizeElement =
    document.getElementById("map-size");


let socket;

let currentRobots = [];


// ============================================================
// WEBSOCKET
// ============================================================

function connect() {

    socket = new WebSocket(
        `ws://${window.location.host}/ws/dashboard`
    );


    socket.onopen = () => {

        connectionElement.textContent =
            "● Live";

        connectionElement.style.color =
            "#4ade80";
    };


    socket.onclose = () => {

        connectionElement.textContent =
            "● Disconnected";

        connectionElement.style.color =
            "#f87171";

        setTimeout(
            connect,
            2000
        );
    };


    socket.onerror = () => {

        socket.close();
    };


    socket.onmessage = event => {

        try {

            const state =
                JSON.parse(event.data);

            currentRobots =
                state.robots || [];

            render(state);

        }
        catch (error) {

            console.error(
                "Invalid server state:",
                error
            );
        }
    };
}


// ============================================================
// SEND CONTROL
// ============================================================

function sendControl(
    robotId,
    action,
    extra = {}
) {

    if (
        !socket ||
        socket.readyState !== WebSocket.OPEN
    ) {

        console.warn(
            "Dashboard WebSocket is not connected."
        );

        return;
    }


    const message = {

        type:
            "CONTROL",

        robot_id:
            Number(robotId),

        action:
            action,

        ...extra
    };


    console.log(
        "Sending:",
        message
    );


    socket.send(
        JSON.stringify(message)
    );
}


// ============================================================
// MODE
// ============================================================

function setRobotMode(
    robotId,
    mode
) {

    sendControl(

        robotId,

        "SET_MODE",

        {
            mode:
                mode
        }
    );
}


// ============================================================
// ROBOT COMMAND
// ============================================================

function sendRobotCommand(
    robotId,
    command
) {

    sendControl(

        robotId,

        "COMMAND",

        {
            command:
                command
        }
    );
}


// ============================================================
// RENDER
// ============================================================

function render(state) {

    renderMap(
        state.map || [],
        state.robots || []
    );


    renderRobots(
        state.robots || []
    );
}


// ============================================================
// MAP
// ============================================================

function renderMap(
    cells,
    robots
) {

    mapElement.innerHTML = "";


    if (
        cells.length === 0
    ) {

        mapSizeElement.textContent =
            "Map: 0 × 0";

        return;
    }


    const coordinates =
        cells.map(
            cell => [
                cell.x,
                cell.y
            ]
        );


    robots.forEach(
        robot => {

            coordinates.push([
                robot.x,
                robot.y
            ]);


            if (robot.path) {

                robot.path.forEach(
                    point => {

                        coordinates.push([
                            point.x,
                            point.y
                        ]);

                    }
                );
            }

        }
    );


    const xs =
        coordinates.map(
            point => point[0]
        );


    const ys =
        coordinates.map(
            point => point[1]
        );


    const minX =
        Math.min(...xs);

    const maxX =
        Math.max(...xs);

    const minY =
        Math.min(...ys);

    const maxY =
        Math.max(...ys);


    const width =
        maxX - minX + 1;

    const height =
        maxY - minY + 1;


    mapElement.style.gridTemplateColumns =
        `repeat(${width}, 55px)`;


    mapElement.style.gridTemplateRows =
        `repeat(${height}, 55px)`;


    mapSizeElement.textContent =
        `Map: ${width} × ${height}`;


    const cellMap =
        new Map();


    cells.forEach(
        cell => {

            cellMap.set(
                `${cell.x},${cell.y}`,
                cell
            );

        }
    );


    const pathMap =
        new Set();


    robots.forEach(
        robot => {

            if (!robot.path) {
                return;
            }


            robot.path.forEach(
                point => {

                    pathMap.add(
                        `${point.x},${point.y}`
                    );

                }
            );

        }
    );


    const robotMap =
        new Map();


    robots.forEach(
        robot => {

            robotMap.set(
                `${robot.x},${robot.y}`,
                robot
            );

        }
    );


    let visited = 0;

    let obstacles = 0;


    for (
        let y = maxY;
        y >= minY;
        y--
    ) {

        for (
            let x = minX;
            x <= maxX;
            x++
        ) {

            const div =
                document.createElement(
                    "div"
                );


            div.className =
                "cell";


            const key =
                `${x},${y}`;


            const cell =
                cellMap.get(key);


            const robot =
                robotMap.get(key);


            if (
                pathMap.has(key)
            ) {

                div.classList.add(
                    "path"
                );
            }


            if (cell) {

                if (
                    cell.type ===
                    "obstacle"
                ) {

                    div.classList.add(
                        "obstacle"
                    );

                    div.textContent =
                        "■";

                    obstacles++;

                }
                else if (
                    cell.visited
                ) {

                    div.classList.add(
                        "visited"
                    );

                    visited++;

                }
                else {

                    div.classList.add(
                        "unknown"
                    );
                }
            }


            if (
                x === 0 &&
                y === 0
            ) {

                div.classList.add(
                    "start"
                );


                if (!robot) {

                    div.textContent =
                        "S";
                }
            }


            if (robot) {

                div.classList.add(
                    "robot"
                );


                const label =
                    document.createElement(
                        "span"
                    );


                label.className =
                    "robot-label";


                label.textContent =
                    `R${robot.id}`;


                const direction =
                    document.createElement(
                        "span"
                    );


                direction.className =
                    "robot-direction";


                direction.textContent =
                    getDirectionArrow(
                        robot.orientation
                    );


                div.appendChild(
                    label
                );


                div.appendChild(
                    direction
                );
            }


            mapElement.appendChild(
                div
            );
        }
    }


    visitedElement.textContent =
        visited;


    discoveredElement.textContent =
        cells.length;


    obstaclesElement.textContent =
        obstacles;
}


// ============================================================
// DIRECTION
// ============================================================

function getDirectionArrow(
    orientation
) {

    switch (
        orientation
    ) {

        case "NORTH":
            return "↑";

        case "EAST":
            return "→";

        case "SOUTH":
            return "↓";

        case "WEST":
            return "←";

        default:
            return "•";
    }
}


// ============================================================
// ROBOTS
// ============================================================

function renderRobots(
    robots
) {

    robotsElement.innerHTML = "";


    if (
        robots.length === 0
    ) {

        robotsElement.innerHTML =
            "<p>No robots connected.</p>";

        return;
    }


    robots
        .sort(
            (a, b) =>
                a.id - b.id
        )
        .forEach(
            robot => {

                const card =
                    document.createElement(
                        "div"
                    );


                card.className =
                    "robot-card";


                const sensors =
                    robot.sensors || {};


                const manual =
                    robot.mode === "MANUAL";


                const online =
                    robot.status !==
                    "DISCONNECTED";


                card.innerHTML = `

                    <div class="robot-header">

                        <strong>
                            🤖 ROBOT_${robot.id}
                        </strong>

                        <span class="${
                            online
                                ? "online"
                                : "offline"
                        }">

                            ● ${
                                online
                                    ? "Online"
                                    : "Offline"
                            }

                        </span>

                    </div>


                    <div class="robot-info">

                        <div>
                            Position:
                            (${robot.x}, ${robot.y})
                        </div>


                        <div>
                            Direction:
                            ${robot.orientation}
                            ${getDirectionArrow(
                                robot.orientation
                            )}
                        </div>


                        <div>
                            Status:
                            ${robot.status}
                        </div>


                        <div>
                            Action:
                            ${robot.action}
                        </div>


                        <div class="mode-row">

                            <span>
                                Control:
                            </span>


                            <button
                                class="${
                                    manual
                                        ? "mode-active"
                                        : ""
                                }"
                                onclick="
                                    setRobotMode(
                                        ${robot.id},
                                        'MANUAL'
                                    )
                                "
                            >
                                🎮 Manual
                            </button>


                            <button
                                class="${
                                    !manual
                                        ? "mode-active"
                                        : ""
                                }"
                                onclick="
                                    setRobotMode(
                                        ${robot.id},
                                        'AUTO'
                                    )
                                "
                            >
                                🤖 Auto
                            </button>

                        </div>


                        <div class="mode-status">

                            ${
                                manual
                                    ? "🎮 MANUAL CONTROL ACTIVE"
                                    : "🤖 AUTOMATIC CONTROL"
                            }

                        </div>


                        <div class="controller">

                            <button
                                class="control-button up"
                                onclick="
                                    sendRobotCommand(
                                        ${robot.id},
                                        'FORWARD'
                                    )
                                "
                                ${!manual ? "disabled" : ""}
                            >
                                ↑
                                <small>
                                    Forward
                                </small>
                            </button>


                            <button
                                class="control-button left"
                                onclick="
                                    sendRobotCommand(
                                        ${robot.id},
                                        'LEFT'
                                    )
                                "
                                ${!manual ? "disabled" : ""}
                            >
                                ←
                                <small>
                                    Left
                                </small>
                            </button>


                            <button
                                class="control-button stop"
                                onclick="
                                    sendRobotCommand(
                                        ${robot.id},
                                        'STOP'
                                    )
                                "
                            >
                                ■
                                <small>
                                    Stop
                                </small>
                            </button>


                            <button
                                class="control-button right"
                                onclick="
                                    sendRobotCommand(
                                        ${robot.id},
                                        'RIGHT'
                                    )
                                "
                                ${!manual ? "disabled" : ""}
                            >
                                →
                                <small>
                                    Right
                                </small>
                            </button>


                            <button
                                class="control-button down"
                                onclick="
                                    sendRobotCommand(
                                        ${robot.id},
                                        'BACKWARD'
                                    )
                                "
                                ${!manual ? "disabled" : ""}
                            >
                                ↓
                                <small>
                                    Backward
                                </small>
                            </button>

                        </div>


                        <div class="sensor-grid">

                            <div class="sensor">

                                Front<br>

                                ${formatSensor(
                                    sensors.front
                                )}

                            </div>

                        </div>


                        <div>
                            Path:
                            ${
                                robot.path
                                    ? robot.path.length
                                    : 0
                            }
                            cells
                        </div>

                    </div>
                `;


                robotsElement.appendChild(
                    card
                );
            }
        );
}


// ============================================================
// SENSOR
// ============================================================

function formatSensor(
    value
) {

    if (
        value === null ||
        value === undefined
    ) {

        return "--";
    }


    const number =
        Number(value);


    if (
        !Number.isFinite(number)
    ) {

        return "--";
    }


    return `${Math.round(number)} cm`;
}


// ============================================================
// KEYBOARD
// ============================================================

document.addEventListener(
    "keydown",
    event => {

        // Ignore typing inside inputs.
        if (
            event.target.tagName === "INPUT" ||
            event.target.tagName === "TEXTAREA"
        ) {

            return;
        }


        // Find a manually controlled robot.
        const manualRobot =
            currentRobots.find(
                robot =>
                    robot.mode === "MANUAL"
            );


        if (!manualRobot) {

            return;
        }


        let command = null;


        switch (
            event.key.toLowerCase()
        ) {

            case "arrowup":
            case "w":

                command =
                    "FORWARD";

                break;


            case "arrowleft":
            case "a":

                command =
                    "LEFT";

                break;


            case "arrowright":
            case "d":

                command =
                    "RIGHT";

                break;


            case "arrowdown":
            case "s":

                command =
                    "BACKWARD";

                break;


            case " ":

                command =
                    "STOP";

                break;


            default:

                return;
        }


        event.preventDefault();


        sendRobotCommand(
            manualRobot.id,
            command
        );
    }
);


connect();