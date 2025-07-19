#include <Arduino.h>

const int enAPin = 3;
const int in1Pin = 5;
const int in2Pin = 6;
const int in3Pin = 9;
const int in4Pin = 10;
const int enBPin = 11;

double Kp = 1.0, Ki = 0.1, Kd = 0.05;
double integral = 0;
double prev_error = 0;
double derivative = 0;
unsigned long prev_time = 0;
enum Motor { LEFT, RIGHT };
int base_speed = 100;
const int MIN_SPEED = 60;
const int MAX_SPEED = 255;

double MAX_INTEGRAL = 50.0;
double OUTPUT_LIMIT = 50.0;

void update_pid_limits() {
  OUTPUT_LIMIT = base_speed * 0.5;
  if (Ki > 0) {
    MAX_INTEGRAL = OUTPUT_LIMIT / Ki;
  } else {
    MAX_INTEGRAL = 50.0;
  }
}

enum MovementMode { MODE_FORWARD, MODE_LEFT, MODE_RIGHT, MODE_STOP };
MovementMode current_mode = MODE_FORWARD;
int mode_bias = 0;

unsigned long last_command_time = 0;
const unsigned long SAFETY_TIMEOUT = 200;

void go(enum Motor m, int speed) {
  digitalWrite(m == RIGHT ? in1Pin : in3Pin, speed > 0 ? LOW : HIGH);
  digitalWrite(m == RIGHT ? in2Pin : in4Pin, speed > 0 ? HIGH : LOW);
  analogWrite(m == RIGHT ? enAPin : enBPin, abs(speed));
}

void set_motors(int left_speed, int right_speed) {
  left_speed = constrain(left_speed, -MAX_SPEED, MAX_SPEED);
  right_speed = constrain(right_speed, -MAX_SPEED, MAX_SPEED);
  
  go(LEFT, left_speed);
  go(RIGHT, right_speed);
}

double compute_pid(double error) {
  unsigned long current_time = millis();
  double dt = (current_time - prev_time) / 1000.0;
  
  if (prev_time == 0 || dt > 1.0) {
    dt = 0.1;
  }
  
  double proportional = Kp * error;
  
  integral += error * dt;
  integral = constrain(integral, -MAX_INTEGRAL, MAX_INTEGRAL);
  double integral_term = Ki * integral;
  
  derivative = (error - prev_error) / dt;
  double derivative_term = Kd * derivative;
  
  prev_error = error;
  prev_time = current_time;
  
  double output = proportional + integral_term + derivative_term;
  
  Serial.print("P:"); Serial.print(proportional);
  Serial.print(" I:"); Serial.print(integral_term);
  Serial.print(" D:"); Serial.print(derivative_term);
  Serial.print(" Out:"); Serial.println(output);
  
  return output;
}

void apply_pid_with_mode(double error) {
  double pid_output = compute_pid(error);
  pid_output = constrain(pid_output, -OUTPUT_LIMIT, OUTPUT_LIMIT);
  
  int left_speed = base_speed;
  int right_speed = base_speed;
  
  switch (current_mode) {
    case MODE_FORWARD:
      left_speed = base_speed - pid_output;
      right_speed = base_speed + pid_output;
      break;
      
    case MODE_LEFT:
      left_speed = (base_speed - mode_bias) - pid_output;
      right_speed = (base_speed + mode_bias) + pid_output;
      break;
      
    case MODE_RIGHT:
      left_speed = (base_speed + mode_bias) - pid_output;
      right_speed = (base_speed - mode_bias) + pid_output;
      break;
      
    case MODE_STOP:
      left_speed = 0;
      right_speed = 0;
      break;
  }
  
  if (current_mode != MODE_STOP) {
    if (abs(left_speed) < MIN_SPEED && left_speed != 0) {
      left_speed = (left_speed > 0) ? MIN_SPEED : -MIN_SPEED;
    }
    if (abs(right_speed) < MIN_SPEED && right_speed != 0) {
      right_speed = (right_speed > 0) ? MIN_SPEED : -MIN_SPEED;
    }
  }
  
  set_motors(left_speed, right_speed);
  
  Serial.print("Mode:"); Serial.print(current_mode);
  Serial.print(" Error:"); Serial.print(error);
  Serial.print(" L:"); Serial.print(left_speed);
  Serial.print(" R:"); Serial.println(right_speed);
}

void reset_pid() {
  integral = 0;
  prev_error = 0;
  derivative = 0;
  prev_time = 0;
  Serial.println("PID Reset");
}

void setup() {
  Serial.begin(115200);
  pinMode(enAPin, OUTPUT);
  pinMode(in1Pin, OUTPUT);
  pinMode(in2Pin, OUTPUT);
  pinMode(in3Pin, OUTPUT);
  pinMode(in4Pin, OUTPUT);
  pinMode(enBPin, OUTPUT);
  update_pid_limits();
  
  set_motors(0, 0);
  Serial.println("Arduino PID Controller Ready");
}

void loop() {
  unsigned long current_time = millis();
  
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    last_command_time = current_time;
    
    if (command.startsWith("E")) {
      int first_comma = command.indexOf(',');
      int second_comma = command.indexOf(',', first_comma + 1);
      
      if (first_comma != -1) {
        double error = command.substring(first_comma + 1, 
                      second_comma != -1 ? second_comma : command.length()).toFloat();
        
        if (second_comma != -1) {
          String mode_str = command.substring(second_comma + 1);
          if (mode_str == "F") current_mode = MODE_FORWARD;
          else if (mode_str == "L") current_mode = MODE_LEFT;
          else if (mode_str == "R") current_mode = MODE_RIGHT;
          else if (mode_str == "S") current_mode = MODE_STOP;
        }
        
        apply_pid_with_mode(error);
      }
    }
    else if (command.startsWith("H")) {
      int firstComma = command.indexOf(',');
      int secondComma = command.indexOf(',', firstComma + 1);
      if (firstComma != -1 && secondComma != -1) {
        int left = command.substring(firstComma + 1, secondComma).toInt();
        int right = command.substring(secondComma + 1).toInt();
        set_motors(left, right);
        reset_pid(); 
      }
    }
    else if (command.startsWith("P")) {
      int first = command.indexOf(',');
      int second = command.indexOf(',', first + 1);
      int third = command.indexOf(',', second + 1);
      if (first != -1 && second != -1 && third != -1) {
        Kp = command.substring(first + 1, second).toFloat();
        Ki = command.substring(second + 1, third).toFloat();
        Kd = command.substring(third + 1).toFloat();
        update_pid_limits();
        reset_pid();
      }
    }
    else if (command.startsWith("S")) {
      int comma = command.indexOf(',');
      if (comma != -1) {
        base_speed = command.substring(comma + 1).toInt();
        base_speed = constrain(base_speed, 0, MAX_SPEED);
        update_pid_limits();
      }
    }
    else if (command.startsWith("B")) {
      int comma = command.indexOf(',');
      if (comma != -1) {
        mode_bias = command.substring(comma + 1).toInt();
        mode_bias = constrain(mode_bias, 0, 100);
        Serial.print("Mode bias set to: "); Serial.println(mode_bias);
      }
    }
    else if (command == "R") {
      reset_pid();
    }
    else if (command == "X") {
      current_mode = MODE_STOP;
      set_motors(0, 0);
      reset_pid();
    }
  }
  
  if (current_time - last_command_time > SAFETY_TIMEOUT) {
    current_mode = MODE_STOP;
    set_motors(0, 0);
  }
}