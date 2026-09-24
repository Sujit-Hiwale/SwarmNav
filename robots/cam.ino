#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "esp_camera.h"

// ============================================================
// WIFI
// ============================================================

const char* WIFI_SSID = "Sujit";
const char* WIFI_PASSWORD = "12345677";

// ============================================================
// ROBOT IDENTITY
// ============================================================

#define ROBOT_ID 1
#define ROBOT_HOSTNAME "rover-1"

// ============================================================
// SERVER
// ============================================================

const char* SERVER_HOST = "sujit";
const uint16_t SERVER_PORT = 8000;
const char* SERVER_WS_PATH = "/ws/robot";

// ============================================================
// MOTORS
// ============================================================

#define MOTOR_IN1 12
#define MOTOR_IN2 13
#define MOTOR_IN3 15
#define MOTOR_IN4 14

// ============================================================
// ULTRASONIC
// ============================================================

#define ULTRASONIC_TRIG 2
#define ULTRASONIC_ECHO 4

bool movingForward = false;
bool movementActive = false;
unsigned long movementStartTime = 0;
unsigned long movementDuration = 0;

// Stop/blocked distance in centimeters
#define OBSTACLE_DISTANCE_CM 20.0
#define FORWARD_DURATION 1000
#define BACKWARD_DURATION 1000
#define LEFT_DURATION 500
#define RIGHT_DURATION 500

// ============================================================
// CAMERA - AI THINKER ESP32-CAM
// ============================================================

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM       5

#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ============================================================
// OBJECTS
// ============================================================

WebServer cameraServer(80);
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

void motorForward() {
    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, LOW);
    digitalWrite(MOTOR_IN3, LOW);
    digitalWrite(MOTOR_IN4, HIGH);
    movingForward = true;
}

void motorLeft() {
    digitalWrite(MOTOR_IN1, LOW);
    digitalWrite(MOTOR_IN2, HIGH);
    digitalWrite(MOTOR_IN3, LOW);
    digitalWrite(MOTOR_IN4, HIGH);
    movingForward = false;
}

void motorRight() {
    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, LOW);
    digitalWrite(MOTOR_IN3, HIGH);
    digitalWrite(MOTOR_IN4, LOW);
    movingForward = false;
}
void motorBackward() {
    digitalWrite(MOTOR_IN1, LOW);
    digitalWrite(MOTOR_IN2, HIGH);
    digitalWrite(MOTOR_IN3, HIGH);
    digitalWrite(MOTOR_IN4, LOW);
    movingForward = false;
}

void startMovement(const String& command, unsigned long duration) {
    motorStop();

    if (command == "FORWARD") {
        if (frontBlocked()) {
            sendStatus("BLOCKED");
            return;
        }
        motorForward();
    } 
    else if (command == "BACKWARD") {
        motorBackward();
    } 
    else if (command == "LEFT") {
        motorLeft();
    } 
    else if (command == "RIGHT") {
        motorRight();
    }

    movementStartTime = millis();
    movementDuration = duration;
    movementActive = true;
}
void updateMovement() {
    if (!movementActive) {
        return;
    }

    if (millis() - movementStartTime >= movementDuration) {
        motorStop();
        sendStatus("ACTION_COMPLETE");
    }
}
// ============================================================
// ULTRASONIC
// ============================================================

float readUltrasonic() {

    digitalWrite(ULTRASONIC_TRIG, LOW);
    delayMicroseconds(2);

    digitalWrite(ULTRASONIC_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(ULTRASONIC_TRIG, LOW);

    unsigned long duration = pulseIn(
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

void checkForwardSafety() {
    if (!movingForward) {
        return;
    }

    float distance = readUltrasonic();

    if (distance >= 0) {
        frontDistance = distance;

        if (distance <= OBSTACLE_DISTANCE_CM) {
            motorStop();

            Serial.print("[SAFETY] Obstacle at ");
            Serial.print(distance);
            Serial.println(" cm - MOTOR STOPPED");

            sendStatus("BLOCKED");
        }
    }
}

bool frontBlocked() {

    float distance = readUltrasonic();

    if (distance < 0) {
        // No echo: don't treat it as an obstacle.
        return false;
    }

    frontDistance = distance;

    return distance <= OBSTACLE_DISTANCE_CM;
}

// ============================================================
// SEND STATUS
// ============================================================

void sendStatus(const char* status) {

    if (!serverConnected) {
        return;
    }

    StaticJsonDocument<128> doc;

    doc["robot_id"] = ROBOT_ID;
    doc["type"] = "STATUS";
    doc["status"] = status;

    String message;

    serializeJson(
        doc,
        message
    );

    webSocket.sendTXT(message);

    Serial.print("[STATUS] ");
    Serial.println(message);
}

// ============================================================
// SEND SENSOR DATA
// ============================================================

void sendSensorData() {

    if (!serverConnected) {
        return;
    }

    StaticJsonDocument<128> doc;

    doc["robot_id"] = ROBOT_ID;
    doc["type"] = "SENSOR";

    if (frontDistance >= 0) {
        doc["front"] = frontDistance;
    } else {
        doc["front"] = nullptr;
    }

    String message;

    serializeJson(
        doc,
        message
    );

    webSocket.sendTXT(message);

    Serial.print("[SENSOR] ");
    Serial.println(message);
}

void executeCommand(const String& command) {

    if (command == "FORWARD") {
        startMovement(command, FORWARD_DURATION);
        Serial.println("[MOTOR] FORWARD");
        return;
    }

    if (command == "BACKWARD") {
        startMovement(command, BACKWARD_DURATION);
        Serial.println("[MOTOR] BACKWARD");
        return;
    }

    if (command == "LEFT") {
        startMovement(command, LEFT_DURATION);
        Serial.println("[MOTOR] LEFT");
        return;
    }

    if (command == "RIGHT") {
        startMovement(command, RIGHT_DURATION);
        Serial.println("[MOTOR] RIGHT");
        return;
    }

    if (command == "STOP") {
        motorStop();
        sendStatus("ACTION_COMPLETE");
        Serial.println("[MOTOR] STOP");
        return;
    }

    Serial.print("[MOTOR] Unsupported command: ");
    Serial.println(command);
}

void handleStream() {

    WiFiClient client =
        cameraServer.client();

    camera_fb_t* fb = nullptr;

    client.println(
        "HTTP/1.1 200 OK"
    );

    client.println(
        "Content-Type: multipart/x-mixed-replace; boundary=frame"
    );

    client.println(
        "Cache-Control: no-cache"
    );

    client.println(
        "Connection: close"
    );

    client.println();

    while (client.connected()) {

        fb = esp_camera_fb_get();

        if (!fb) {

            Serial.println(
                "Camera capture failed"
            );

            break;
        }

        client.printf(
            "--frame\r\n"
            "Content-Type: image/jpeg\r\n"
            "Content-Length: %u\r\n\r\n",
            fb->len
        );

        client.write(
            fb->buf,
            fb->len
        );

        client.print(
            "\r\n"
        );

        esp_camera_fb_return(fb);

        delay(30);
    }
}

// ============================================================
// CAMERA
// ============================================================

bool startCamera() {

    camera_config_t config;

    config.ledc_channel =
        LEDC_CHANNEL_0;

    config.ledc_timer =
        LEDC_TIMER_0;

    config.pin_d0 =
        Y2_GPIO_NUM;

    config.pin_d1 =
        Y3_GPIO_NUM;

    config.pin_d2 =
        Y4_GPIO_NUM;

    config.pin_d3 =
        Y5_GPIO_NUM;

    config.pin_d4 =
        Y6_GPIO_NUM;

    config.pin_d5 =
        Y7_GPIO_NUM;

    config.pin_d6 =
        Y8_GPIO_NUM;

    config.pin_d7 =
        Y9_GPIO_NUM;

    config.pin_xclk =
        XCLK_GPIO_NUM;

    config.pin_pclk =
        PCLK_GPIO_NUM;

    config.pin_vsync =
        VSYNC_GPIO_NUM;

    config.pin_href =
        HREF_GPIO_NUM;

    config.pin_sccb_sda =
        SIOD_GPIO_NUM;

    config.pin_sccb_scl =
        SIOC_GPIO_NUM;

    config.pin_pwdn =
        PWDN_GPIO_NUM;

    config.pin_reset =
        RESET_GPIO_NUM;

    config.xclk_freq_hz =
        20000000;

    config.pixel_format =
        PIXFORMAT_JPEG;

    if (psramFound()) {

        config.frame_size =
            FRAMESIZE_QVGA;

        config.jpeg_quality =
            12;

        config.fb_count =
            2;

        config.grab_mode =
            CAMERA_GRAB_LATEST;
    }

    else {

        config.frame_size =
            FRAMESIZE_QQVGA;

        config.jpeg_quality =
            15;

        config.fb_count =
            1;

        config.grab_mode =
            CAMERA_GRAB_WHEN_EMPTY;
    }

    esp_err_t result =
        esp_camera_init(&config);

    if (result != ESP_OK) {

        Serial.printf(
            "Camera init FAILED: 0x%x\n",
            result
        );

        return false;
    }

    sensor_t* sensor =
        esp_camera_sensor_get();

    if (sensor) {

        sensor->set_framesize(
            sensor,
            FRAMESIZE_QVGA
        );
    }

    Serial.println(
        "Camera initialized!"
    );

    cameraServer.on(
        "/stream",
        HTTP_GET,
        handleStream
    );

    cameraServer.on(
        "/",
        HTTP_GET,
        []() {

            cameraServer.send(
                200,
                "text/plain",
                "ROVER_1 CAMERA ONLINE"
            );
        }
    );

    cameraServer.begin();

    Serial.println(
        "Camera server started"
    );

    Serial.print(
        "Camera: http://"
    );

    Serial.print(
        ROBOT_HOSTNAME
    );

    Serial.println(
        ".local/stream"
    );

    return true;
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

    if (!MDNS.begin(
        ROBOT_HOSTNAME
    )) {

        Serial.println(
            "mDNS FAILED"
        );

        return false;
    }

    MDNS.addService(
        "http",
        "tcp",
        80
    );

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

                doc["camera"] =
                    true;

                doc["camera_host"] =
                    String(
                        ROBOT_HOSTNAME
                    ) + ".local";

                doc["camera_stream"] =
                    "http://" +
                    String(
                        ROBOT_HOSTNAME
                    ) +
                    ".local/stream";

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

        case WStype_DISCONNECTED:

            serverConnected = false;

            motorStop();

            Serial.println(
                "[WS] Disconnected"
            );

            break;

        case WStype_TEXT: {

            Serial.print(
                "[WS] RX: "
            );

            Serial.println(
                (char*)payload
            );

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

            if (
                cmd == "FORWARD" ||
                cmd == "LEFT" ||
                cmd == "RIGHT" ||
                cmd == "BACKWARD" ||
                cmd == "STOP"
            ) {

                executeCommand(cmd);

                break;
            }

            Serial.print(
                "[WS] Unknown command: "
            );

            Serial.println(
                cmd
            );

            break;
        }

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
            0, 0, 0, 0
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

    Serial.begin(115200);
    delay(2000);

    Serial.println();
    Serial.println("================================");

    Serial.println("      ESP32-CAM ROBOT_1");

    Serial.println("================================");

    pinMode(MOTOR_IN1,OUTPUT);
    pinMode(MOTOR_IN2,OUTPUT);
    pinMode(MOTOR_IN3,OUTPUT);
    pinMode(MOTOR_IN4,OUTPUT);
    motorStop();

    pinMode(ULTRASONIC_TRIG, OUTPUT);
    pinMode(ULTRASONIC_ECHO, INPUT);
    digitalWrite(ULTRASONIC_TRIG, LOW);

    Serial.println("[ULTRASONIC] Initialized");

    WiFi.mode(WIFI_STA);

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    Serial.print("Connecting to WiFi");

    while (WiFi.status() != WL_CONNECTED) {

        delay(500);

        Serial.print(".");
    }

    Serial.println();

    Serial.println("WiFi connected!");

    Serial.print("IP: ");
    Serial.println(WiFi.localIP());

    // --------------------------------------------------------
    // mDNS
    // --------------------------------------------------------

    mdnsReady = startMDNS();

    // --------------------------------------------------------
    // CAMERA
    // --------------------------------------------------------

    startCamera();

    // --------------------------------------------------------
    // SERVER
    // --------------------------------------------------------

    if (mdnsReady) {

        serverConfigured =
            connectToServer();
    }

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

    cameraServer.handleClient();

    if (serverConfigured) {

        webSocket.loop();
    }

    checkForwardSafety();
    updateMovement();

    if (millis() - lastSensorReport >= 500) {

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

    // --------------------------------------------------------
    // Retry server mDNS resolution
    // --------------------------------------------------------

    if (
        !serverConfigured &&
        mdnsReady &&
        millis() - lastServerResolve > 5000
    ) {

        lastServerResolve =
            millis();

        serverConfigured =
            connectToServer();
    }

    delay(2);
}