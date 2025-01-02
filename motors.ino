const int enAPin = 7;
const int in1Pin = 6;
const int in2Pin = 5;
const int in3Pin = 4;
const int in4Pin = 2;
const int enBPin = 3;

const unsigned long serialTimeout = 3000;
const unsigned long forwardTime = 5000;

unsigned long lastSerialTime = 0;
unsigned long lastMoveTime = 0;

enum Motor { LEFT, RIGHT };

void go(enum Motor m, int speed) {
    digitalWrite(m == LEFT ? in1Pin : in3Pin, speed > 0 ? HIGH : LOW);
    digitalWrite(m == LEFT ? in2Pin : in4Pin, speed <= 0 ? HIGH : LOW);
    analogWrite(m == LEFT ? enAPin : enBPin, speed < 0 ? -speed : speed);
}

void stopMotors() {
    go(LEFT, 0);
    go(RIGHT, 0);
}

void rotate360(bool direction) {
    if (direction) {
        go(LEFT, 255);
        go(RIGHT, -255);
    } else {
        go(LEFT, -255);
        go(RIGHT, 255);
    }
    delay(2000);
    stopMotors();
}

void setup() {
    pinMode(enAPin, OUTPUT);
    pinMode(in1Pin, OUTPUT);
    pinMode(in2Pin, OUTPUT);
    pinMode(in3Pin, OUTPUT);
    pinMode(in4Pin, OUTPUT);
    pinMode(enBPin, OUTPUT);

    Serial.begin(9600);

    go(LEFT, 255);
    go(RIGHT, 255);

    lastSerialTime = millis();
    lastMoveTime = millis();
}

void loop() {
    if (Serial.available() > 0) {
        Serial.read();
        lastSerialTime = millis();
        stopMotors();
    } else {
        if (millis() - lastSerialTime > serialTimeout) {
            go(LEFT, 255);
            go(RIGHT, 255);
        }

        if (millis() - lastMoveTime >= forwardTime) {
            stopMotors();

            bool direction = random(0, 2);
            rotate360(direction);
            go(LEFT, 255);
            go(RIGHT, 255);

            lastMoveTime = millis();
        }
    }
    delay(50);
}
