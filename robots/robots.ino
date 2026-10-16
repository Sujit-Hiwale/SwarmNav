#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

// ============================================================
// WIFI
// ============================================================

const char* WIFI_SSID = "Sujit";
const char* WIFI_PASSWORD = "12345677";

// ============================================================
// ROBOT IDENTITY
// ============================================================

#define ROBOT_ID 2
#define ROBOT_HOSTNAME "rover-2"

// ============================================================
// SERVER
// ============================================================

const char* SERVER_HOST = "sujit";
const uint16_t SERVER_PORT = 8000;
const char* SERVER_WS_PATH = "/ws/robot";

// ============================================================
// MOTORS
// ============================================================

#define MOTOR_IN1 13
#define MOTOR_IN2 12
#define MOTOR_IN3 14
#define MOTOR_IN4 27

// ============================================================
// ULTRASONIC
// ============================================================

#define ULTRASONIC_TRIG 2
#define ULTRASONIC_ECHO 4

// ============================================================
// MOVEMENT SETTINGS
// ============================================================

bool movingForward = false;
bool movementActive = false;

unsigned long movementStartTime = 0;
unsigned long movementDuration = 0;

// Stop / blocked distance in centimeters
#define OBSTACLE_DISTANCE_CM 20.0

#define FORWARD_DURATION 1000
#define BACKWARD_DURATION 1000
#define LEFT_DURATION 500
#define RIGHT_DURATION 500

// ============================================================
// WEBSOCKET
// ============================================================

WebSocketsClient webSocket;

// ============================================================
// STATE
// ============================================================

bool mdnsReady = false;
bool serverConfigured = false;
bool serverConnected = false;

unsigned long lastServerResolve = 0;
unsigned long lastSensorReport = 0;

float frontDistance = -1.0;

// ============================================================
// FORWARD DECLARATIONS
// ============================================================

void sendStatus(const char* status);
void sendSensorData();
bool frontBlocked();
void executeCommand(const String& command);

// ============================================================
// MOTOR CONTROL
// ============================================================

void motorStop() {

    digitalWrite(MOTOR_IN1, LOW);
    digitalWrite(MOTOR_IN2, LOW);
    digitalWrite(MOTOR_IN3, LOW);
    digitalWrite(MOTOR_IN4, LOW);

    movingForward = false;
    movementActive = false;
}


// ------------------------------------------------------------
// FORWARD
// ------------------------------------------------------------

void motorForward() {

    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, LOW);

    digitalWrite(MOTOR_IN3, LOW);
    digitalWrite(MOTOR_IN4, HIGH);

    movingForward = true;
}


// ------------------------------------------------------------
// LEFT
// ------------------------------------------------------------

void motorLeft() {

    digitalWrite(MOTOR_IN1, LOW);
    digitalWrite(MOTOR_IN2, HIGH);

    digitalWrite(MOTOR_IN3, LOW);
    digitalWrite(MOTOR_IN4, HIGH);

    movingForward = false;
}


// ------------------------------------------------------------
// RIGHT
// ------------------------------------------------------------

void motorRight() {

    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, LOW);

    digitalWrite(MOTOR_IN3, HIGH);
    digitalWrite(MOTOR_IN4, LOW);

    movingForward = false;
}


// ------------------------------------------------------------
// BACKWARD
// ------------------------------------------------------------

void motorBackward() {

    digitalWrite(MOTOR_IN1, LOW);
    digitalWrite(MOTOR_IN2, HIGH);

    digitalWrite(MOTOR_IN3, HIGH);
    digitalWrite(MOTOR_IN4, LOW);

    movingForward = false;
}


// ============================================================
// MOVEMENT TIMER
// ============================================================

void startMovement(
    const String& command,
    unsigned long duration
) {

    motorStop();

    // --------------------------------------------------------
    // FORWARD
    // --------------------------------------------------------

    if (command == "FORWARD") {

        if (frontBlocked()) {

            sendStatus("BLOCKED");

            Serial.println(
                "[SAFETY] FORWARD BLOCKED"
            );

            return;
        }

        motorForward();
    }

    // --------------------------------------------------------
    // BACKWARD
    // --------------------------------------------------------

    else if (command == "BACKWARD") {

        motorBackward();
    }

    // --------------------------------------------------------
    // LEFT
    // --------------------------------------------------------

    else if (command == "LEFT") {

        motorLeft();
    }

    // --------------------------------------------------------
    // RIGHT
    // --------------------------------------------------------

    else if (command == "RIGHT") {

        motorRight();
    }

    // --------------------------------------------------------
    // START TIMER
    // --------------------------------------------------------

    movementStartTime = millis();
    movementDuration = duration;

    movementActive = true;
}


// ============================================================
// UPDATE MOVEMENT
// ============================================================

void updateMovement() {

    if (!movementActive) {
        return;
    }

    if (
        millis() - movementStartTime
        >= movementDuration
    ) {

        motorStop();

        sendStatus("ACTION_COMPLETE");
    }
}


// ============================================================
// ULTRASONIC
// ============================================================

float readUltrasonic() {

    digitalWrite(
        ULTRASONIC_TRIG,
        LOW
    );

    delayMicroseconds(2);

    digitalWrite(
        ULTRASONIC_TRIG,
        HIGH
    );

    delayMicroseconds(10);

    digitalWrite(
        ULTRASONIC_TRIG,
        LOW
    );

    unsigned long duration =
        pulseIn(
            ULTRASONIC_ECHO,
            HIGH,
            30000
        );

    if (duration == 0) {

        return -1.0;
    }

    float distance =
        (duration * 0.0343) / 2.0;

    return distance;
}


// ============================================================
// FORWARD SAFETY CHECK
// ============================================================

void checkForwardSafety() {

    if (!movingForward) {
        return;
    }

    float distance =
        readUltrasonic();

    if (distance >= 0) {

        frontDistance = distance;

        if (
            distance <=
            OBSTACLE_DISTANCE_CM
        ) {

            motorStop();

            Serial.print(
                "[SAFETY] Obstacle at "
            );

            Serial.print(
                distance
            );

            Serial.println(
                " cm - MOTOR STOPPED"
            );

            sendStatus("BLOCKED");
        }
    }
}


// ============================================================
// CHECK FRONT
// ============================================================

bool frontBlocked() {

    float distance =
        readUltrasonic();

    if (distance < 0) {

        // No echo:
        // do not treat as obstacle.
        return false;
    }

    frontDistance =
        distance;

    return (
        distance <=
        OBSTACLE_DISTANCE_CM
    );
}


// ============================================================
// SEND STATUS
// ============================================================

void sendStatus(
    const char* status
) {

    if (!serverConnected) {
        return;
    }

    StaticJsonDocument<128> doc;

    doc["robot_id"] =
        ROBOT_ID;

    doc["type"] =
        "STATUS";

    doc["status"] =
        status;

    String message;

    serializeJson(
        doc,
        message
    );

    webSocket.sendTXT(
        message
    );

    Serial.print(
        "[STATUS] "
    );

    Serial.println(
        message
    );
}


// ============================================================
// SEND SENSOR DATA
// ============================================================

void sendSensorData() {

    if (!serverConnected) {
        return;
    }

    StaticJsonDocument<128> doc;

    doc["robot_id"] =
        ROBOT_ID;

    doc["type"] =
        "SENSOR";

    if (frontDistance >= 0) {

        doc["front"] =
            frontDistance;
    }

    else {

        doc["front"] =
            nullptr;
    }

    String message;

    serializeJson(
        doc,
        message
    );

    webSocket.sendTXT(
        message
    );

    Serial.print(
        "[SENSOR] "
    );

    Serial.println(
        message
    );
}


// ============================================================
// EXECUTE COMMAND
// ============================================================

void executeCommand(
    const String& command
) {

    // --------------------------------------------------------
    // FORWARD
    // --------------------------------------------------------

    if (command == "FORWARD") {

        startMovement(
            command,
            FORWARD_DURATION
        );

        Serial.println(
            "[MOTOR] FORWARD"
        );

        return;
    }

    // --------------------------------------------------------
    // BACKWARD
    // --------------------------------------------------------

    if (command == "BACKWARD") {

        startMovement(
            command,
            BACKWARD_DURATION
        );

        Serial.println(
            "[MOTOR] BACKWARD"
        );

        return;
    }

    // --------------------------------------------------------
    // LEFT
    // --------------------------------------------------------

    if (command == "LEFT") {

        startMovement(
            command,
            LEFT_DURATION
        );

        Serial.println(
            "[MOTOR] LEFT"
        );

        return;
    }

    // --------------------------------------------------------
    // RIGHT
    // --------------------------------------------------------

    if (command == "RIGHT") {

        startMovement(
            command,
            RIGHT_DURATION
        );

        Serial.println(
            "[MOTOR] RIGHT"
        );

        return;
    }

    // --------------------------------------------------------
    // STOP
    // --------------------------------------------------------

    if (command == "STOP") {

        motorStop();

        sendStatus(
            "ACTION_COMPLETE"
        );

        Serial.println(
            "[MOTOR] STOP"
        );

        return;
    }

    Serial.print(
        "[MOTOR] Unsupported command: "
    );

    Serial.println(
        command
    );
}


// ============================================================
// mDNS
// ============================================================

bool startMDNS() {

    Serial.print(
        "Starting mDNS as "
    );

    Serial.print(
        ROBOT_HOSTNAME
    );

    Serial.println(
        ".local"
    );

    if (
        !MDNS.begin(
            ROBOT_HOSTNAME
        )
    ) {

        Serial.println(
            "mDNS FAILED"
        );

        return false;
    }

    Serial.println(
        "mDNS ready"
    );

    return true;
}


// ============================================================
// WEBSOCKET EVENT
// ============================================================

void webSocketEvent(
    WStype_t type,
    uint8_t* payload,
    size_t length
) {

    switch (type) {

        // ====================================================
        // CONNECTED
        // ====================================================

        case WStype_CONNECTED:

            serverConnected = true;

            Serial.println(
                "[WS] Connected to server"
            );

            {

                StaticJsonDocument<256> doc;

                doc["robot_id"] =
                    ROBOT_ID;

                doc["type"] =
                    "REGISTER";

                // Regular ESP32 has no camera
                doc["camera"] =
                    false;

                String message;

                serializeJson(
                    doc,
                    message
                );

                webSocket.sendTXT(
                    message
                );

                Serial.print(
                    "[WS] REGISTER -> "
                );

                Serial.println(
                    message
                );
            }

            break;


        // ====================================================
        // DISCONNECTED
        // ====================================================

        case WStype_DISCONNECTED:

            serverConnected =
                false;

            motorStop();

            Serial.println(
                "[WS] Disconnected"
            );

            break;


        // ====================================================
        // TEXT MESSAGE
        // ====================================================

        case WStype_TEXT:

            Serial.print(
                "[WS] RX: "
            );

            Serial.println(
                (char*)payload
            );

            {

                StaticJsonDocument<256> doc;

                DeserializationError error =
                    deserializeJson(
                        doc,
                        payload
                    );

                if (error) {

                    Serial.println(
                        "[WS] Invalid JSON"
                    );

                    break;
                }

                const char* command =
                    doc["command"];

                if (!command) {

                    break;
                }

                String cmd =
                    String(command);

                // ------------------------------------------------
                // MOTOR COMMANDS
                // ------------------------------------------------

                if (
                    cmd == "FORWARD" ||
                    cmd == "LEFT" ||
                    cmd == "RIGHT" ||
                    cmd == "BACKWARD" ||
                    cmd == "STOP"
                ) {

                    executeCommand(
                        cmd
                    );

                    break;
                }

                Serial.print(
                    "[WS] Unknown command: "
                );

                Serial.println(
                    cmd
                );
            }

            break;


        // ====================================================
        // ERROR
        // ====================================================

        case WStype_ERROR:

            Serial.println(
                "[WS] ERROR"
            );

            break;


        default:

            break;
    }
}


// ============================================================
// CONNECT TO SERVER
// ============================================================

bool connectToServer() {

    Serial.println(
        "Resolving"
    );

    Serial.println(
        SERVER_HOST
    );

    IPAddress serverIP =
        MDNS.queryHost(
            SERVER_HOST,
            5000
        );

    if (
        serverIP ==
        IPAddress(
            0,
            0,
            0,
            0
        )
    ) {

        Serial.println(
            "Server mDNS resolution FAILED"
        );

        return false;
    }

    Serial.print(
        "Server found: "
    );

    Serial.println(
        serverIP
    );

    webSocket.begin(
        serverIP.toString().c_str(),
        SERVER_PORT,
        SERVER_WS_PATH
    );

    webSocket.onEvent(
        webSocketEvent
    );

    webSocket.setReconnectInterval(
        5000
    );

    webSocket.enableHeartbeat(
        15000,
        3000,
        2
    );

    Serial.println(
        "[WS] Connection configured"
    );

    return true;
}


// ============================================================
// SETUP
// ============================================================

void setup() {

    Serial.begin(
        115200
    );

    delay(2000);

    Serial.println();
    Serial.println(
        "================================"
    );

    Serial.println(
        "        ESP32 ROBOT_2"
    );

    Serial.println(
        "================================"
    );


    // ========================================================
    // MOTOR INITIALIZATION
    // ========================================================

    pinMode(
        MOTOR_IN1,
        OUTPUT
    );

    pinMode(
        MOTOR_IN2,
        OUTPUT
    );

    pinMode(
        MOTOR_IN3,
        OUTPUT
    );

    pinMode(
        MOTOR_IN4,
        OUTPUT
    );

    motorStop();


    // ========================================================
    // ULTRASONIC INITIALIZATION
    // ========================================================

    pinMode(
        ULTRASONIC_TRIG,
        OUTPUT
    );

    pinMode(
        ULTRASONIC_ECHO,
        INPUT
    );

    digitalWrite(
        ULTRASONIC_TRIG,
        LOW
    );

    Serial.println(
        "[ULTRASONIC] Initialized"
    );


    // ========================================================
    // WIFI
    // ========================================================

    WiFi.mode(
        WIFI_STA
    );

    WiFi.begin(
        WIFI_SSID,
        WIFI_PASSWORD
    );

    Serial.print(
        "Connecting to WiFi"
    );

    while (
        WiFi.status() !=
        WL_CONNECTED
    ) {

        delay(500);

        Serial.print(
            "."
        );
    }

    Serial.println();

    Serial.println(
        "WiFi connected!"
    );

    Serial.print(
        "IP: "
    );

    Serial.println(
        WiFi.localIP()
    );


    // ========================================================
    // mDNS
    // ========================================================

    mdnsReady =
        startMDNS();


    // ========================================================
    // SERVER
    // ========================================================

    if (mdnsReady) {

        serverConfigured =
            connectToServer();
    }


    // ========================================================
    // READY
    // ========================================================

    Serial.println();

    Serial.println(
        "================================"
    );

    Serial.println(
        "          ROBOT READY"
    );

    Serial.println(
        "================================"
    );
}


// ============================================================
// LOOP
// ============================================================

void loop() {

    // ========================================================
    // WEBSOCKET
    // ========================================================

    if (serverConfigured) {

        webSocket.loop();
    }


    // ========================================================
    // ULTRASONIC SAFETY
    // ========================================================

    checkForwardSafety();


    // ========================================================
    // MOVEMENT TIMER
    // ========================================================

    updateMovement();


    // ========================================================
    // SENSOR REPORT
    // ========================================================

    if (
        millis() - lastSensorReport
        >= 500
    ) {

        lastSensorReport =
            millis();

        frontDistance =
            readUltrasonic();

        Serial.print(
            "[ULTRASONIC] Front: "
        );

        if (frontDistance >= 0) {

            Serial.print(
                frontDistance
            );

            Serial.println(
                " cm"
            );
        }

        else {

            Serial.println(
                "No echo"
            );
        }

        sendSensorData();
    }


    // ========================================================
    // RETRY SERVER CONNECTION
    // ========================================================

    if (
        !serverConfigured &&
        mdnsReady &&
        millis() - lastServerResolve
            > 5000
    ) {

        lastServerResolve =
            millis();

        serverConfigured =
            connectToServer();
    }


    delay(2);
}