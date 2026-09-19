#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// ============================================================
// ROBOT ID
// Change this before uploading to each ESP32
//
// Robot 1 -> 1
// Robot 2 -> 2
// Robot 3 -> 3
// ============================================================

#define ROBOT_ID 2


// ============================================================
// WIFI
// ============================================================

const char* WIFI_SSID = "Sujit";
const char* WIFI_PASSWORD = "12345677";


// ============================================================
// SERVER
// IMPORTANT:
// Replace this with your LAPTOP'S IP address on the
// "Sujit" hotspot network.
//
// ============================================================

const char* SERVER_IP = "172.25.154.139";

const uint16_t SERVER_PORT = 8000;


// ============================================================
// L298N MOTOR PINS
//
// LEFT SIDE  -> IN1 / IN2
// RIGHT SIDE -> IN3 / IN4
//
// The two physical left motors should be connected together
// to the left L298N channel.
// The two physical right motors should be connected together
// to the right L298N channel.
// ============================================================

#define IN1 25
#define IN2 26

#define IN3 27
#define IN4 14


// L298N enable pins
#define ENA 33
#define ENB 32


// ============================================================
// ULTRASONIC SENSOR
// ============================================================

#define TRIG_PIN 5
#define ECHO_PIN 34


// ============================================================
// SERVO
// ============================================================

#define SERVO_PIN 13

#define LEFT_ANGLE 45
#define FRONT_ANGLE 90
#define RIGHT_ANGLE 135


Servo scannerServo;

WebSocketsClient webSocket;


// ============================================================
// MOVEMENT
// ============================================================

// One grid/block movement.
//
// This MUST eventually be calibrated for your robot.
unsigned long BLOCK_TIME = 800;

// Approximate 90-degree turning time.
//
// This MUST also be calibrated.
unsigned long TURN_TIME = 450;


// Motor speed: 0-255
int MOTOR_SPEED = 200;


// Minimum safe distance in cm
const float SAFE_DISTANCE = 20.0;


// ============================================================
// MOTOR CONTROL
// ============================================================

void setLeftMotor(int speed)
{
    if (speed > 0)
    {
        digitalWrite(IN1, HIGH);
        digitalWrite(IN2, LOW);

        ledcWrite(ENA, speed);
    }
    else if (speed < 0)
    {
        digitalWrite(IN1, LOW);
        digitalWrite(IN2, HIGH);

        ledcWrite(ENA, -speed);
    }
    else
    {
        digitalWrite(IN1, LOW);
        digitalWrite(IN2, LOW);

        ledcWrite(ENA, 0);
    }
}


void setRightMotor(int speed)
{
    if (speed > 0)
    {
        digitalWrite(IN3, HIGH);
        digitalWrite(IN4, LOW);

        ledcWrite(ENB, speed);
    }
    else if (speed < 0)
    {
        digitalWrite(IN3, LOW);
        digitalWrite(IN4, HIGH);

        ledcWrite(ENB, -speed);
    }
    else
    {
        digitalWrite(IN3, LOW);
        digitalWrite(IN4, LOW);

        ledcWrite(ENB, 0);
    }
}


// ============================================================
// MOVEMENT
// ============================================================

void stopMotors()
{
    setLeftMotor(0);
    setRightMotor(0);
}


void moveForward()
{
    setLeftMotor(MOTOR_SPEED);
    setRightMotor(MOTOR_SPEED);
}


void moveBackward()
{
    setLeftMotor(-MOTOR_SPEED);
    setRightMotor(-MOTOR_SPEED);
}


void turnLeft()
{
    setLeftMotor(0);
    setRightMotor(MOTOR_SPEED);
}


void turnRight()
{
    setLeftMotor(MOTOR_SPEED);
    setRightMotor(0);
}


// ============================================================
// ULTRASONIC
// ============================================================

float getDistance()
{
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);

    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);

    digitalWrite(TRIG_PIN, LOW);

    long duration = pulseIn(
        ECHO_PIN,
        HIGH,
        30000
    );

    if (duration == 0)
    {
        return 400.0;
    }

    return duration * 0.0343 / 2.0;
}


// ============================================================
// SERVO SCANNING
// ============================================================

float scanAngle(int angle)
{
    scannerServo.write(angle);

    delay(300);

    return getDistance();
}


void performScan()
{
    float leftDistance;
    float frontDistance;
    float rightDistance;


    // LEFT
    leftDistance = scanAngle(LEFT_ANGLE);


    // FRONT
    frontDistance = scanAngle(FRONT_ANGLE);


    // RIGHT
    rightDistance = scanAngle(RIGHT_ANGLE);


    // Return servo to front
    scannerServo.write(FRONT_ANGLE);


    StaticJsonDocument<256> doc;

    doc["robot_id"] = ROBOT_ID;
    doc["type"] = "SENSOR";

    doc["left"] = leftDistance;
    doc["front"] = frontDistance;
    doc["right"] = rightDistance;


    String output;

    serializeJson(
        doc,
        output
    );


    webSocket.sendTXT(output);


    Serial.print("SCAN | L: ");
    Serial.print(leftDistance);

    Serial.print(" | F: ");
    Serial.print(frontDistance);

    Serial.print(" | R: ");
    Serial.println(rightDistance);
}


// ============================================================
// STATUS
// ============================================================

void sendStatus(const char* status)
{
    StaticJsonDocument<160> doc;

    doc["robot_id"] = ROBOT_ID;
    doc["type"] = "STATUS";
    doc["status"] = status;


    String output;

    serializeJson(
        doc,
        output
    );


    webSocket.sendTXT(output);


    Serial.print("STATUS: ");
    Serial.println(status);
}


// ============================================================
// EXECUTE ONE COMMAND
// ============================================================

void executeCommand(String command)
{
    Serial.print("COMMAND: ");
    Serial.println(command);


    // --------------------------------------------------------
    // SCAN
    // --------------------------------------------------------

    if (command == "SCAN")
    {
        performScan();
        
        return;
    }


    // --------------------------------------------------------
    // STOP
    // --------------------------------------------------------

    if (command == "STOP")
    {
        stopMotors();

        sendStatus("ACTION_COMPLETE");

        return;
    }


    sendStatus("MOVING");


    // --------------------------------------------------------
    // FORWARD
    // --------------------------------------------------------

    if (command == "FORWARD")
    {
        scannerServo.write(FRONT_ANGLE);

        delay(150);

        float frontDistance =
            getDistance();


        Serial.print(
            "Front distance: "
        );

        Serial.println(
            frontDistance
        );


        // Safety check
        if (frontDistance < SAFE_DISTANCE)
        {
            stopMotors();

            sendStatus("BLOCKED");

            performScan();

            return;
        }


        moveForward();

        delay(BLOCK_TIME);

        stopMotors();
    }


    // --------------------------------------------------------
    // BACKWARD
    // --------------------------------------------------------

    else if (command == "BACKWARD")
    {
        moveBackward();

        delay(BLOCK_TIME);

        stopMotors();
    }


    // --------------------------------------------------------
    // LEFT
    // --------------------------------------------------------

    else if (command == "LEFT")
    {
        turnLeft();

        delay(TURN_TIME);

        stopMotors();
    }


    // --------------------------------------------------------
    // RIGHT
    // --------------------------------------------------------

    else if (command == "RIGHT")
    {
        turnRight();

        delay(TURN_TIME);

        stopMotors();
    }


    // --------------------------------------------------------
    // UNKNOWN COMMAND
    // --------------------------------------------------------

    else
    {
        stopMotors();

        sendStatus("UNKNOWN_COMMAND");

        return;
    }


    // --------------------------------------------------------
    // MOVEMENT COMPLETED
    // --------------------------------------------------------

    sendStatus(
        "ACTION_COMPLETE"
    );


    // Immediately scan surroundings
    performScan();
}


// ============================================================
// WEBSOCKET EVENT
// ============================================================

void webSocketEvent(
    WStype_t type,
    uint8_t* payload,
    size_t length
)
{
    switch (type)
    {
        // ----------------------------------------------------
        // DISCONNECTED
        // ----------------------------------------------------

        case WStype_DISCONNECTED:

            Serial.println(
                "WebSocket disconnected"
            );

            break;


        // ----------------------------------------------------
        // CONNECTED
        // ----------------------------------------------------

        case WStype_CONNECTED:

            Serial.println(
                "Connected to server"
            );


            {
                StaticJsonDocument<128> doc;

                doc["robot_id"] = ROBOT_ID;
                doc["type"] = "REGISTER";


                String output;

                serializeJson(
                    doc,
                    output
                );


                webSocket.sendTXT(
                    output
                );
            }

            break;


        // ----------------------------------------------------
        // MESSAGE
        // ----------------------------------------------------

        case WStype_TEXT:
        {
            Serial.print(
                "SERVER: "
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


            if (error)
            {
                Serial.println(
                    "Invalid JSON received"
                );

                return;
            }


            int targetRobot =
                doc["robot_id"];


            // Ignore commands intended
            // for another robot

            if (
                targetRobot != ROBOT_ID
            )
            {
                return;
            }


            String command =
                doc["command"];


            executeCommand(
                command
            );


            break;
        }


        default:

            break;
    }
}


// ============================================================
// WIFI
// ============================================================

void connectWiFi()
{
    Serial.println();
    Serial.print(
        "Connecting to WiFi: "
    );

    Serial.println(
        WIFI_SSID
    );


    WiFi.begin(
        WIFI_SSID,
        WIFI_PASSWORD
    );


    while (
        WiFi.status() != WL_CONNECTED
    )
    {
        delay(500);

        Serial.print(".");
    }


    Serial.println();

    Serial.println(
        "WiFi connected!"
    );


    Serial.print(
        "ESP32 IP: "
    );

    Serial.println(
        WiFi.localIP()
    );
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
    Serial.begin(115200);

    delay(1000);


    Serial.println();
    Serial.println(
        "=============================="
    );

    Serial.print(
        "ROBOT_"
    );

    Serial.println(
        ROBOT_ID
    );

    Serial.println(
        "=============================="
    );


    // --------------------------------------------------------
    // Motor pins
    // --------------------------------------------------------

    pinMode(IN1, OUTPUT);
    pinMode(IN2, OUTPUT);

    pinMode(IN3, OUTPUT);
    pinMode(IN4, OUTPUT);


    // --------------------------------------------------------
    // PWM
    // --------------------------------------------------------

    ledcAttach(
        ENA,
        1000,
        8
    );

    ledcAttach(
        ENB,
        1000,
        8
    );


    stopMotors();


    // --------------------------------------------------------
    // Ultrasonic
    // --------------------------------------------------------

    pinMode(
        TRIG_PIN,
        OUTPUT
    );

    pinMode(
        ECHO_PIN,
        INPUT
    );


    // --------------------------------------------------------
    // Servo
    // --------------------------------------------------------

    scannerServo.setPeriodHertz(
        50
    );

    scannerServo.attach(
        SERVO_PIN,
        500,
        2400
    );

    scannerServo.write(
        FRONT_ANGLE
    );


    // --------------------------------------------------------
    // WiFi
    // --------------------------------------------------------

    connectWiFi();


    // --------------------------------------------------------
    // WebSocket
    // --------------------------------------------------------

    webSocket.begin(
        SERVER_IP,
        SERVER_PORT,
        "/ws/robot"
    );


    webSocket.onEvent(
        webSocketEvent
    );


    webSocket.setReconnectInterval(
        5000
    );


    Serial.println();
    Serial.println(
        "Robot ready."
    );
}

void loop()
{
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("WiFi disconnected. Reconnecting...");
        connectWiFi();
    }

    webSocket.loop();

    delay(10);
}