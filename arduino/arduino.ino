const int enAPin = 3;
const int in1Pin = 5;
const int in2Pin = 6;
const int in3Pin = 9;
const int in4Pin = 10;
const int enBPin = 11;

enum Motor { LEFT, RIGHT };

void go(enum Motor m, int speed) {
  digitalWrite(m == RIGHT ? in1Pin : in3Pin, speed > 0 ? LOW : HIGH);
  digitalWrite(m == RIGHT ? in2Pin : in4Pin, speed > 0 ? HIGH : LOW);
  analogWrite(m == RIGHT ? enAPin : enBPin, abs(speed));
}

void setup() {
  Serial.begin(115200);
  pinMode(enAPin, OUTPUT);
  pinMode(in1Pin, OUTPUT);
  pinMode(in2Pin, OUTPUT);
  pinMode(in3Pin, OUTPUT);
  pinMode(in4Pin, OUTPUT);
  pinMode(enBPin, OUTPUT);
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command.startsWith("H")) {
      int firstComma = command.indexOf(',');
      int secondComma = command.indexOf(',', firstComma + 1);
      if (firstComma != -1 && secondComma != -1) {
        String leftStr = command.substring(firstComma + 1, secondComma);
        String rightStr = command.substring(secondComma + 1);
        int leftSpeed = leftStr.toInt();
        int rightSpeed = rightStr.toInt();
        go(LEFT, leftSpeed);
        go(RIGHT, rightSpeed);
      }
    }
  }
}
