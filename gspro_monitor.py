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
    def __init__(self, region, output_file='player_handedness.txt', interval=1.0, confirmations=3, arduino_port=None):
        self.region = region
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
            # Try whitelist method first (most reliable)
            text = pytesseract.image_to_string(image, config='--psm 6 -c tessedit_char_whitelist=RHLH')
            text_clean = text.strip().upper()
            
            # Direct match
            if text_clean == 'RH' or text_clean == 'LH':
                return text_clean
            
            # Contains RH or LH
            if 'RH' in text_clean:
                return 'RH'
            if 'LH' in text_clean:
                return 'LH'
            
            # Look for R H or L H with space/noise
            if re.search(r'R\s*H', text_clean):
                return 'RH'
            if re.search(r'L\s*H', text_clean):
                return 'LH'
            
            # If whitelist didn't work, try other configs
            configs = [
                '--psm 7',  # Single line
                '--psm 8',  # Single word
                '--psm 10', # Single character
            ]
            
            all_results = []
            for config in configs:
                text = pytesseract.image_to_string(image, config=config)
                text_clean = text.strip().upper()
                all_results.append(text_clean)
                
                # Direct match
                if text_clean == 'RH' or text_clean == 'LH':
                    return text_clean
                
                # Contains RH or LH
                if 'RH' in text_clean:
                    return 'RH'
                if 'LH' in text_clean:
                    return 'LH'
            
            # Fuzzy matching - OCR commonly misreads R as W
            combined = ' '.join(all_results)
            if 'WH' in combined:
                return 'RH'
            
            return None
        except Exception as e:
            print(f"OCR Error: {e}")
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
        print(f"Monitoring region: Left={self.region['left']}, Top={self.region['top']}, "
              f"Width={self.region['width']}, Height={self.region['height']}")
        print(f"Output file: {self.output_file}")
        print(f"Scan interval: {self.interval}s")
        print(f"Confirmations required: {self.confirmations}")
        print("=" * 70)
        print("\nMonitoring started... (minimize this window)")
        print("Press Ctrl+C to stop\n")
        
        scan_count = 0
        
        try:
            while True:
                # Capture and process
                img = self.capture_region()
                handedness = self.extract_handedness(img)
                
                scan_count += 1
                
                # If handedness detected
                if handedness:
                    # If it's different from current
                    if handedness != self.current_handedness:
                        # If it matches pending, increment count
                        if handedness == self.pending_handedness:
                            self.pending_count += 1
                            
                            # If we have enough confirmations, accept the change
                            if self.pending_count >= self.confirmations:
                                self.current_handedness = handedness
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                print(f"[{timestamp}] ⭐ CHANGED TO: {handedness}")
                                
                                # Write to file
                                if self.write_handedness(handedness):
                                    print(f"[{timestamp}] ✓ Written to {self.output_file}")
                                
                                # Send command to Arduino
                                if self.arduino:
                                    print(f"[{timestamp}] → Sending {handedness} to Arduino")
                                    self.send_arduino_command(handedness)
                                
                                # Reset pending
                                self.pending_handedness = None
                                self.pending_count = 0
                        else:
                            # New pending value, start counting
                            self.pending_handedness = handedness
                            self.pending_count = 1
                    else:
                        # Same as current, reset pending
                        if self.pending_handedness:
                            self.pending_handedness = None
                            self.pending_count = 0
                
                if scan_count % 30 == 0:
                    # Show activity every 30 scans
                    print(".", end="", flush=True)
                    
                    # Periodic Arduino connection check (every 30 scans)
                    if self.arduino and scan_count % 300 == 0:  # Every 5 minutes at 1s interval
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
        'left': 1485,  # Shifted left to capture more
        'top': 1085,   # Shifted up to capture more
        'width': 100,  # Doubled from 50
        'height': 100  # Doubled from 50
    }
    output_file = 'player_handedness.txt'
    interval = 0.5  # Faster scanning - check every 0.5 seconds instead of 1
    confirmations = 2  # Reduce confirmations from 3 to 2 for faster response
    
    # Create and run monitor
    monitor = GSProHandednessMonitor(region, output_file, interval, confirmations, arduino_port)
    monitor.run()

if __name__ == "__main__":
    main()