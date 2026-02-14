# GSPro Automatic Stance Adjustment System

An Arduino-based linear actuator controller that automatically adjusts your golf simulator setup between left-handed and right-handed stances based on GSPro player settings.

## Overview

This system monitors GSPro golf simulator software and automatically extends/retracts a linear actuator when you switch between left-handed and right-handed players. Perfect for multi-player sessions or households with mixed handedness.

### Key Features

- ✅ **Automatic detection** - Monitors GSPro player handedness in real-time
- ✅ **Hands-free operation** - Actuator moves automatically when you change players
- ✅ **Built-in safety** - Actuator has internal limit switches (no external switches needed)
- ✅ **Optional e-stop** - Emergency stop button for additional safety
- ✅ **Status LEDs** - Visual feedback for current position and movement
- ✅ **Serial control** - Manual control via serial commands for testing/calibration

---

## Hardware Requirements

### Core Components

| Component | Specification | Purpose |
|-----------|--------------|---------|
| Linear Actuator | 28-30" stroke, 12V, with built-in limit switches | Physical adjustment mechanism |
| Arduino Uno R3 | Microcontroller | System control |
| BTS7960 Motor Driver | 43A H-bridge module | Actuator power control |
| 12V Power Supply | 10A minimum, DC barrel jack | Main power |
| LM2596 Buck Converter | 12V→5V, 3A | Arduino power regulation |
| USB A-to-B Cable | 6-10ft | Arduino-to-PC connection |

### Optional Components

| Component | Purpose |
|-----------|---------|
| Emergency Stop Button | Mushroom-style NC (normally closed), red |
| Red LED + 220Ω resistor | Left-handed position indicator |
| Green LED + 220Ω resistor | Right-handed position indicator |
| Yellow LED + 220Ω resistor | Movement in progress indicator |
| Project Enclosure | 6"×4"×3" minimum (smaller without LEDs/e-stop) |
| Terminal Blocks | Screw-type for clean wiring |
| 10A Inline Fuse | 12V power line protection |

### Wiring & Hardware

- 18AWG wire (red/black) for 12V power
- 22AWG wire for signals
- Wire ferrules and heat shrink tubing
- Cable glands for enclosure penetrations
- Mounting standoffs for Arduino and driver

---

## Software Requirements

### Arduino IDE
- Version 1.8.x or newer
- No additional libraries required (uses standard Arduino functions)

### Python Environment
- Python 3.7 or newer
- `pyserial` library: `pip install pyserial`
- Windows, macOS, or Linux

### GSPro Golf Simulator
- Any version that saves player settings to disk
- Access to GSPro's player configuration files

---

## Installation

### 1. Hardware Assembly

See the complete [GSPro Actuator Wiring Guide](GSPro_Actuator_Wiring_Guide.md) for detailed assembly instructions.

**Quick Summary:**
1. Mount components in enclosure
2. Wire 12V power through buck converter to Arduino VIN
3. Connect BTS7960 motor driver pins to Arduino (pins 5-8)
4. Connect actuator wires to BTS7960 M+ and M-
5. Optional: Add e-stop to pin 4, LEDs to pins 10-12
6. Connect Arduino to PC via USB

### 2. Arduino Code Upload

1. Open `gspro_actuator_controller.ino` in Arduino IDE
2. Select **Tools → Board → Arduino Uno**
3. Select **Tools → Port → [Your Arduino's COM port]**
4. Click **Upload** button (→)
5. Wait for "Done uploading" message

### 3. Python Script Setup

1. Install required library:
   ```bash
   pip install pyserial
   ```

2. Edit `gspro_monitor.py` and configure:
   ```python
   GSPRO_PLAYER_FILE = r"C:\GSPro\Players\CurrentPlayer.json"  # Update path
   ARDUINO_PORT = None  # Auto-detect, or specify like "COM3"
   ```

3. Ensure Python script has read permissions for GSPro files

---

## Configuration

### Arduino Settings

Edit these constants in `gspro_actuator_controller.ino`:

```cpp
// Movement Parameters
const int MOVE_SPEED = 255;              // PWM speed (0-255)
const unsigned long MOVE_TIME_LH_TO_RH = 21000;  // LH→RH time (ms)
const unsigned long MOVE_TIME_RH_TO_LH = 21000;  // RH→LH time (ms)
const unsigned long MOVE_BUFFER = 2000;   // Safety buffer (ms)

// Pin Assignments
const int PIN_RPWM = 5;      // BTS7960 Right PWM
const int PIN_LPWM = 6;      // BTS7960 Left PWM
const int PIN_R_EN = 7;      // BTS7960 Right Enable
const int PIN_L_EN = 8;      // BTS7960 Left Enable
const int PIN_ESTOP = 4;     // Emergency stop (optional)
const int PIN_LED_LH = 10;   // Left-handed LED (optional)
const int PIN_LED_RH = 11;   // Right-handed LED (optional)
const int PIN_LED_MOVE = 12; // Moving LED (optional)
```

### Python Settings

Edit these constants in `gspro_monitor.py`:

```python
# File Monitoring
GSPRO_PLAYER_FILE = r"C:\GSPro\Players\CurrentPlayer.json"
CHECK_INTERVAL = 1.0  # Seconds between file checks

# Serial Communication
ARDUINO_PORT = None   # Auto-detect or specify "COM3", "/dev/ttyUSB0", etc.
BAUD_RATE = 9600
TIMEOUT = 2.0

# Behavior
AUTO_HOME_ON_START = True  # Move to RH position on startup
```

---

## Usage

### Starting the System

1. **Power on** the 12V supply
2. **Verify** Arduino power LED is lit
3. **Run** the Python monitor:
   ```bash
   python gspro_monitor.py
   ```
4. **Check** output for successful Arduino connection
5. **Start** GSPro and select a player

### Automatic Operation

The system automatically monitors GSPro and:
- Detects when you change player handedness
- Extends actuator for left-handed players (LH position)
- Retracts actuator for right-handed players (RH position)
- Provides visual feedback via LEDs (if installed)

### Manual Control (Testing)

Open Arduino Serial Monitor (9600 baud) and send commands:

| Command | Action |
|---------|--------|
| `LH` | Move to left-handed position |
| `RH` | Move to right-handed position |
| `STATUS` | Display current state |
| `STOP` | Emergency stop |

### Emergency Stop

If e-stop button is installed:
1. **Press** red mushroom button
2. **All movement stops immediately**
3. **Release** button to resume normal operation
4. **Re-send** last command if movement was interrupted

---

## Calibration

### Initial Speed Test (IMPORTANT!)

**Before first use:**

1. Set `MOVE_SPEED = 128` in Arduino code (50% speed)
2. Upload code
3. **Clear the actuator's travel path completely**
4. Send `LH` command and observe movement
5. Verify smooth operation and that built-in limit stops extension
6. Send `RH` command and verify retraction

**Once verified:**
1. Restore `MOVE_SPEED = 255` (or your preferred speed)
2. Re-upload code

### Timing Calibration

For accurate timed movements:

1. **Measure actual movement times** with a stopwatch:
   - Send `RH` (if not already there)
   - Send `LH` and time until motion stops: **___ seconds**
   - Send `RH` and time until motion stops: **___ seconds**

2. **Update Arduino code** with measured times (in milliseconds):
   ```cpp
   const unsigned long MOVE_TIME_LH_TO_RH = 21000;  // Your measured time
   const unsigned long MOVE_TIME_RH_TO_LH = 21000;  // Your measured time
   ```

3. **Add safety buffer** (2-3 seconds recommended):
   ```cpp
   const unsigned long MOVE_BUFFER = 2000;  // 2 seconds
   ```

### Direction Correction

If actuator moves in wrong direction:

**Option 1 - Hardware (Recommended):**
- Swap M+ and M- wires at BTS7960 terminals

**Option 2 - Software:**
- In Arduino code, swap logic in `moveLeft()` and `moveRight()` functions

---

## Troubleshooting

### Actuator Doesn't Move

**Check Power:**
- Verify 12V supply is connected and powered on
- Measure voltage at BTS7960 B+ terminal (should read 12V)
- Check buck converter output (should read 5V)

**Check Connections:**
- Verify all BTS7960 pins are connected per wiring guide
- Ensure M+ and M- are connected to actuator
- Check all ground connections are common

**Check Code:**
- Open Serial Monitor - look for "GSPro Actuator Controller Ready"
- Send `STATUS` command - should get position response
- Send `LH` or `RH` - should see "Moving to..." message

### Moves Wrong Direction

- Swap M+ and M- wires on BTS7960 output terminals
- Or modify Arduino code to reverse motor polarity

### Movement Doesn't Stop at Limits

- **This is normal!** Built-in limit switches stop the actuator
- Arduino times out and stops sending power
- If actuator overshoots, verify it has internal limit switches

### Python Can't Find Arduino

**Windows:**
1. Open Device Manager → Ports (COM & LPT)
2. Look for "Arduino Uno (COM#)"
3. Note the COM port number
4. Set `ARDUINO_PORT = "COM3"` (use your port) in Python code

**Mac/Linux:**
1. Run: `ls /dev/tty.*` (Mac) or `ls /dev/ttyUSB*` (Linux)
2. Look for `/dev/tty.usbserial-*` or `/dev/ttyUSB0`
3. Set `ARDUINO_PORT = "/dev/ttyUSB0"` in Python code

**Cable Issues:**
- Use a **data-capable** USB cable (not charge-only)
- Try a different USB port
- Install Arduino drivers if needed

### Python Can't Find GSPro Player File

1. Launch GSPro and select a player
2. Find the actual player file location (varies by GSPro version)
3. Update `GSPRO_PLAYER_FILE` path in Python code
4. Ensure Python has read permissions for that directory

### Erratic Movement or Buzzing

- **Reduce speed:** Lower `MOVE_SPEED` to 200 or 180
- **Add capacitor:** 1000µF across 12V supply terminals
- **Check power supply:** Ensure it can deliver 10A continuously
- **Verify grounds:** All GND connections must be common

### LEDs Not Working

- Check orientation: Long leg (anode) toward resistor, short leg to GND
- Verify 220Ω resistor is installed
- Test LED separately with 5V and resistor
- Check pin assignments match your connections

---

## System Behavior

### Startup Sequence

1. Arduino powers on, initializes pins
2. Built-in limit switches are ready (always active)
3. Python script connects to Arduino
4. If `AUTO_HOME_ON_START = True`, moves to RH position
5. Begins monitoring GSPro player file

### During Operation

- Python checks player file every 1 second (configurable)
- When handedness changes, sends `LH` or `RH` command
- Arduino moves actuator for calculated time
- Built-in limits prevent over-travel
- LEDs show current state (if installed)

### Safety Features

1. **Hardware limit switches** - Always active, factory calibrated
2. **Timed movements** - Arduino stops after expected duration
3. **E-stop button** - Immediate halt (if installed)
4. **Enable pins** - Must be HIGH for any movement
5. **Serial monitoring** - All actions logged for troubleshooting

---

## Advanced Customization

### Adjust Movement Speed

Lower values = quieter, smoother, slower:
```cpp
const int MOVE_SPEED = 200;  // 78% speed
```

Higher values = faster, more powerful:
```cpp
const int MOVE_SPEED = 255;  // Full speed
```

### Acceleration Ramping (Soft Start)

For gentler starts/stops, modify `moveLeft()` and `moveRight()` functions to gradually increase/decrease PWM values over time.

### Add Position Feedback

Install a linear potentiometer on actuator to get real position feedback instead of timed movements.

### WiFi Control

Replace Arduino Uno with ESP32 for wireless operation - no USB cable needed.

---

## Safety Warnings

⚠️ **READ BEFORE OPERATING:**

1. **Clear travel path** - Ensure nothing obstructs actuator before automated use
2. **Built-in limits are primary protection** - Do not rely solely on Arduino timing
3. **Keep hands clear** - Never reach into travel path during automated operation
4. **Test at reduced speed first** - Always verify safe operation at 50% speed initially
5. **Secure all wiring** - Use proper wire gauge, ferrules, and strain relief
6. **Mount enclosure safely** - Ensure it cannot fall or shift during operation
7. **E-stop recommended** - Additional safety layer for peace of mind
8. **Power down for service** - Always disconnect 12V supply when working on system
9. **Supervise initial runs** - Be present for first several automated movements
10. **Label everything** - Clear labels prevent wiring mistakes during maintenance

---

## File Structure

```
gspro-actuator/
├── README.md                              # This file
├── GSPro_Actuator_Wiring_Guide.md        # Complete assembly instructions
├── gspro_actuator_controller.ino         # Arduino firmware
├── gspro_monitor.py                      # Python monitoring script
└── examples/
    ├── manual_control.ino                # Serial command testing
    └── calibration_test.ino              # Movement timing calibration
```

---

## Support & Contributing

### Getting Help

1. Check **Troubleshooting** section above
2. Review **Wiring Guide** for assembly questions
3. Test with Serial Monitor for Arduino issues
4. Verify GSPro file path for Python issues

### Reporting Issues

When reporting problems, include:
- Arduino Serial Monitor output
- Python script console output
- Actuator model and specifications
- Power supply voltage/amperage
- Description of unexpected behavior

### Improvements

Suggested enhancements:
- Current sensing for obstruction detection
- Mobile app control
- Voice command integration ("Alexa, set left-handed")
- Usage logging and statistics
- Predictive maintenance alerts

---

## License

This project is provided as-is for personal use. Modify and adapt as needed for your golf simulator setup.

**Disclaimer:** Use at your own risk. Author assumes no liability for damage or injury resulting from construction or use of this system. Always follow electrical safety practices and ensure proper supervision during automated operation.

---

## Acknowledgments

Built for golf simulator enthusiasts who want automated setup switching without manual adjustments. Perfect for families, teaching pros, or anyone who regularly switches between left and right-handed players.

**Happy golfing! ⛳**
