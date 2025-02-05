const int enAPin = 7;
const int in1Pin = 6;
const int in2Pin = 5;
const int in3Pin = 4;
const int in4Pin = 2;
const int enBPin = 3;

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
}

void setup() {
    pinMode(enAPin, OUTPUT);
    pinMode(in1Pin, OUTPUT);
    pinMode(in2Pin, OUTPUT);
    pinMode(in3Pin, OUTPUT);
    pinMode(in4Pin, OUTPUT);
    pinMode(enBPin, OUTPUT);

    Serial.begin(9600);
}

void loop() {
    if (Serial.available()) {
        char direction = Serial.read();
        switch (direction) {
            case 'R':
                go(LEFT, -255);
                go(RIGHT, 255);
                break;
            case 'L':
                go(LEFT, 255);
                go(RIGHT, -255);
                break;
            default:
                stopMotors();
                break;
        }
    }
    else{
        stopMotors();
    }
}
