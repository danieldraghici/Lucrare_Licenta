//const int enAPin = 6;
//const int in1Pin = 7;
//const int in2Pin = 5;
//const int in3Pin = 4;
//const int in4Pin = 2;
//const int enBPin = 3;
//
//enum Motor
//{
//  LEFT,
//  RIGHT
//};
//
//void go(enum Motor m, int speed)
//{
//  digitalWrite(m == RIGHT ? in1Pin : in3Pin, speed > 0 ? LOW : HIGH);
//  digitalWrite(m == RIGHT ? in2Pin : in4Pin, speed > 0 ? HIGH : LOW);
//  analogWrite(m == RIGHT ? enAPin : enBPin, abs(speed));
//}
//
//void stopMotors()
//{
//  go(LEFT, 0);
//  go(RIGHT, 0);
//}
//void stopLeft()
//{
//  go(LEFT, 0);
//}
//void stopRight()
//{
//  go(RIGHT, 0);
//}
//void moveRight(int speed, float duration)
//{
//  stopLeft();
//  go(RIGHT, speed);
//  delay(duration);
//  stopRight();
//}
//void moveBackward(int speed, float duration)
//{
//  go(LEFT, -speed);
//  go(RIGHT, -speed);
//  delay(duration);
//  stopMotors();
//}
//void moveForward(int speed, float duration)
//{
//  go(LEFT, speed);
//  go(RIGHT, speed);
//  delay(duration);
//  stopMotors();
//}
//void moveLeft(int speed, float duration)
//{
//  stopRight();
//  go(LEFT, speed);
//  delay(duration);
//  stopLeft();
//}
//
//int speed1, speed2;
//
//void setup()
//{
//  Serial.begin(9600);
//  pinMode(enAPin, OUTPUT);
//  pinMode(in1Pin, OUTPUT);
//  pinMode(in2Pin, OUTPUT);
//  pinMode(in3Pin, OUTPUT);
//  pinMode(in4Pin, OUTPUT);
//  pinMode(enBPin, OUTPUT);
//}
//int a;
//int v[3];
//int i;
//void setMotor(int speed1,int speed2, float duration)
//{
//  if(speed1>0)
//  {
//    moveLeft(speed1, duration);
//  }
//  else
//  {
//    moveLeft(-speed1, duration);
//  }
//  if(speed2>0)
//  {
//    moveRight(speed2, duration);
//  }
//  else
//  {
//    moveRight(-speed2, duration);
//  }
//}
//void loop()
//{
//  if (Serial.available())
//  {
//    if (Serial.read() == 'H')
//    {
//      for (i = 0; i < 2; i++) {
//        v[i] = Serial.parseInt();
//      }
//      speed1 = v[0];
//      speed2 = v[1];
//      i = 0;
//
//      if(speed1 == speed2) {
//        if(speed1 > 0) {
//          moveForward(speed1, 1);
//        } else if(speed1 < 0) {
//          moveBackward(abs(speed1), 1);
//        } else {
//          stopMotors();
//        }
//      } else if(speed1 == 0) {
//        moveRight(speed2, 1);
//      } else if(speed2 == 0) {
//        moveLeft(speed1, 1);
//      } else {
//        setMotor(speed1, speed2,1);
//      }
//    }
//  }
//}
const int enAPin = 6;
const int in1Pin = 7;
const int in2Pin = 5;
const int in3Pin = 4;
const int in4Pin = 2;
const int enBPin = 3;

enum Motor { LEFT, RIGHT };

void go(enum Motor m, int speed) {
  digitalWrite(m == RIGHT ? in1Pin : in3Pin, speed > 0 ? LOW : HIGH);
  digitalWrite(m == RIGHT ? in2Pin : in4Pin, speed > 0 ? HIGH : LOW);
  analogWrite(m == RIGHT ? enAPin : enBPin, abs(speed));
}

void setup() {
  Serial.begin(9600);
  pinMode(enAPin, OUTPUT);
  pinMode(in1Pin, OUTPUT);
  pinMode(in2Pin, OUTPUT);
  pinMode(in3Pin, OUTPUT);
  pinMode(in4Pin, OUTPUT);
  pinMode(enBPin, OUTPUT);
}

int v[2];
int i;

void loop() {
  if (Serial.available()) {
    if (Serial.read() == 'H') {
      // Parse two integers for motor speeds
      for (i = 0; i < 2; i++) {
        v[i] = Serial.parseInt();
      }
      // Set left and right motor speeds directly
      go(LEFT, v[0]);
      go(RIGHT, v[1]);
    }
  }
}
