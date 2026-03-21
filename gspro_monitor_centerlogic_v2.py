import time
import mss
import pytesseract
from PIL import Image
from datetime import datetime
import re
import sys
import serial
import serial.tools.list_ports
import threading

class GSProHandednessMonitor:
    # Clubs that should center the launch monitor regardless of handedness.
    # Add or remove club names here (case-insensitive, partial match supported).
    CENTER_CLUBS = [
        'putter',
        'wedge',
        'pw',   # Pitching Wedge abbreviation
        'sw',   # Sand Wedge abbreviation
        'lw',   # Lob Wedge abbreviation
        'aw',   # Approach Wedge abbreviation
        'gw',   # Gap Wedge abbreviation
    ]

    def __init__(self, region, club_region=None, output_file='player_handedness.txt',
                 interval=1.0, confirmations=3, arduino_port=None):
        self.region = region
        self.club_region = club_region  # Screen region that shows the current club name
        self.output_file = output_file
        self.interval = interval
        self.confirmations = confirmations
        self.current_handedness = None
        self.pending_handedness = None
        self.pending_count = 0
        self.last_detected = None  # Track last detection regardless of confirmation
        self.failed_reads = 0  # Count consecutive failed reads
        self.sct = mss.mss()
        self.arduino = None
        self.arduino_port = arduino_port

        # Club / center-position state
        self.current_club = None          # Last confirmed club name
        self.center_mode = False          # True when a center club is active
        self.pending_club = None
        self.pending_club_count = 0

        # Set to True to print every raw OCR result for the club region - useful
        # for diagnosing why a club isn't being detected.
        self.club_debug = True

        # Connect to Arduino if port specified
        if arduino_port:
            self.connect_arduino()
    
    def connect_arduino(self):
        """Connect to Arduino via serial"""
        try:
            # Close existing connection if open
            if self.arduino and self.arduino.is_open:
                try:
                    self.arduino.close()
                except:
                    pass
                time.sleep(1)
            
            self.arduino = serial.Serial(self.arduino_port, 9600, timeout=2)
            time.sleep(2.5)  # Longer wait for Arduino to reset
            print(f"✓ Connected to Arduino on {self.arduino_port}")
            
            # Clear any stale data
            self.arduino.reset_input_buffer()
            self.arduino.reset_output_buffer()
            
            # Read initial status (Arduino sends startup messages)
            time.sleep(0.5)
            startup_messages = []
            timeout = time.time() + 3
            while time.time() < timeout and self.arduino.in_waiting:
                try:
                    line = self.arduino.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        startup_messages.append(line)
                        print(f"  Arduino: {line}")
                except:
                    pass
                time.sleep(0.1)
            
            # Verify connection with STATUS command
            time.sleep(0.5)
            self.arduino.write(b"STATUS\n")
            self.arduino.flush()
            time.sleep(0.5)
            
            got_response = False
            timeout = time.time() + 2
            while time.time() < timeout:
                if self.arduino.in_waiting:
                    line = self.arduino.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(f"  Arduino: {line}")
                        if "STATUS:" in line:
                            got_response = True
                            break
                time.sleep(0.1)
            
            if got_response:
                print("  ✓ Connection verified")
                return True
            else:
                print("  ⚠️ Connected but no status response")
                return True  # Continue anyway
            
        except Exception as e:
            print(f"✗ Failed to connect to Arduino: {e}")
            self.arduino = None
            return False
    
    def check_arduino_connection(self):
        """Check if Arduino is still connected and responsive"""
        if not self.arduino:
            return False
        
        try:
            # Check if port is still open
            if not self.arduino.is_open:
                print("  Arduino connection lost, attempting to reconnect...")
                return self.connect_arduino()
            
            # Send a status check
            self.arduino.write(b"STATUS\n")
            time.sleep(0.2)
            
            # Try to read response
            if self.arduino.in_waiting:
                return True
            
            return True  # Assume OK if no error
        except Exception as e:
            print(f"  Arduino connection check failed: {e}")
            print("  Attempting to reconnect...")
            return self.connect_arduino()
    
    def send_arduino_command(self, command):
        """Send command to Arduino with non-blocking timeout and auto-reconnect"""
        if not self.arduino_port:
            return False
        
        max_retries = 3  # Increased from 2
        
        for attempt in range(max_retries):
            try:
                # Check if we need to reconnect
                if not self.arduino or not self.arduino.is_open:
                    print(f"  Connection lost, reconnecting... (attempt {attempt + 1}/{max_retries})")
                    if not self.connect_arduino():
                        if attempt < max_retries - 1:
                            time.sleep(1)
                            continue
                        return False
                
                # Clear buffers before sending
                try:
                    self.arduino.reset_input_buffer()
                    self.arduino.reset_output_buffer()
                except:
                    # If buffer clear fails, connection is probably dead
                    print(f"  Buffer clear failed, reconnecting...")
                    self.arduino = None
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return False
                
                # Send command
                self.arduino.write(f"{command}\n".encode())
                self.arduino.flush()
                print(f"  Command sent: {command}")
                
                # Non-blocking read with timeout
                start_time = time.time()
                timeout = 3.0  # Increased from 2 seconds
                response_lines = []
                got_acknowledgment = False
                
                while time.time() - start_time < timeout:
                    try:
                        # Check if data is available (non-blocking)
                        if self.arduino.in_waiting > 0:
                            line = self.arduino.readline().decode('utf-8', errors='ignore').strip()
                            if line:
                                response_lines.append(line)
                                print(f"  Arduino: {line}")
                                
                                # Check for acknowledgment keywords
                                if any(keyword in line for keyword in ['Received:', 'Moving', 'Already at', 'STATUS:', 'Reached', 'position']):
                                    got_acknowledgment = True
                                    # Give a bit more time for complete response
                                    time.sleep(0.3)
                                    # Read any remaining messages
                                    remaining_timeout = time.time() + 0.5
                                    while time.time() < remaining_timeout and self.arduino.in_waiting:
                                        try:
                                            extra_line = self.arduino.readline().decode('utf-8', errors='ignore').strip()
                                            if extra_line:
                                                print(f"  Arduino: {extra_line}")
                                        except:
                                            break
                                        time.sleep(0.05)
                                    break
                        else:
                            # No data yet, sleep briefly to avoid busy-waiting
                            time.sleep(0.05)
                    except (serial.SerialException, OSError) as read_error:
                        print(f"  Read error: {read_error}")
                        self.arduino = None  # Mark connection as dead
                        break
                    except Exception as read_error:
                        print(f"  Unexpected read error: {read_error}")
                        break
                
                # If we got acknowledgment, success!
                if got_acknowledgment:
                    return True
                
                # No response received
                print(f"  No response within timeout (attempt {attempt + 1}/{max_retries})")
                
                # Test if connection is still alive
                try:
                    self.arduino.write(b"\n")  # Send empty line to test
                    self.arduino.flush()
                except:
                    print(f"  Connection appears dead, marking for reconnect")
                    self.arduino = None
                
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    # Last attempt - force reconnect for next command
                    print(f"  All attempts failed, will reconnect on next command")
                    try:
                        if self.arduino:
                            self.arduino.close()
                    except:
                        pass
                    self.arduino = None
                    return False
                
            except serial.SerialException as e:
                print(f"  Serial error: {e}")
                self.arduino = None  # Mark as disconnected
                if attempt < max_retries - 1:
                    print(f"  Reconnecting... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(1)
                else:
                    print(f"  Failed after {max_retries} attempts - will try again on next command")
                    return False
            except Exception as e:
                print(f"  Unexpected error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    return False
        
        return False
        
    def capture_region(self):
        """Capture the specified screen region"""
        screenshot = self.sct.grab(self.region)
        img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
        return img
    
    def extract_handedness(self, image):
        """Extract handedness from image using OCR"""
        try:
            def check(text):
                t = text.strip().upper()
                if t in ('RH', 'LH'):
                    return t
                if 'RH' in t: return 'RH'
                if 'LH' in t: return 'LH'
                if re.search(r'R\s*H', t): return 'RH'
                if re.search(r'L\s*H', t): return 'LH'
                return None

            # Whitelist method first (most reliable)
            text = pytesseract.image_to_string(image, config='--psm 6 -c tessedit_char_whitelist=RHLH')
            result = check(text)
            if result:
                return result

            # Try other PSM modes
            all_results = []
            for psm in [7, 8, 10]:
                text = pytesseract.image_to_string(image, config=f'--psm {psm}')
                result = check(text)
                if result:
                    return result
                all_results.append(text.strip().upper())

            # Fuzzy matching - OCR commonly misreads R as W
            if 'WH' in ' '.join(all_results):
                return 'RH'

            return None
        except Exception as e:
            print(f"OCR Error: {e}")
            return None
    
    def is_center_club(self, club_name):
        """Return True if this club should trigger center positioning."""
        if not club_name:
            return False
        club_lower = club_name.lower().strip()
        return any(center in club_lower for center in self.CENTER_CLUBS)

    def capture_club_region(self):
        """Capture the club-name screen region."""
        if not self.club_region:
            return None
        screenshot = self.sct.grab(self.club_region)
        img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
        return img

    def preprocess_club_image(self, image):
        """
        Preprocessing for GSPro club name region: bright white text on dark background.
        Strategy: invert so text becomes dark on light, then upscale for tesseract.
        Keeps it simple — the raw capture is already high contrast; we just need to
        flip it so tesseract's dark-text-on-light assumption is satisfied.
        """
        from PIL import ImageOps
        w, h = image.size
        image = image.resize((w * 3, h * 3), Image.LANCZOS)
        image = image.convert('L')
        image = ImageOps.invert(image)  # white text on dark → dark text on white
        return image

    def extract_club(self, image):
        """
        Extract the current club name from the club-region image.
        The GSPro club region has clean white text on a dark background at a
        readable size — PSM 7 (single line) on the inverted image is most reliable.
        Falls back to raw image PSM 7/6 if the inverted pass returns nothing.
        Returns lowercased text, or None.
        """
        if image is None:
            return None
        try:
            candidates = []

            # ── Pass 1: inverted image (dark text on white) ───────────────────
            inv = self.preprocess_club_image(image)
            for psm in [7, 6]:
                text = pytesseract.image_to_string(inv, config=f'--psm {psm}').strip()
                if text:
                    candidates.append(text)
                    if self.club_debug:
                        print(f"    [club OCR psm{psm} inverted] '{text}'")

            # ── Pass 2: raw image fallback ────────────────────────────────────
            # Tesseract can sometimes handle light-on-dark directly
            for psm in [7, 6]:
                text = pytesseract.image_to_string(image, config=f'--psm {psm}').strip()
                if text:
                    candidates.append(text)
                    if self.club_debug:
                        print(f"    [club OCR psm{psm} raw] '{text}'")

            if not candidates:
                return None

            # ── Match against center-club keywords ────────────────────────────
            for candidate in candidates:
                c_clean = re.sub(r'[^a-z\s]', '', candidate.lower()).strip()
                for keyword in self.CENTER_CLUBS:
                    if keyword in c_clean:
                        if self.club_debug:
                            print(f"    [club match] '{c_clean}' → keyword '{keyword}'")
                        return c_clean

            # No center match — return the longest clean result for state tracking
            best = max(candidates, key=lambda t: len(re.sub(r'[^a-zA-Z\s]', '', t)))
            return re.sub(r'[^a-z\s]', '', best.lower()).strip() or None

        except Exception as e:
            print(f"Club OCR Error: {e}")
            return None

    def write_handedness(self, handedness):
        """Write handedness to file with timestamp"""
        try:
            with open(self.output_file, 'w') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"{handedness}\n")
                f.write(f"Updated: {timestamp}\n")
            return True
        except Exception as e:
            print(f"File write error: {e}")
            return False
    
    def run(self):
        """Main monitoring loop"""
        print("=" * 70)
        print("GSPro Handedness Monitor")
        print("=" * 70)
        print(f"Handedness region: Left={self.region['left']}, Top={self.region['top']}, "
              f"Width={self.region['width']}, Height={self.region['height']}")
        if self.club_region:
            print(f"Club region:       Left={self.club_region['left']}, Top={self.club_region['top']}, "
                  f"Width={self.club_region['width']}, Height={self.club_region['height']}")
            print(f"Center clubs:      {', '.join(self.CENTER_CLUBS)}")
            print(f"Club OCR debug:    {'ON  ← raw OCR output will print below' if self.club_debug else 'OFF (set self.club_debug=True to enable)'}")
        else:
            print("Club region:       Not configured (center-mode disabled)")
        print(f"Output file: {self.output_file}")
        print(f"Scan interval: {self.interval}s")
        print(f"Confirmations required: {self.confirmations}")
        print("=" * 70)
        print("\nMonitoring started... (minimize this window)")
        print("Press Ctrl+C to stop\n")
        
        scan_count = 0
        
        try:
            while True:
                scan_count += 1
                timestamp = datetime.now().strftime('%H:%M:%S')

                # ── Club detection (runs only when club_region is configured) ──────
                if self.club_region:
                    club_img = self.capture_club_region()
                    detected_club = self.extract_club(club_img)

                    # Only print debug line when the raw reading changes
                    if self.club_debug and detected_club != getattr(self, '_last_debug_club', '__unset__'):
                        print(f"[{timestamp}] [club raw] '{detected_club}'  center={self.is_center_club(detected_club)}")
                        self._last_debug_club = detected_club

                    if detected_club == self.pending_club:
                        self.pending_club_count += 1
                    else:
                        self.pending_club = detected_club
                        self.pending_club_count = 1

                    if self.pending_club_count >= self.confirmations:
                        confirmed_club = self.pending_club
                        wants_center = self.is_center_club(confirmed_club)

                        if wants_center and not self.center_mode:
                            # Transition INTO center mode
                            self.center_mode = True
                            self.current_club = confirmed_club
                            print(f"[{timestamp}] 🎯 CENTER CLUB detected: {confirmed_club} → centering actuator")
                            if self.arduino:
                                print(f"[{timestamp}] → Sending CENTER to Arduino")
                                self.send_arduino_command("CENTER")

                        elif not wants_center and self.center_mode:
                            # Transition OUT of center mode — restore handedness position
                            self.center_mode = False
                            self.current_club = confirmed_club
                            print(f"[{timestamp}] 🏌️ Normal club: {confirmed_club} → restoring {self.current_handedness} position")
                            if self.arduino and self.current_handedness:
                                print(f"[{timestamp}] → Sending {self.current_handedness} to Arduino")
                                self.send_arduino_command(self.current_handedness)

                        elif confirmed_club != self.current_club:
                            self.current_club = confirmed_club

                # ── Handedness detection ─────────────────────────────────────────
                img = self.capture_region()
                handedness = self.extract_handedness(img)

                if handedness:
                    if handedness != self.current_handedness:
                        if handedness == self.pending_handedness:
                            self.pending_count += 1

                            if self.pending_count >= self.confirmations:
                                self.current_handedness = handedness
                                print(f"[{timestamp}] ⭐ CHANGED TO: {handedness}")

                                # Write to file
                                if self.write_handedness(handedness):
                                    print(f"[{timestamp}] ✓ Written to {self.output_file}")

                                # Only move actuator if NOT in center mode
                                if self.arduino:
                                    if self.center_mode:
                                        print(f"[{timestamp}] ℹ️  Center mode active — actuator stays centered (handedness recorded as {handedness})")
                                    else:
                                        print(f"[{timestamp}] → Sending {handedness} to Arduino")
                                        self.send_arduino_command(handedness)

                                self.pending_handedness = None
                                self.pending_count = 0
                        else:
                            self.pending_handedness = handedness
                            self.pending_count = 1
                    else:
                        if self.pending_handedness:
                            self.pending_handedness = None
                            self.pending_count = 0

                # ── Periodic heartbeat ───────────────────────────────────────────
                if scan_count % 30 == 0:
                    print(".", end="", flush=True)
                    if self.arduino and scan_count % 300 == 0:
                        if not self.check_arduino_connection():
                            print("\n  ⚠️ Arduino connection issue detected")

                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\n\n" + "=" * 70)
            print("✓ Stopped by user")
            print(f"Total scans: {scan_count}")
            if self.current_handedness:
                print(f"Last detected: {self.current_handedness}")
            print("=" * 70)

def find_arduino_port():
    """Auto-detect Arduino port"""
    ports = list(serial.tools.list_ports.comports())
    arduino_ports = []
    
    for port in ports:
        # Look for Arduino in the description
        if 'arduino' in port.description.lower() or 'ch340' in port.description.lower() or 'usb' in port.description.lower():
            arduino_ports.append(port.device)
    
    return arduino_ports

def main():
    print("=" * 70)
    print("GSPro Handedness Monitor with Arduino Control")
    print("=" * 70)
    print()
    
    # Detect Arduino
    print("Searching for Arduino...")
    arduino_ports = find_arduino_port()
    
    if arduino_ports:
        print(f"Found {len(arduino_ports)} potential Arduino port(s):")
        for port in arduino_ports:
            print(f"  - {port}")
        arduino_port = arduino_ports[0]  # Use first one
        print(f"\nUsing: {arduino_port}")
    else:
        print("No Arduino detected.")
        print("The monitor will still work but won't control the actuator.")
        arduino_port = None
    
    print()
    
    # Hardcoded settings - INCREASED REGION SIZE for better OCR
    region = {
        'left': 1478,  # Shifted left to capture more
        'top': 1123,   # Shifted up to capture more
        'width': 100,  # Doubled from 50
        'height': 45  # Doubled from 50
    }

    # ── Club name region ──────────────────────────────────────────────────────
    # Set this to the screen area that shows the current club name in GSPro.
    # Use a screenshot tool (e.g. Snipping Tool or mss) to find the exact
    # coordinates, then update left/top/width/height below.
    # Set to None to disable center-mode entirely.
    club_region = {
        'left': 1478,   # TODO: update to match your GSPro layout
        'top':  1055,   # TODO: update to match your GSPro layout
        'width': 100,
        'height': 45,
    }
    # ─────────────────────────────────────────────────────────────────────────

    output_file = 'player_handedness.txt'
    interval = 1  # Faster scanning - check every 0.5 seconds instead of 1
    confirmations = 3  # Reduce confirmations from 3 to 2 for faster response
    
    # Create and run monitor
    monitor = GSProHandednessMonitor(region, club_region, output_file, interval, confirmations, arduino_port)
    monitor.run()

if __name__ == "__main__":
    main()