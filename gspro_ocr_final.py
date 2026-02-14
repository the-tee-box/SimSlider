import time
import mss
import pytesseract
from PIL import Image
from datetime import datetime
import re

class GSProHandednessMonitor:
    def __init__(self, region, output_file='player_handedness.txt', interval=1.0, confirmations=3):
        self.region = region
        self.output_file = output_file
        self.interval = interval
        self.confirmations = confirmations  # Number of consecutive reads needed
        self.current_handedness = None
        self.pending_handedness = None
        self.pending_count = 0
        self.sct = mss.mss()
        self.verbose = False
        
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
            
            if self.verbose:
                print(f"  OCR (whitelist): '{text_clean}'")
            
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
                
                if self.verbose and text_clean:
                    print(f"  OCR ({config}): '{text_clean}'")
                
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
                # WH is likely RH
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
        print("GSPro Handedness Auto Monitor")
        print("=" * 70)
        print(f"Monitoring region: {self.region}")
        print(f"Output file: {self.output_file}")
        print(f"Check interval: {self.interval}s")
        print(f"Confirmations required: {self.confirmations}")
        print("=" * 70)
        print("\nMonitoring for player handedness changes...")
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
                            if self.verbose:
                                print(f"  Confirming {handedness}... ({self.pending_count}/{self.confirmations})")
                            
                            # If we have enough confirmations, accept the change
                            if self.pending_count >= self.confirmations:
                                self.current_handedness = handedness
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                print(f"[{timestamp}] ⭐ CHANGED TO: {handedness}")
                                
                                if self.write_handedness(handedness):
                                    print(f"[{timestamp}] ✓ Written to {self.output_file}")
                                print()
                                
                                # Reset pending
                                self.pending_handedness = None
                                self.pending_count = 0
                        else:
                            # New pending value, start counting
                            self.pending_handedness = handedness
                            self.pending_count = 1
                            if self.verbose:
                                print(f"  Detected {handedness}, waiting for confirmation...")
                    else:
                        # Same as current, reset pending
                        if self.pending_handedness:
                            if self.verbose:
                                print(f"  Back to {self.current_handedness}, reset pending")
                            self.pending_handedness = None
                            self.pending_count = 0
                else:
                    # No handedness detected, don't reset anything
                    pass
                
                if not self.verbose and scan_count % 10 == 0:
                    # Show activity every 10 scans
                    print(".", end="", flush=True)
                
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\n\n" + "=" * 70)
            print("✓ Stopped by user")
            print(f"Total scans: {scan_count}")
            if self.current_handedness:
                print(f"Last detected: {self.current_handedness}")
            print("=" * 70)

def main():
    print("=" * 70)
    print("GSPro Handedness Auto Monitor - Setup")
    print("=" * 70)
    print()
    
    # Default to your working coordinates
    default_region = {
        'left': 1510,
        'top': 1110,
        'width': 50,
        'height': 50
    }
    
    print("Default region (your working coordinates):")
    print(f"  Left: {default_region['left']}")
    print(f"  Top: {default_region['top']}")
    print(f"  Width: {default_region['width']}")
    print(f"  Height: {default_region['height']}")
    print()
    
    use_default = input("Use these coordinates? (y/n, default y): ").strip().lower()
    
    if use_default == 'n':
        print("\nEnter custom coordinates:")
        region = {
            'left': int(input("  Left: ")),
            'top': int(input("  Top: ")),
            'width': int(input("  Width: ")),
            'height': int(input("  Height: "))
        }
    else:
        region = default_region
    
    # Get scan interval
    interval_input = input("\nScan interval in seconds (default 1.0): ").strip()
    try:
        interval = float(interval_input) if interval_input else 1.0
    except:
        interval = 1.0
    
    # Get output file
    output_file = input("Output file (default player_handedness.txt): ").strip()
    if not output_file:
        output_file = 'player_handedness.txt'
    
    # Ask about verbose mode
    verbose = input("\nEnable verbose mode to see OCR output? (y/n, default n): ").strip().lower()
    
    # Ask about confirmations
    confirm_input = input("Number of confirmations required before change (default 3): ").strip()
    try:
        confirmations = int(confirm_input) if confirm_input else 3
    except:
        confirmations = 3
    
    print()
    
    # Create and run monitor
    monitor = GSProHandednessMonitor(region, output_file, interval, confirmations)
    monitor.verbose = (verbose == 'y')
    monitor.run()

if __name__ == "__main__":
    main()