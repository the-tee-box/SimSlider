/*
 * GSPro Linear Actuator Controller
 * Controls 12V linear actuator via BTS7960 motor driver
 * Receives commands from PC via Serial USB
 * 
 * Hardware Connections:
 * BTS7960 Motor Driver:
 *   - RPWM (right PWM) -> Arduino Pin 5
 *   - LPWM (left PWM) -> Arduino Pin 6
 *   - R_EN (right enable) -> Arduino Pin 7
 *   - L_EN (left enable) -> Arduino Pin 8
 *   - VCC -> 5V (from Arduino or buck converter)
 *   - GND -> Arduino GND
 *   - B+ -> 12V Power Supply +
 *   - B- -> 12V Power Supply -
 *   - M+ -> Actuator wire 1
 *   - M- -> Actuator wire 2
 * 
 * Status LEDs:
 *   - Red (LH position) -> Pin 10
 *   - Green (RH position) -> Pin 11
 *   - Yellow (Moving) -> Pin 12
 * 
 * Emergency Stop (optional):
 *   - E-stop button (NC) -> Pin 4 (with pullup)
 */

// Pin definitions
const int RPWM_PIN = 5;      // Extend actuator (extend = RH)
const int LPWM_PIN = 6;      // Retract actuator (retract = LH)
const int R_EN_PIN = 7;      // Right enable
const int L_EN_PIN = 8;      // Left enable

const int ESTOP_PIN = 4;        // Emergency stop (optional)

const int LED_LH = 10;       // Red LED - Left handed
const int LED_RH = 11;       // Green LED - Right handed  
const int LED_MOVING = 12;   // Yellow LED - Moving

// Movement parameters
const int MOVE_SPEED = 255;           // PWM speed (0-255)

// Movement timing (based on 1.34"/sec and 28" travel = ~21 seconds)
const unsigned long MOVE_TIME_LH_TO_RH = 16000;  // Time to move from LH to RH (ms)
const unsigned long MOVE_TIME_RH_TO_LH = 16000;  // Time to move from RH to LH (ms)
const unsigned long MOVE_BUFFER = 2000;          // Extra time buffer (ms)

// State tracking
enum Position { POS_UNKNOWN, POS_RH, POS_LH, POS_MOVING };
Position currentPosition = POS_LH;  // Start assuming LH position (retracted)
Position targetPosition = POS_UNKNOWN;

unsigned long moveStartTime = 0;
unsigned long moveExpectedTime = 0;
bool isMoving = false;
bool eStopActive = false;

void setup() {
  // Initialize serial communication with larger buffer
  Serial.begin(9600);
  while (!Serial && millis() < 3000) {
    ; // Wait for serial port to connect (timeout after 3 seconds)
  }
  
  // Configure motor driver pins
  pinMode(RPWM_PIN, OUTPUT);
  pinMode(LPWM_PIN, OUTPUT);
  pinMode(R_EN_PIN, OUTPUT);
  pinMode(L_EN_PIN, OUTPUT);
  
  // Configure E-stop pin (optional - with internal pullup)
  pinMode(ESTOP_PIN, INPUT_PULLUP);
  
  // Configure LED pins
  pinMode(LED_LH, OUTPUT);
  pinMode(LED_RH, OUTPUT);
  pinMode(LED_MOVING, OUTPUT);
  
  // Stop motor initially
  stopMotor();
  
  // Set initial LEDs
  updateLEDs();
  
  // Clear any garbage in serial buffer
  while (Serial.available() > 0) {
    Serial.read();
  }
  
  Serial.println("GSPro Actuator Controller Ready");
  Serial.println("Actuator has built-in limit switches");
  Serial.println("Commands: RH, LH, STOP, STATUS, HOME");
  Serial.flush();
  delay(100);
  reportStatus();
}

void loop() {
  // Check emergency stop first
  checkEmergencyStop();
  
  // If moving, check progress
  if (isMoving) {
    checkMovement();
  }
  
  // Update LEDs
  updateLEDs();
  
  // Check for serial commands (non-blocking)
  if (Serial.available() > 0) {
    // Add small delay to ensure complete command is received
    delay(20);
    
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();
    
    // Clear any remaining characters in buffer
    while (Serial.available() > 0) {
      Serial.read();
    }
    
    if (command.length() > 0) {
      // Echo command for debugging
      Serial.print("Received: ");
      Serial.println(command);
      Serial.flush();
      delay(10);
      
      if (command == "RH") {
        moveTo(POS_RH);
      }
      else if (command == "LH") {
        moveTo(POS_LH);
      }
      else if (command == "STOP") {
        stopMotor();
        Serial.println("STOPPED");
        Serial.flush();
        delay(10);
        reportStatus();
      }
      else if (command == "STATUS") {
        reportStatus();
      }
      else if (command == "HOME") {
        // Move to LH position (home/retracted)
        currentPosition = POS_UNKNOWN;
        moveTo(POS_LH);
      }
      else {
        Serial.print("Unknown command: ");
        Serial.println(command);
        Serial.flush();
      }
    }
  }
  
  // Small delay to prevent overwhelming serial
  delay(10);
}

void moveTo(Position target) {
  if (eStopActive) {
    Serial.println("ERROR: E-stop active");
    Serial.flush();
    return;
  }
  
  if (currentPosition == target) {
    Serial.print("Already at ");
    Serial.println(target == POS_RH ? "RH" : "LH");
    Serial.flush();
    return;
  }
  
  targetPosition = target;
  isMoving = true;
  moveStartTime = millis();
  
  // Calculate expected movement time
  if (currentPosition == POS_UNKNOWN) {
    // Don't know where we are, use max time
    moveExpectedTime = max(MOVE_TIME_LH_TO_RH, MOVE_TIME_RH_TO_LH) + MOVE_BUFFER;
  }
  else if (target == POS_RH && currentPosition == POS_LH) {
    moveExpectedTime = MOVE_TIME_LH_TO_RH + MOVE_BUFFER;
  }
  else if (target == POS_LH && currentPosition == POS_RH) {
    moveExpectedTime = MOVE_TIME_RH_TO_LH + MOVE_BUFFER;
  }
  else {
    moveExpectedTime = max(MOVE_TIME_LH_TO_RH, MOVE_TIME_RH_TO_LH) + MOVE_BUFFER;
  }
  
  currentPosition = POS_MOVING;
  
  if (target == POS_RH) {
    // Move to right-handed position (extend actuator)
    Serial.println("Moving to RH position...");
    Serial.print("Expected time: ");
    Serial.print(moveExpectedTime / 1000.0);
    Serial.println(" seconds");
    Serial.flush();  // Ensure messages are sent immediately
    moveRight();
  }
  else if (target == POS_LH) {
    // Move to left-handed position (retract actuator)
    Serial.println("Moving to LH position...");
    Serial.print("Expected time: ");
    Serial.print(moveExpectedTime / 1000.0);
    Serial.println(" seconds");
    Serial.flush();  // Ensure messages are sent immediately
    moveLeft();
  }
}

void moveLeft() {
  // Retract actuator = LH position
  digitalWrite(R_EN_PIN, HIGH);
  digitalWrite(L_EN_PIN, HIGH);
  analogWrite(RPWM_PIN, MOVE_SPEED);  // RPWM for retract
  analogWrite(LPWM_PIN, 0);
}

void moveRight() {
  // Extend actuator = RH position
  digitalWrite(R_EN_PIN, HIGH);
  digitalWrite(L_EN_PIN, HIGH);
  analogWrite(LPWM_PIN, MOVE_SPEED);  // LPWM for extend
  analogWrite(RPWM_PIN, 0);
}

void stopMotor() {
  analogWrite(RPWM_PIN, 0);
  analogWrite(LPWM_PIN, 0);
  digitalWrite(R_EN_PIN, LOW);
  digitalWrite(L_EN_PIN, LOW);
  isMoving = false;
}

void checkMovement() {
  unsigned long elapsed = millis() - moveStartTime;
  
  // Check if expected time has elapsed
  // Actuator's built-in limit switches will stop it automatically
  if (elapsed >= moveExpectedTime) {
    // Movement should be complete
    stopMotor();
    currentPosition = targetPosition;
    
    // Clear serial buffer before sending completion message
    Serial.flush();
    delay(10);
    
    Serial.print("Reached ");
    Serial.print(targetPosition == POS_RH ? "RH" : "LH");
    Serial.println(" position");
    Serial.flush();
    delay(50);  // Give time for message to transmit
    
    reportStatus();
    
    // Clear any stale incoming commands that arrived during movement
    while (Serial.available() > 0) {
      Serial.read();
    }
  }
  
  // Send periodic progress updates every 5 seconds
  static unsigned long lastProgressUpdate = 0;
  if (elapsed >= 5000 && (elapsed - lastProgressUpdate >= 5000)) {
    Serial.flush();  // Flush before sending update
    delay(10);
    
    Serial.print("Moving... ");
    Serial.print(elapsed / 1000);
    Serial.print("s / ");
    Serial.print(moveExpectedTime / 1000);
    Serial.println("s");
    Serial.flush();
    
    lastProgressUpdate = elapsed;
    
    // Small delay to ensure transmission
    delay(50);
  }
}

void checkEmergencyStop() {
  bool estop = (digitalRead(ESTOP_PIN) == LOW);  // NC switch opens when pressed
  
  if (estop && !eStopActive) {
    eStopActive = true;
    stopMotor();
    Serial.println("EMERGENCY STOP ACTIVATED");
  }
  else if (!estop && eStopActive) {
    eStopActive = false;
    Serial.println("Emergency stop released");
  }
}

void updateLEDs() {
  if (eStopActive) {
    // Flash all LEDs if e-stop active
    bool flash = (millis() / 250) % 2;
    digitalWrite(LED_LH, flash);
    digitalWrite(LED_RH, flash);
    digitalWrite(LED_MOVING, flash);
  }
  else if (isMoving) {
    digitalWrite(LED_LH, LOW);
    digitalWrite(LED_RH, LOW);
    digitalWrite(LED_MOVING, HIGH);
  }
  else {
    digitalWrite(LED_MOVING, LOW);
    digitalWrite(LED_LH, currentPosition == POS_LH ? HIGH : LOW);
    digitalWrite(LED_RH, currentPosition == POS_RH ? HIGH : LOW);
  }
}

void reportStatus() {
  Serial.print("STATUS:");
  if (eStopActive) {
    Serial.println("ESTOP");
  }
  else if (isMoving) {
    Serial.print("MOVING_TO_");
    Serial.println(targetPosition == POS_RH ? "RH" : "LH");
  }
  else {
    switch (currentPosition) {
      case POS_RH: Serial.println("RH"); break;
      case POS_LH: Serial.println("LH"); break;
      case POS_UNKNOWN: Serial.println("UNKNOWN"); break;
      default: Serial.println("ERROR"); break;
    }
  }
  Serial.flush();  // Ensure status is sent immediately
}