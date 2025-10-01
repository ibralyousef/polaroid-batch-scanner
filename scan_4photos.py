#!/usr/bin/env python3
"""
Canon LiDE400 Multi-Photo Scanner
Scans 4 polaroid photos (3.5" x 4.25") at 1200 DPI and saves as separate TIFF files.
"""

import sane
import json
import os
import sys
import re
import subprocess
import tempfile
import shutil
import time
from pathlib import Path
from datetime import datetime
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Configuration
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
PREFIXES_FILE = SCRIPT_DIR / "cartridge_prefixes.json"
OUTPUT_DIR = SCRIPT_DIR / "output"

# Calibration constants
CALIBRATION_DPI = 75
POLAROID_WIDTH_INCHES = 3.6
POLAROID_HEIGHT_INCHES = 4.35
POLAROID_WIDTH_MM = POLAROID_WIDTH_INCHES * 25.4
POLAROID_HEIGHT_MM = POLAROID_HEIGHT_INCHES * 25.4

# Available scanner settings
AVAILABLE_RESOLUTIONS = [75, 150, 300, 600, 1200, 2400, 4800]
AVAILABLE_COLOR_MODES = {
    "Color": "Color (24-bit RGB)",
    "Gray": "Grayscale (8-bit)",
    "16 bits gray": "16 bits gray (16-bit grayscale)",
    "Lineart": "Black & White (1-bit)"
}
PREVIEW_MODES = {
    "off": "Off (no preview)",
    "scan": "Full Bed Preview (75 DPI with overlays)",
    "guide": "Quick Preview (75 DPI scan of each photo)"
}
AVAILABLE_FORMATS = {
    "tiff": "TIFF (lossless, large files)",
    "png": "PNG (lossless, medium files)",
    "jpeg": "JPEG (lossy, small files)"
}


def load_config():
    """Load scanning configuration from JSON file."""
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def load_prefix_mappings():
    """Load cartridge prefix to folder mappings."""
    if not PREFIXES_FILE.exists():
        # Create default mappings
        default_mappings = {
            "P": "/Users/fermious/Pictures/Personal",
            "F": "/Users/fermious/Pictures/Family"
        }
        save_prefix_mappings(default_mappings)
        return default_mappings

    try:
        with open(PREFIXES_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in prefix file: {e}")
        sys.exit(1)


def save_prefix_mappings(mappings):
    """Save cartridge prefix to folder mappings."""
    with open(PREFIXES_FILE, 'w') as f:
        json.dump(mappings, f, indent=2)


def find_next_cartridge_number(prefix_mappings):
    """Find the next available cartridge number globally across all folders.

    Cartridge numbers are global - the prefix letter just indicates destination.
    This searches ALL folders in prefix_mappings to find the highest number.

    Args:
        prefix_mappings: Dict mapping prefix letters to folder paths

    Returns:
        Tuple of (next_number_str, findings_dict)
        - next_number_str: Next available number as "XXX" (e.g., "007")
        - findings_dict: Dict mapping folder paths to lists of found cartridges
    """
    # Pattern to match any prefix: {LETTER}#{number}_...{extension}
    # Match any supported format: tif, tiff, png, jpg, jpeg
    pattern = re.compile(r'^[A-Z]#(\d{3})_.*\.(tif|tiff|png|jpg|jpeg)$')

    max_number = 0
    findings = {}

    # Search across ALL folders
    for prefix, folder_path in prefix_mappings.items():
        folder = Path(folder_path)
        if not folder.exists():
            continue

        found_in_folder = []

        for filename in folder.iterdir():
            match = pattern.match(filename.name)
            if match:
                cartridge_num = int(match.group(1))
                max_number = max(max_number, cartridge_num)
                # Extract full cartridge name (e.g., "P#001")
                cartridge_name = filename.name.split('_')[0]
                found_in_folder.append(cartridge_name)

        if found_in_folder:
            findings[folder_path] = sorted(set(found_in_folder))

    # Return next number in format XXX (3 digits)
    next_number = max_number + 1
    return f"{next_number:03d}", findings


def get_cartridge_name(prefix_mappings):
    """Prompt user for cartridge name and validate format."""
    print("\n" + "="*60)
    print("CARTRIDGE IDENTIFICATION")
    print("="*60)
    print("Enter cartridge name:")
    print("  Full format: {LETTER}#XXX (e.g., P#001, F#042)")
    print("  Prefix only: {LETTER}# (e.g., P#, F#) - auto-suggests next number")
    print("\nKnown prefixes:")
    for prefix, folder in sorted(prefix_mappings.items()):
        folder_name = Path(folder).name
        print(f"  {prefix}# → {folder_name}")
    print("\nOr press Enter to use generic naming (saves to output/)")
    print("="*60)

    while True:
        cartridge = input("\nCartridge name: ").strip().upper()

        # Allow empty for generic naming
        if not cartridge:
            return None

        # Validate format: {LETTER}#XXX or {LETTER}#
        pattern = r'^[A-Z]#(\d{3})?$'
        match = re.match(pattern, cartridge)

        if match:
            # Check if digits were provided
            if match.group(1):
                # Full format: P#001
                return cartridge
            else:
                # Prefix only: P# - need to suggest next number
                return cartridge  # Return P# to be handled later
        else:
            print("  ✗ Invalid format! Use {LETTER}#XXX or {LETTER}# (e.g., P#001, F#, G#042)")


def determine_destination(cartridge, prefix_mappings):
    """Determine destination folder based on cartridge prefix."""
    if cartridge is None:
        return OUTPUT_DIR, prefix_mappings

    # Extract prefix letter from cartridge (e.g., 'P' from 'P#001')
    prefix = cartridge[0]

    # Check if prefix exists in mappings
    if prefix in prefix_mappings:
        return Path(prefix_mappings[prefix]), prefix_mappings

    # New prefix detected - prompt user for destination
    print("\n" + "="*60)
    print(f"NEW PREFIX DETECTED: '{prefix}'")
    print("="*60)
    print("\nExisting prefix mappings:")
    for p, folder in sorted(prefix_mappings.items()):
        print(f"  {p}#XXX → {folder}")
    print("\n" + "="*60)

    while True:
        print(f"\nEnter destination folder for '{prefix}' cartridges:")
        print("  (or press Enter to cancel)")
        dest_folder = input("Folder path: ").strip()

        if not dest_folder:
            print("\nCancelled. Using generic naming in output/ folder.")
            return OUTPUT_DIR, prefix_mappings

        # Expand ~ to home directory
        dest_path = Path(dest_folder).expanduser()

        # Confirm with user
        print(f"\n'{prefix}' cartridges will save to: {dest_path}")
        confirm = input("Confirm? (Y/n): ").strip().lower()

        if confirm in ['y', '']:
            # Save new mapping
            prefix_mappings[prefix] = str(dest_path)
            save_prefix_mappings(prefix_mappings)
            print(f"✓ Saved! '{prefix}' prefix added to configuration.")
            return dest_path, prefix_mappings

        print("Let's try again...")


def get_next_sequence(cartridge, destination_dir):
    """Find the next sequence number for the cartridge and today's date."""
    if cartridge is None:
        return 1

    # Get today's date in YYYYMMDD format
    today = datetime.now().strftime("%Y%m%d")

    # Pattern to match: {cartridge}_{date}_{sequence}.{extension}
    # Match any supported format: tif, tiff, png, jpg, jpeg
    pattern = re.compile(rf'^{re.escape(cartridge)}_{today}_(\d{{4}})\.(tif|tiff|png|jpg|jpeg)$')

    # Scan destination folder for existing files
    max_sequence = 0
    if destination_dir.exists():
        for filename in destination_dir.iterdir():
            match = pattern.match(filename.name)
            if match:
                sequence = int(match.group(1))
                max_sequence = max(max_sequence, sequence)

    return max_sequence + 1


def initialize_scanner():
    """Initialize SANE and detect Canon LiDE400 scanner."""
    print("Initializing SANE...")
    sane.init()

    devices = sane.get_devices()
    if not devices:
        print("ERROR: No scanners detected!")
        print("Make sure your Canon LiDE400 is connected via USB.")
        print("Try running: scanimage -L")
        sys.exit(1)

    print(f"Found {len(devices)} scanner(s):")
    for dev in devices:
        print(f"  - {dev[0]}: {dev[1]} {dev[2]}")

    # Open the first available scanner with retry logic
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            scanner = sane.open(devices[0][0])
            print(f"\nOpened scanner: {devices[0][1]} {devices[0][2]}")
            return scanner
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Scanner busy or unavailable: {e}")
                print(f"Waiting {retry_delay}s before retry... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"\nERROR: Failed to open scanner after {max_retries} attempts: {e}")
                print("\nTroubleshooting tips:")
                print("  1. Wait a few seconds and try again")
                print("  2. Unplug and replug the scanner USB cable")
                print("  3. Check scanner connection: scanimage -L")
                sys.exit(1)


def configure_scanner(scanner, config, position):
    """Configure scanner settings for a specific position."""
    settings = config['scan_settings']

    # Set resolution
    try:
        scanner.resolution = settings['resolution']
    except:
        print(f"  Warning: Could not set resolution to {settings['resolution']}")

    # Set mode (Color, Gray, Lineart)
    try:
        scanner.mode = settings['mode']
    except:
        print(f"  Warning: Could not set mode to {settings['mode']}")

    # Set scan area geometry (in mm)
    try:
        scanner.tl_x = position['left_mm']  # Top-left X
        scanner.tl_y = position['top_mm']   # Top-left Y
        scanner.br_x = position['left_mm'] + position['width_mm']   # Bottom-right X
        scanner.br_y = position['top_mm'] + position['height_mm']   # Bottom-right Y

        print(f"  Scan area: {position['left_mm']:.1f}mm x {position['top_mm']:.1f}mm "
              f"({position['width_mm']:.1f}mm × {position['height_mm']:.1f}mm)")
    except AttributeError as e:
        print(f"  Warning: Could not set geometry: {e}")
        print("  Your scanner may use different parameter names.")


def scan_photo(scanner, output_file, position_label, output_format='tiff'):
    """Perform a single scan and save to file.

    Args:
        scanner: SANE scanner object
        output_file: Path to save the scanned image
        position_label: Label for progress display
        output_format: Output format ('tiff', 'png', 'jpeg')

    Returns:
        True if scan succeeded, False otherwise
    """
    print(f"\nScanning {position_label}...")

    # Check if file already exists
    if output_file.exists():
        print(f"  ⚠ WARNING: File already exists, skipping: {output_file.name}")
        return False

    try:
        # Start scan
        scanner.start()

        # Get image data
        image = scanner.snap()

        # Save with specified format
        # PIL format names: TIFF, PNG, JPEG
        pil_format = output_format.upper()
        if pil_format == 'JPG':
            pil_format = 'JPEG'

        image.save(output_file, format=pil_format)

        file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
        print(f"  ✓ Saved: {output_file.name} ({file_size:.2f} MB)")

    except Exception as e:
        print(f"  ✗ ERROR: Failed to scan {position_label}: {e}")
        return False

    return True


# ============================================================================
# CALIBRATION FUNCTIONS
# ============================================================================

def pixels_to_mm(pixels, dpi):
    """Convert pixels to millimeters."""
    return (pixels / dpi) * 25.4


def mm_to_pixels(mm, dpi):
    """Convert millimeters to pixels."""
    return (mm * dpi) / 25.4


def take_calibration_scan():
    """Take a quick 75 DPI scan of the entire scanner bed."""
    print("\n" + "="*60)
    print("CALIBRATION SCAN")
    print("="*60)
    print("\nPlace your adapter/photos on the scanner bed.")
    print("Make sure everything is properly positioned.")
    input("\nPress Enter when ready to scan...")

    print("\nScanning at 75 DPI (this will be quick)...")

    with tempfile.NamedTemporaryFile(suffix='.tiff', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Retry logic for scanner access
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            if attempt > 0:
                print(f"  Scanner busy, waiting {retry_delay}s before retry... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)

            try:
                result = subprocess.run([
                    'scanimage',
                    '--format=tiff',
                    '--resolution', str(CALIBRATION_DPI),
                    '--mode', 'Color',
                    '-o', tmp_path
                ], capture_output=True, text=True, timeout=60)

                if result.returncode == 0:
                    # Success!
                    break

                # Check if this was the last attempt
                if attempt == max_retries - 1:
                    print(f"ERROR: Calibration scan failed after {max_retries} attempts")
                    print(f"Scanner error: {result.stderr.strip()}")
                    print("TIP: Wait a few seconds and try again, or unplug/replug the scanner USB cable")
                    return None

            except subprocess.TimeoutExpired:
                if attempt == max_retries - 1:
                    print("ERROR: Calibration scan timed out after multiple attempts")
                    print("TIP: Check scanner connection and try again")
                    return None

        print("✓ Calibration scan complete!")
        img = Image.open(tmp_path)
        return img, CALIBRATION_DPI

    except Exception as e:
        print(f"ERROR: {e}")
        return None


class InteractiveCalibrator:
    """Interactive calibration with custom drag-to-draw rectangles."""

    def __init__(self, img, dpi, mode='polaroid', num_photos=4, photo_width_mm=None, photo_height_mm=None):
        self.img = img
        self.dpi = dpi
        self.mode = mode
        self.num_photos = num_photos
        self.rectangles = []
        self.selected_idx = None

        # Photo dimensions for polaroid mode (defaults to standard Polaroid)
        self.photo_width_mm = photo_width_mm if photo_width_mm is not None else POLAROID_WIDTH_MM
        self.photo_height_mm = photo_height_mm if photo_height_mm is not None else POLAROID_HEIGHT_MM

        # Drawing state
        self.is_drawing = False
        self.is_dragging = False
        self.draw_start = None
        self.preview_rect = None
        self.preview_label = None
        self.drag_offset = None

        # Resize state
        self.is_resizing = False
        self.resize_handle = None  # 'tl', 'tr', 'br', 'bl', 't', 'r', 'b', 'l'
        self.resize_start_rect = None
        self.handle_size = 8  # Handle radius in pixels
        self.handle_patches = []  # Visual handle markers

        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(16, 12))
        self.ax.imshow(img)
        self.update_title()

        # Connect mouse and keyboard events
        self.fig.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.fig.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)

        # Instructions
        self.show_instructions()

    def update_title(self):
        """Update title based on current state."""
        num_placed = len(self.rectangles)
        if self.mode == 'polaroid':
            title = f'Polaroid Calibration: {num_placed}/{self.num_photos} rectangles'
        else:
            title = f'Custom Calibration: {num_placed}/{self.num_photos} rectangles'

        if num_placed < self.num_photos:
            title += ' | Drag to draw rectangle'
        else:
            title += ' | Press ENTER to save'

        if self.selected_idx is not None:
            title += f' | Selected: #{self.selected_idx + 1}'

        self.ax.set_title(title, fontsize=14, fontweight='bold')

    def show_instructions(self):
        """Show instruction text."""
        instructions = [
            "Controls:",
            "• Drag: Draw new rectangle",
            "• Click inside: Select rectangle",
            "• Drag selected: Move rectangle",
            "• D: Delete selected/last rectangle",
            "• ENTER/C: Confirm and save",
            "• ESC: Cancel"
        ]
        y_pos = 0.98
        for inst in instructions:
            self.ax.text(0.02, y_pos, inst, transform=self.fig.transFigure,
                        fontsize=10, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            y_pos -= 0.03

    def point_in_rect(self, x, y, rect_data):
        """Check if point is inside rectangle."""
        left = rect_data['left_px']
        top = rect_data['top_px']
        right = left + rect_data['width_px']
        bottom = top + rect_data['height_px']
        return left <= x <= right and top <= y <= bottom

    def find_clicked_rect(self, x, y):
        """Find which rectangle was clicked."""
        for i, rect_data in enumerate(self.rectangles):
            if self.point_in_rect(x, y, rect_data):
                return i
        return None

    def update_rect_visual(self, idx):
        """Update rectangle visual appearance."""
        rect_data = self.rectangles[idx]
        is_selected = (idx == self.selected_idx)

        # Update color
        color = 'yellow' if is_selected else 'lime'
        rect_data['patch'].set_edgecolor(color)
        rect_data['label'].set_color(color)

    def draw_resize_handles(self, rect_data):
        """Draw 8 resize handles around selected rectangle."""
        # Remove old handles
        for handle in self.handle_patches:
            try:
                handle.remove()
            except (ValueError, AttributeError):
                pass
        self.handle_patches = []

        left = rect_data['left_px']
        top = rect_data['top_px']
        width = rect_data['width_px']
        height = rect_data['height_px']

        # Calculate handle positions (8 handles: 4 corners + 4 edges)
        handles = {
            'tl': (left, top),
            't': (left + width/2, top),
            'tr': (left + width, top),
            'r': (left + width, top + height/2),
            'br': (left + width, top + height),
            'b': (left + width/2, top + height),
            'bl': (left, top + height),
            'l': (left, top + height/2)
        }

        # Draw handles as small circles
        for handle_id, (hx, hy) in handles.items():
            handle = patches.Circle(
                (hx, hy), self.handle_size,
                color='yellow', zorder=10
            )
            self.ax.add_patch(handle)
            self.handle_patches.append(handle)

    def find_handle_at_point(self, x, y, rect_data):
        """Find which resize handle (if any) is at the given point."""
        left = rect_data['left_px']
        top = rect_data['top_px']
        width = rect_data['width_px']
        height = rect_data['height_px']

        # Calculate handle positions
        handles = {
            'tl': (left, top),
            't': (left + width/2, top),
            'tr': (left + width, top),
            'r': (left + width, top + height/2),
            'br': (left + width, top + height),
            'b': (left + width/2, top + height),
            'bl': (left, top + height),
            'l': (left, top + height/2)
        }

        # Check if click is near any handle
        tolerance = self.handle_size * 1.5
        for handle_id, (hx, hy) in handles.items():
            dist = ((x - hx)**2 + (y - hy)**2)**0.5
            if dist <= tolerance:
                return handle_id

        return None

    def on_mouse_press(self, event):
        """Handle mouse press."""
        if event.xdata is None or event.ydata is None:
            return

        if event.inaxes != self.ax:
            return

        x, y = event.xdata, event.ydata

        # Check if clicking on a resize handle (if rectangle is selected)
        if self.selected_idx is not None:
            rect_data = self.rectangles[self.selected_idx]
            handle = self.find_handle_at_point(x, y, rect_data)
            if handle is not None:
                # Start resize
                self.is_resizing = True
                self.resize_handle = handle
                self.resize_start_rect = {
                    'left_px': rect_data['left_px'],
                    'top_px': rect_data['top_px'],
                    'width_px': rect_data['width_px'],
                    'height_px': rect_data['height_px'],
                    'start_x': x,
                    'start_y': y
                }
                return

        # Check if clicking inside existing rectangle
        clicked_idx = self.find_clicked_rect(x, y)

        if clicked_idx is not None:
            # Select rectangle
            old_selected = self.selected_idx
            self.selected_idx = clicked_idx

            # Update visuals
            if old_selected is not None:
                self.update_rect_visual(old_selected)
            self.update_rect_visual(clicked_idx)

            # Draw resize handles
            rect_data = self.rectangles[clicked_idx]
            self.draw_resize_handles(rect_data)

            # Start dragging
            self.is_dragging = True
            self.drag_offset = (x - rect_data['left_px'], y - rect_data['top_px'])

            self.update_title()
            self.fig.canvas.draw()
        else:
            # Start drawing new rectangle
            if len(self.rectangles) < self.num_photos:
                self.is_drawing = True
                self.draw_start = (x, y)

                # Deselect any selected rectangle
                if self.selected_idx is not None:
                    self.update_rect_visual(self.selected_idx)
                    self.selected_idx = None
                    # Remove handles
                    for handle in self.handle_patches:
                        try:
                            handle.remove()
                        except (ValueError, AttributeError):
                            pass
                    self.handle_patches = []
                    self.update_title()

    def on_mouse_move(self, event):
        """Handle mouse move."""
        if event.xdata is None or event.ydata is None:
            return

        if event.inaxes != self.ax:
            return

        x, y = event.xdata, event.ydata

        if self.is_drawing and self.draw_start:
            # Update preview rectangle
            if self.preview_rect:
                try:
                    self.preview_rect.remove()
                except (ValueError, AttributeError):
                    pass
            if self.preview_label:
                try:
                    self.preview_label.remove()
                except (ValueError, AttributeError):
                    pass

            x1, y1 = self.draw_start

            if self.mode == 'polaroid':
                # Fixed size
                width_px = mm_to_pixels(self.photo_width_mm, self.dpi)
                height_px = mm_to_pixels(self.photo_height_mm, self.dpi)
                left_px = x1
                top_px = y1
            else:
                # Custom size
                left_px = min(x1, x)
                top_px = min(y1, y)
                width_px = abs(x - x1)
                height_px = abs(y - y1)

            # Draw preview
            self.preview_rect = patches.Rectangle(
                (left_px, top_px), width_px, height_px,
                linewidth=2, edgecolor='red', facecolor='red', alpha=0.3
            )
            self.ax.add_patch(self.preview_rect)

            width_mm = pixels_to_mm(width_px, self.dpi)
            height_mm = pixels_to_mm(height_px, self.dpi)
            self.preview_label = self.ax.text(
                left_px + width_px/2, top_px + height_px/2,
                f"Preview\n{width_mm:.1f}×{height_mm:.1f}mm",
                color='red', fontsize=12, fontweight='bold',
                ha='center', va='center',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
            )

            self.fig.canvas.draw()

        elif self.is_resizing and self.selected_idx is not None:
            # Resize selected rectangle
            rect_data = self.rectangles[self.selected_idx]
            handle = self.resize_handle
            start = self.resize_start_rect

            # Calculate deltas
            dx = x - start['start_x']
            dy = y - start['start_y']

            # Initialize new dimensions
            new_left = start['left_px']
            new_top = start['top_px']
            new_width = start['width_px']
            new_height = start['height_px']

            # Update dimensions based on handle
            if 'l' in handle or handle == 'l':
                new_left = start['left_px'] + dx
                new_width = start['width_px'] - dx
            if 'r' in handle or handle == 'r':
                new_width = start['width_px'] + dx
            if 't' in handle or handle == 't':
                new_top = start['top_px'] + dy
                new_height = start['height_px'] - dy
            if 'b' in handle or handle == 'b':
                new_height = start['height_px'] + dy

            # For Polaroid mode, maintain aspect ratio when resizing corners
            if self.mode == 'polaroid' and handle in ['tl', 'tr', 'br', 'bl']:
                aspect_ratio = self.photo_width_mm / self.photo_height_mm
                # Use width as primary dimension, adjust height
                new_height = new_width / aspect_ratio

                # Adjust top position for top handles
                if 't' in handle:
                    new_top = start['top_px'] + start['height_px'] - new_height

            # Prevent negative dimensions
            if new_width < 20:
                new_width = 20
                new_left = start['left_px']
            if new_height < 20:
                new_height = 20
                new_top = start['top_px']

            # Update rectangle
            rect_data['patch'].set_x(new_left)
            rect_data['patch'].set_y(new_top)
            rect_data['patch'].set_width(new_width)
            rect_data['patch'].set_height(new_height)

            # Update label position
            rect_data['label'].set_position((new_left + new_width/2, new_top + new_height/2))

            # Update stored dimensions
            rect_data['left_px'] = new_left
            rect_data['top_px'] = new_top
            rect_data['width_px'] = new_width
            rect_data['height_px'] = new_height
            rect_data['left_mm'] = pixels_to_mm(new_left, self.dpi)
            rect_data['top_mm'] = pixels_to_mm(new_top, self.dpi)
            rect_data['width_mm'] = pixels_to_mm(new_width, self.dpi)
            rect_data['height_mm'] = pixels_to_mm(new_height, self.dpi)

            # Redraw handles at new positions
            self.draw_resize_handles(rect_data)

            self.fig.canvas.draw()

        elif self.is_dragging and self.selected_idx is not None:
            # Move selected rectangle
            rect_data = self.rectangles[self.selected_idx]
            dx, dy = self.drag_offset

            new_left = x - dx
            new_top = y - dy

            # Update rectangle position
            rect_data['patch'].set_x(new_left)
            rect_data['patch'].set_y(new_top)

            # Update label position
            width_px = rect_data['width_px']
            height_px = rect_data['height_px']
            rect_data['label'].set_position((new_left + width_px/2, new_top + height_px/2))

            # Update stored position
            rect_data['left_px'] = new_left
            rect_data['top_px'] = new_top
            rect_data['left_mm'] = pixels_to_mm(new_left, self.dpi)
            rect_data['top_mm'] = pixels_to_mm(new_top, self.dpi)

            # Redraw handles at new position
            self.draw_resize_handles(rect_data)

            self.fig.canvas.draw()

    def on_mouse_release(self, event):
        """Handle mouse release."""
        if event.xdata is None or event.ydata is None:
            self.is_drawing = False
            self.is_dragging = False
            self.is_resizing = False
            return

        if event.inaxes != self.ax:
            self.is_drawing = False
            self.is_dragging = False
            self.is_resizing = False
            return

        x, y = event.xdata, event.ydata

        if self.is_drawing and self.draw_start:
            # Finalize rectangle
            if self.preview_rect:
                try:
                    self.preview_rect.remove()
                except (ValueError, AttributeError):
                    pass
                self.preview_rect = None
            if self.preview_label:
                try:
                    self.preview_label.remove()
                except (ValueError, AttributeError):
                    pass
                self.preview_label = None

            x1, y1 = self.draw_start

            if self.mode == 'polaroid':
                width_px = mm_to_pixels(self.photo_width_mm, self.dpi)
                height_px = mm_to_pixels(self.photo_height_mm, self.dpi)
                left_px = x1
                top_px = y1
            else:
                left_px = min(x1, x)
                top_px = min(y1, y)
                width_px = abs(x - x1)
                height_px = abs(y - y1)

            # Don't create tiny rectangles
            if width_px < 10 or height_px < 10:
                self.is_drawing = False
                self.fig.canvas.draw()
                return

            # Convert to mm
            left_mm = pixels_to_mm(left_px, self.dpi)
            top_mm = pixels_to_mm(top_px, self.dpi)
            width_mm = pixels_to_mm(width_px, self.dpi)
            height_mm = pixels_to_mm(height_px, self.dpi)

            # Create final rectangle
            rect = patches.Rectangle(
                (left_px, top_px), width_px, height_px,
                linewidth=3, edgecolor='lime', facecolor='none'
            )
            self.ax.add_patch(rect)

            photo_num = len(self.rectangles) + 1
            label_text = self.ax.text(
                left_px + width_px/2, top_px + height_px/2,
                f"{photo_num}\n{width_mm:.1f}×{height_mm:.1f}mm",
                color='lime', fontsize=14, fontweight='bold',
                ha='center', va='center',
                bbox=dict(boxstyle='round', facecolor='black', alpha=0.7)
            )

            # Store rectangle
            self.rectangles.append({
                'patch': rect,
                'label': label_text,
                'left_px': left_px,
                'top_px': top_px,
                'width_px': width_px,
                'height_px': height_px,
                'left_mm': left_mm,
                'top_mm': top_mm,
                'width_mm': width_mm,
                'height_mm': height_mm
            })

            print(f"✓ Rectangle {photo_num}: {left_mm:.2f}mm × {top_mm:.2f}mm ({width_mm:.1f}×{height_mm:.1f}mm)")

            self.update_title()
            self.fig.canvas.draw()

        self.is_drawing = False
        self.is_dragging = False
        self.is_resizing = False

    def on_key(self, event):
        """Handle keyboard events."""
        if event.key in ['enter', 'c']:
            if len(self.rectangles) == self.num_photos:
                plt.close(self.fig)
            else:
                print(f"Need {self.num_photos} rectangles, have {len(self.rectangles)}")

        elif event.key == 'd':
            # Delete selected or last rectangle
            if self.rectangles:
                if self.selected_idx is not None:
                    idx = self.selected_idx
                    self.selected_idx = None
                else:
                    idx = len(self.rectangles) - 1

                rect_data = self.rectangles.pop(idx)
                rect_data['patch'].remove()
                rect_data['label'].remove()

                # Remove resize handles
                for handle in self.handle_patches:
                    try:
                        handle.remove()
                    except (ValueError, AttributeError):
                        pass
                self.handle_patches = []

                # Renumber remaining rectangles
                for i, rd in enumerate(self.rectangles):
                    rd['label'].set_text(f"{i+1}\n{rd['width_mm']:.1f}×{rd['height_mm']:.1f}mm")

                print(f"Deleted rectangle")
                self.update_title()
                self.fig.canvas.draw()

        elif event.key == 'escape':
            self.rectangles = []
            plt.close(self.fig)

    def get_positions(self):
        """Get calibration positions."""
        if len(self.rectangles) != self.num_photos:
            return None

        positions = []
        for i, rect_data in enumerate(self.rectangles):
            positions.append({
                'id': i + 1,
                'label': f"Photo {i + 1}",
                'left_mm': round(rect_data['left_mm'], 2),
                'top_mm': round(rect_data['top_mm'], 2),
                'width_mm': round(rect_data['width_mm'], 2),
                'height_mm': round(rect_data['height_mm'], 2)
            })

        return positions


def calibrate_polaroid_mode():
    """Polaroid mode: Drag to place 4 fixed-size rectangles."""
    print("\n" + "="*60)
    print("POLAROID CALIBRATION MODE")
    print("="*60)

    # Ask for dimensions
    print(f"\nStandard Polaroid dimensions: 3.5\" × 4.25\"")
    print(f"                             ({POLAROID_WIDTH_MM:.2f}mm × {POLAROID_HEIGHT_MM:.2f}mm)")

    while True:
        use_standard = input("\nUse standard Polaroid dimensions? (Y/n): ").strip().lower()

        if use_standard in ['y', '']:
            # Use standard dimensions
            photo_width_inches = POLAROID_WIDTH_INCHES
            photo_height_inches = POLAROID_HEIGHT_INCHES
            photo_width_mm = POLAROID_WIDTH_MM
            photo_height_mm = POLAROID_HEIGHT_MM
            break
        elif use_standard == 'n':
            # Get custom dimensions
            print("\nEnter custom photo dimensions:")
            try:
                photo_width_inches = float(input("  Width (inches): "))
                photo_height_inches = float(input("  Height (inches): "))

                if photo_width_inches <= 0 or photo_height_inches <= 0:
                    print("  ✗ Dimensions must be positive numbers")
                    continue

                photo_width_mm = photo_width_inches * 25.4
                photo_height_mm = photo_height_inches * 25.4
                break
            except ValueError:
                print("  ✗ Invalid input. Please enter numeric values.")
                continue
        else:
            print("  Please enter 'y' or 'n'")

    print(f"\nPhoto size: {photo_width_inches}\" × {photo_height_inches}\"")
    print(f"           ({photo_width_mm:.2f}mm × {photo_height_mm:.2f}mm)")
    print("\nDrag to place each rectangle (auto-sized to these dimensions)")
    print("="*60)

    scan_result = take_calibration_scan()
    if scan_result is None:
        return None

    img, dpi = scan_result

    print("\n" + "="*60)
    print("INTERACTIVE CALIBRATION")
    print("="*60)
    print("Drag to draw 4 rectangles (one for each photo)")
    print("Controls:")
    print("  • Drag mouse: Place rectangle")
    print("  • D key: Delete last rectangle")
    print("  • ENTER: Confirm and save")
    print("  • ESC: Cancel")
    print("="*60)

    # Create interactive calibrator with custom dimensions
    calibrator = InteractiveCalibrator(img, dpi, mode='polaroid', num_photos=4,
                                      photo_width_mm=photo_width_mm,
                                      photo_height_mm=photo_height_mm)
    plt.show()

    # Get positions
    positions = calibrator.get_positions()
    return positions


def calibrate_custom_mode():
    """Custom mode: Drag to draw custom-sized rectangles."""
    print("\n" + "="*60)
    print("CUSTOM CALIBRATION MODE")
    print("="*60)

    while True:
        try:
            num_photos = int(input("\nHow many photos? (1-20): "))
            if 1 <= num_photos <= 20:
                break
            else:
                print("  Please enter a number between 1 and 20")
        except ValueError:
            print("  Invalid input. Please enter a number.")

    print(f"\nDrag to draw {num_photos} rectangle(s) of any size.")
    print("="*60)

    scan_result = take_calibration_scan()
    if scan_result is None:
        return None

    img, dpi = scan_result

    print("\n" + "="*60)
    print("INTERACTIVE CALIBRATION")
    print("="*60)
    print(f"Drag to draw {num_photos} rectangles")
    print("Controls:")
    print("  • Drag mouse: Draw rectangle")
    print("  • D key: Delete last rectangle")
    print("  • ENTER: Confirm and save")
    print("  • ESC: Cancel")
    print("="*60)

    # Create interactive calibrator
    calibrator = InteractiveCalibrator(img, dpi, mode='custom', num_photos=num_photos)
    plt.show()

    # Get positions
    positions = calibrator.get_positions()
    return positions


def run_calibration():
    """Run calibration workflow."""
    print("\n" + "="*60)
    print("SCANNER CALIBRATION")
    print("="*60)
    print("\nCalibration Mode:")
    print("  1. Polaroid (4 photos, 3.6\"×4.35\") - Mark 1 corner per photo")
    print("  2. Custom (any layout) - Mark 4 corners per photo")
    print()

    while True:
        choice = input("Select mode (1 or 2, or 'b' to go back): ").strip().lower()
        if choice in ['1', '2', 'b']:
            break
        print("  Invalid choice. Please enter 1, 2, or 'b'.")

    if choice == 'b':
        return

    if choice == '1':
        positions = calibrate_polaroid_mode()
    else:
        positions = calibrate_custom_mode()

    if not positions:
        print("\nCalibration failed or cancelled.")
        return

    print("\n" + "="*60)
    print("CALIBRATION SUMMARY")
    print("="*60)
    for pos in positions:
        print(f"{pos['label']}:")
        print(f"  Position: {pos['left_mm']:.2f}mm × {pos['top_mm']:.2f}mm")
        print(f"  Size: {pos['width_mm']:.2f}mm × {pos['height_mm']:.2f}mm")

    print("\n" + "="*60)
    save = input("\nSave this configuration? (Y/n): ").strip().lower()

    if save in ['y', '']:
        try:
            config = load_config()
        except:
            config = {}

        backup_file = CONFIG_FILE.with_suffix('.json.backup')
        if CONFIG_FILE.exists():
            shutil.copy(CONFIG_FILE, backup_file)
            print(f"✓ Backup saved: {backup_file.name}")

        config['positions'] = positions

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"✓ Configuration saved: {CONFIG_FILE}")
        print("\n✓ Calibration complete!")
    else:
        print("\nConfiguration not saved.")


# ============================================================================
# PREVIEW SCAN
# ============================================================================

def show_preview_scan(config, positions):
    """Show a preview of what will be scanned.

    Takes a 75 DPI scan and displays it with rectangles showing
    where each photo will be captured during the actual scan.

    Args:
        config: Configuration dictionary with scan_settings
        positions: List of position dictionaries with scan areas

    Returns:
        True to proceed with scanning, False to cancel
    """
    print("\n" + "="*60)
    print("PREVIEW SCAN")
    print("="*60)
    print("\nTaking quick preview scan at 75 DPI...")
    print("This will show you exactly what will be scanned.")

    # Take preview scan
    with tempfile.NamedTemporaryFile(suffix='.tiff', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Retry logic for scanner access
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            if attempt > 0:
                print(f"  Scanner busy, waiting {retry_delay}s before retry... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)

            try:
                result = subprocess.run([
                    'scanimage',
                    '--format=tiff',
                    '--resolution', str(CALIBRATION_DPI),
                    '--mode', 'Color',
                    '-o', tmp_path
                ], capture_output=True, text=True, timeout=60)

                if result.returncode == 0:
                    # Success!
                    break

                # Check if this was the last attempt
                if attempt == max_retries - 1:
                    print(f"ERROR: Preview scan failed after {max_retries} attempts")
                    print(f"Scanner error: {result.stderr.strip()}")
                    print("TIP: Wait a few seconds and try again, or unplug/replug the scanner USB cable")
                    return True  # Continue anyway

            except subprocess.TimeoutExpired:
                if attempt == max_retries - 1:
                    print("ERROR: Preview scan timed out after multiple attempts")
                    print("TIP: Check scanner connection and try again")
                    return True  # Continue anyway

        print("✓ Preview scan complete!")

        # Load the preview image
        img = Image.open(tmp_path)

        # Create figure
        fig, ax = plt.subplots(figsize=(14, 10))
        ax.imshow(img)
        ax.set_title('PREVIEW - Planned Scan Areas\n(Green rectangles show where photos will be scanned)',
                    fontsize=14, fontweight='bold')
        ax.set_xlabel('X (pixels)')
        ax.set_ylabel('Y (pixels)')

        # Draw rectangles for each position
        for pos in positions:
            # Convert mm to pixels at 75 DPI
            left_px = mm_to_pixels(pos['left_mm'], CALIBRATION_DPI)
            top_px = mm_to_pixels(pos['top_mm'], CALIBRATION_DPI)
            width_px = mm_to_pixels(pos['width_mm'], CALIBRATION_DPI)
            height_px = mm_to_pixels(pos['height_mm'], CALIBRATION_DPI)

            # Draw rectangle
            rect = patches.Rectangle(
                (left_px, top_px), width_px, height_px,
                linewidth=3, edgecolor='lime', facecolor='none'
            )
            ax.add_patch(rect)

            # Add label
            label_text = ax.text(
                left_px + width_px/2, top_px + height_px/2,
                f"{pos['label']}\n{pos['width_mm']:.1f}×{pos['height_mm']:.1f}mm",
                color='lime', fontsize=12, fontweight='bold',
                ha='center', va='center',
                bbox=dict(boxstyle='round', facecolor='black', alpha=0.7)
            )

        plt.tight_layout()
        print("\nPreview window opened.")
        print("Close the window when done reviewing.")
        plt.show()

        # Cleanup temp file
        try:
            os.unlink(tmp_path)
        except:
            pass

        # Ask user if they want to proceed
        print("\n" + "="*60)
        while True:
            response = input("Continue with scanning? (Y/n/r to retake preview): ").strip().lower()
            if response in ['y', '']:
                return True
            elif response == 'n':
                print("Scan cancelled.")
                return False
            elif response == 'r':
                # Retake preview
                return show_preview_scan(config, positions)
            else:
                print("Please enter 'y', 'n', or 'r'")

    except Exception as e:
        print(f"ERROR: Preview failed: {e}")
        return True  # Continue anyway


def show_individual_previews(config, positions):
    """Scan each photo position individually at 75 DPI and display previews.

    Takes quick 75 DPI scans of each photo position separately and displays
    all previews in a grid so user can see actual photo content before
    committing to high-resolution scanning.

    Args:
        config: Configuration dictionary with scan_settings
        positions: List of position dictionaries with scan areas

    Returns:
        True to proceed with scanning, False to cancel
    """
    print("\n" + "="*60)
    print("QUICK PREVIEW SCANS")
    print("="*60)
    print(f"\nScanning {len(positions)} photos at 75 DPI for preview...")

    preview_images = []
    temp_files = []

    try:
        # Scan each position individually
        for i, pos in enumerate(positions, 1):
            print(f"\n  Scanning preview {i}/{len(positions)}: {pos['label']}...")

            # Create temp file for this preview
            with tempfile.NamedTemporaryFile(suffix='.tiff', delete=False) as tmp:
                tmp_path = tmp.name
                temp_files.append(tmp_path)

            # Retry logic for scanner access
            max_retries = 3
            retry_delay = 2

            for attempt in range(max_retries):
                if attempt > 0:
                    print(f"    Scanner busy, waiting {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)

                try:
                    # Scan this specific photo position
                    result = subprocess.run([
                        'scanimage',
                        '--format=tiff',
                        '--resolution', str(CALIBRATION_DPI),
                        '--mode', 'Color',
                        '-l', str(pos['left_mm']),
                        '-t', str(pos['top_mm']),
                        '-x', str(pos['width_mm']),
                        '-y', str(pos['height_mm']),
                        '-o', tmp_path
                    ], capture_output=True, text=True, timeout=60)

                    if result.returncode == 0:
                        # Success!
                        break

                    # Check if this was the last attempt
                    if attempt == max_retries - 1:
                        print(f"    ERROR: Preview scan failed after {max_retries} attempts")
                        print(f"    Scanner error: {result.stderr.strip()}")
                        return True  # Continue anyway

                except subprocess.TimeoutExpired:
                    if attempt == max_retries - 1:
                        print("    ERROR: Preview scan timed out")
                        return True  # Continue anyway

            # Load the preview image
            try:
                img = Image.open(tmp_path)
                preview_images.append((pos['label'], img))
                print(f"    ✓ Preview {i} captured")
            except Exception as e:
                print(f"    ERROR: Could not load preview image: {e}")
                return True  # Continue anyway

        print(f"\n  ✓ All {len(positions)} previews captured!")
        print("\n  Displaying preview images...")

        # Calculate grid layout
        n = len(preview_images)
        if n == 4:
            rows, cols = 2, 2
        elif n == 3:
            rows, cols = 1, 3
        elif n == 2:
            rows, cols = 1, 2
        else:
            rows, cols = 1, 1

        # Create figure with subplots
        fig, axes = plt.subplots(rows, cols, figsize=(14, 10))
        fig.suptitle('PREVIEW - Quick 75 DPI Scans\n(Review photos before high-resolution scanning)',
                    fontsize=14, fontweight='bold')

        # Ensure axes is always a list
        if n == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        # Display each preview
        for idx, (label, img) in enumerate(preview_images):
            axes[idx].imshow(img)
            axes[idx].set_title(f"{label} Preview", fontsize=12, fontweight='bold')
            axes[idx].axis('off')

        # Hide unused subplots
        for idx in range(n, len(axes)):
            axes[idx].axis('off')

        plt.tight_layout()
        print("\n  Preview window opened.")
        print("  Review the photos and close the window when done.")
        plt.show()

        # Ask user if they want to proceed
        print("\n" + "="*60)
        while True:
            response = input("Continue with high-resolution scan? (Y/n/r to rescan previews): ").strip().lower()
            if response in ['y', '']:
                return True
            elif response == 'n':
                print("Scan cancelled.")
                return False
            elif response == 'r':
                # Retake previews
                return show_individual_previews(config, positions)
            else:
                print("Please enter 'y', 'n', or 'r'")

    except Exception as e:
        print(f"ERROR: Preview failed: {e}")
        return True  # Continue anyway

    finally:
        # Cleanup temp files
        for tmp_file in temp_files:
            try:
                os.unlink(tmp_file)
            except:
                pass


# ============================================================================
# SETTINGS ADJUSTMENT
# ============================================================================

def adjust_settings():
    """Adjust scan settings (DPI, color mode)."""
    while True:
        try:
            config = load_config()
        except:
            config = {
                'scan_settings': {
                    'resolution': 1200,
                    'mode': 'Color',
                    'format': 'tiff'
                }
            }

        settings = config.get('scan_settings', {})
        current_resolution = settings.get('resolution', 1200)
        current_mode = settings.get('mode', 'Color')
        current_preview_mode = settings.get('preview_mode', 'off')
        current_format = settings.get('format', 'tiff')

        print("\n" + "="*60)
        print("SCAN SETTINGS")
        print("="*60)
        print("\nCurrent Settings:")
        print(f"  Resolution: {current_resolution} DPI")
        mode_desc = AVAILABLE_COLOR_MODES.get(current_mode, current_mode)
        print(f"  Color Mode: {mode_desc}")
        preview_desc = PREVIEW_MODES.get(current_preview_mode, current_preview_mode)
        print(f"  Preview Mode: {preview_desc}")
        format_desc = AVAILABLE_FORMATS.get(current_format, current_format)
        print(f"  Output Format: {format_desc}")
        print("\nAdjust:")
        print("  1. Resolution")
        print("  2. Color Mode")
        print("  3. Preview Mode")
        print("  4. Output Format")
        print("  5. Back to Main Menu")
        print("="*60)

        choice = input("\nSelect option: ").strip()

        if choice == '1':
            print("\nAvailable Resolutions:")
            for i, res in enumerate(AVAILABLE_RESOLUTIONS, 1):
                current_marker = " ← current" if res == current_resolution else ""
                if res <= 300:
                    quality = "fast preview" if res == 75 else "low quality"
                elif res == 600:
                    quality = "good quality"
                elif res == 1200:
                    quality = "high quality"
                elif res == 2400:
                    quality = "very high quality"
                else:
                    quality = "maximum quality"
                print(f"  {i}. {res} DPI ({quality}){current_marker}")

            try:
                sel = int(input("\nSelect resolution (1-7): "))
                if 1 <= sel <= len(AVAILABLE_RESOLUTIONS):
                    settings['resolution'] = AVAILABLE_RESOLUTIONS[sel - 1]
                    config['scan_settings'] = settings
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump(config, f, indent=2)
                    print(f"✓ Resolution set to {settings['resolution']} DPI")
                else:
                    print("Invalid selection")
            except ValueError:
                print("Invalid input")

        elif choice == '2':
            print("\nAvailable Color Modes:")
            modes = list(AVAILABLE_COLOR_MODES.keys())
            for i, mode in enumerate(modes, 1):
                current_marker = " ← current" if mode == current_mode else ""
                print(f"  {i}. {AVAILABLE_COLOR_MODES[mode]}{current_marker}")

            try:
                sel = int(input(f"\nSelect mode (1-{len(modes)}): "))
                if 1 <= sel <= len(modes):
                    settings['mode'] = modes[sel - 1]
                    config['scan_settings'] = settings
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump(config, f, indent=2)
                    print(f"✓ Color mode set to {AVAILABLE_COLOR_MODES[modes[sel - 1]]}")
                else:
                    print("Invalid selection")
            except ValueError:
                print("Invalid input")

        elif choice == '3':
            # Preview mode selection
            print("\nAvailable Preview Modes:")
            modes = list(PREVIEW_MODES.keys())
            for i, mode in enumerate(modes, 1):
                current_marker = " ← current" if mode == current_preview_mode else ""
                print(f"  {i}. {PREVIEW_MODES[mode]}{current_marker}")

            try:
                sel = int(input(f"\nSelect mode (1-{len(modes)}): "))
                if 1 <= sel <= len(modes):
                    settings['preview_mode'] = modes[sel - 1]
                    config['scan_settings'] = settings
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump(config, f, indent=2)
                    print(f"✓ Preview mode set to {PREVIEW_MODES[modes[sel - 1]]}")
                else:
                    print("Invalid selection")
            except ValueError:
                print("Invalid input")

        elif choice == '4':
            # Output format selection
            print("\nAvailable Output Formats:")
            formats = list(AVAILABLE_FORMATS.keys())
            for i, fmt in enumerate(formats, 1):
                current_marker = " ← current" if fmt == current_format else ""
                print(f"  {i}. {AVAILABLE_FORMATS[fmt]}{current_marker}")

            try:
                sel = int(input(f"\nSelect format (1-{len(formats)}): "))
                if 1 <= sel <= len(formats):
                    settings['format'] = formats[sel - 1]
                    config['scan_settings'] = settings
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump(config, f, indent=2)
                    print(f"✓ Output format set to {AVAILABLE_FORMATS[formats[sel - 1]]}")
                else:
                    print("Invalid selection")
            except ValueError:
                print("Invalid input")

        elif choice == '5':
            break

        else:
            print("Invalid choice")


# ============================================================================
# SCANNING WORKFLOW
# ============================================================================

def run_scanning():
    """Main scanning workflow."""
    print("\n" + "=" * 60)
    print("SCANNING")
    print("=" * 60)

    # Load configuration
    try:
        config = load_config()
        print(f"Loaded configuration from: {CONFIG_FILE}")
    except FileNotFoundError:
        print(f"ERROR: Configuration file not found: {CONFIG_FILE}")
        print("Please run calibration first (Option 2 from main menu)")
        return
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in config file: {e}")
        return

    # Load prefix mappings
    prefix_mappings = load_prefix_mappings()

    # Get cartridge name from user
    cartridge = get_cartridge_name(prefix_mappings)

    # Determine destination folder (may update prefix_mappings if new prefix)
    destination_dir, prefix_mappings = determine_destination(cartridge, prefix_mappings)
    destination_dir.mkdir(exist_ok=True, parents=True)

    # Check if prefix-only format was used (e.g., "P#")
    if cartridge and cartridge.endswith('#'):
        prefix = cartridge[0]
        print("\n" + "="*60)
        print(f"PREFIX-ONLY DETECTED: '{cartridge}'")
        print("="*60)
        print(f"\nScanning ALL folders for existing cartridges (global numbering)...")

        # Find next cartridge number globally
        next_num, findings = find_next_cartridge_number(prefix_mappings)
        suggested_cartridge = f"{prefix}#{next_num}"

        # Display findings from all folders
        if findings:
            print("\nExisting cartridges found:")
            for folder_path, cartridges in findings.items():
                folder_name = Path(folder_path).name
                print(f"  {folder_name}: {', '.join(cartridges)}")
        else:
            print("\nNo existing cartridges found in any folder")

        print(f"\nGlobal next cartridge number: #{next_num}")
        print(f"Suggested cartridge: {suggested_cartridge}")
        print(f"Will save to: {destination_dir}")
        print("="*60)

        while True:
            response = input(f"\nUse {suggested_cartridge} for this session? (Y/n): ").strip().lower()
            if response in ['y', '']:
                cartridge = suggested_cartridge
                print(f"✓ Using cartridge {cartridge}")
                break
            elif response == 'n':
                print("\nPlease enter the full cartridge name:")
                manual_cartridge = input("Cartridge name: ").strip().upper()
                pattern = r'^[A-Z]#\d{3}$'
                if re.match(pattern, manual_cartridge):
                    cartridge = manual_cartridge
                    print(f"✓ Using cartridge {cartridge}")
                    break
                else:
                    print("  ✗ Invalid format! Must be {LETTER}#XXX")
            else:
                print("  Please enter 'y' or 'n'")

    # Get today's date for filename
    today = datetime.now().strftime("%Y%m%d")

    # Get starting sequence number
    current_sequence = get_next_sequence(cartridge, destination_dir)

    # Display naming info
    print(f"\nDestination: {destination_dir}")
    if cartridge:
        print(f"Cartridge: {cartridge}")
        print(f"Date: {today}")
        print(f"Starting sequence: {current_sequence:04d}")
    else:
        print("Using generic naming (photo1.tiff, photo2.tiff, ...)")

    # Get settings and positions for preview
    settings = config['scan_settings']
    positions = config['positions']

    # Show preview BEFORE initializing scanner (if enabled)
    # IMPORTANT: Preview uses subprocess scanimage (75 DPI, Color mode)
    # Main scan uses python-sane with settings below - they are completely isolated
    preview_mode = settings.get('preview_mode', 'off')
    if preview_mode == 'scan':
        if not show_preview_scan(config, positions):
            # User cancelled from preview
            print("Scanning cancelled by user.")
            return
    elif preview_mode == 'guide':
        if not show_individual_previews(config, positions):
            # User cancelled from individual previews
            print("Scanning cancelled by user.")
            return

    # Initialize scanner (AFTER preview is done)
    scanner = initialize_scanner()

    # Display scan settings
    print(f"\nScan settings:")
    print(f"  Resolution: {settings['resolution']} DPI")
    print(f"  Mode: {settings['mode']}")
    print(f"  Format: {settings['format'].upper()}")

    total_scanned = 0
    batch_num = 1

    try:
        while True:
            print("\n" + "=" * 60)
            print(f"BATCH #{batch_num} - Scanning {len(positions)} photos")
            print("=" * 60)
            print("Please ensure photos are properly positioned on the scanner.")
            input("Press Enter when ready to scan...")

            print("-" * 60)

            batch_success = 0
            for i, pos in enumerate(positions):
                # Configure scanner for this position
                configure_scanner(scanner, config, pos)

                # Get file extension from format setting
                output_format = settings.get('format', 'tiff')
                extension = output_format if output_format != 'jpeg' else 'jpg'

                # Generate output filename
                if cartridge:
                    # Use cartridge naming: F#001_20251001_0001.tif
                    seq_num = current_sequence + i
                    filename = f"{cartridge}_{today}_{seq_num:04d}.{extension}"
                else:
                    # Use generic naming
                    filename = f"photo{pos['id']}.{extension}"

                output_file = destination_dir / filename

                # Perform scan
                if scan_photo(scanner, output_file, pos['label'], output_format):
                    batch_success += 1

            total_scanned += batch_success

            # Summary for this batch
            print("-" * 60)
            print(f"Batch complete! {batch_success}/{len(positions)} photos scanned successfully.")

            # Update sequence for next batch
            current_sequence += len(positions)

            # Ask if user wants to continue (with optional preview)
            print("\n" + "=" * 60)
            should_exit = False

            while True:
                response = input("Continue scanning this cartridge? (Y/n/p for preview/c to recalibrate): ").strip().lower()

                if response in ['y', '']:
                    # Continue immediately
                    break
                elif response == 'n':
                    # Exit scanning loop
                    should_exit = True
                    break
                elif response == 'c':
                    # Recalibrate positions
                    print("\nClosing scanner for recalibration...")
                    scanner.close()
                    sane.exit()

                    print("\n" + "="*60)
                    print("RECALIBRATION")
                    print("="*60)
                    print("\nCalibration Mode:")
                    print("  1. Polaroid (4 photos, 3.6\"×4.35\") - Drag to place")
                    print("  2. Custom (any layout) - Drag to draw")
                    print()

                    while True:
                        cal_choice = input("Select mode (1 or 2, or 'b' to cancel): ").strip().lower()
                        if cal_choice in ['1', '2', 'b']:
                            break
                        print("  Invalid choice. Please enter 1, 2, or 'b'.")

                    if cal_choice == 'b':
                        # Cancel recalibration, reinitialize and continue
                        print("\nRecalibration cancelled.")
                        scanner = initialize_scanner()
                        configure_scanner(scanner, config, positions[0])
                        print("✓ Scanner ready")
                        break

                    # Run calibration
                    if cal_choice == '1':
                        new_positions = calibrate_polaroid_mode()
                    else:
                        new_positions = calibrate_custom_mode()

                    if not new_positions:
                        print("\nCalibration failed or cancelled.")
                        scanner = initialize_scanner()
                        configure_scanner(scanner, config, positions[0])
                        print("✓ Scanner ready")
                        break

                    # Show summary and save
                    print("\n" + "="*60)
                    print("CALIBRATION SUMMARY")
                    print("="*60)
                    for pos in new_positions:
                        print(f"{pos['label']}:")
                        print(f"  Position: {pos['left_mm']:.2f}mm × {pos['top_mm']:.2f}mm")
                        print(f"  Size: {pos['width_mm']:.2f}mm × {pos['height_mm']:.2f}mm")

                    print("\n" + "="*60)
                    save_cal = input("\nSave this configuration? (Y/n): ").strip().lower()

                    if save_cal in ['y', '']:
                        backup_file = CONFIG_FILE.with_suffix('.json.backup')
                        if CONFIG_FILE.exists():
                            shutil.copy(CONFIG_FILE, backup_file)
                            print(f"✓ Backup saved: {backup_file.name}")

                        config['positions'] = new_positions
                        with open(CONFIG_FILE, 'w') as f:
                            json.dump(config, f, indent=2)
                        print(f"✓ Configuration saved: {CONFIG_FILE}")

                        # Update positions for current session
                        positions = new_positions
                        print("\n✓ Using new calibration for remaining scans")
                    else:
                        print("\nCalibration not saved. Using previous positions.")

                    # Re-initialize scanner
                    print("\nRe-initializing scanner...")
                    scanner = initialize_scanner()
                    configure_scanner(scanner, config, positions[0])
                    print("✓ Scanner ready")
                    break
                elif response == 'p':
                    # Show preview then continue
                    print("\nClosing scanner temporarily for preview...")
                    scanner.close()
                    sane.exit()

                    # Determine which preview mode to use
                    current_preview_mode = settings.get('preview_mode', 'guide')
                    if current_preview_mode == 'off':
                        # If preview disabled in settings, default to individual previews
                        current_preview_mode = 'guide'

                    print(f"Using preview mode: {PREVIEW_MODES[current_preview_mode]}")

                    # Show preview based on mode
                    if current_preview_mode == 'scan':
                        preview_result = show_preview_scan(config, positions)
                    else:  # guide
                        preview_result = show_individual_previews(config, positions)

                    if not preview_result:
                        # User cancelled from preview
                        print("Scanning cancelled.")
                        should_exit = True
                        break

                    # Re-initialize scanner
                    print("\nRe-initializing scanner...")
                    scanner = initialize_scanner()

                    # Reconfigure for first position (rest will be configured in loop)
                    configure_scanner(scanner, config, positions[0])
                    print("✓ Scanner ready")
                    break
                else:
                    print("  Please enter 'y', 'n', 'p', or 'c'")

            # Check if user wants to exit
            if should_exit:
                break

            batch_num += 1
            print("\nReload scanner with next set of photos...")

    finally:
        # Cleanup
        scanner.close()
        sane.exit()

    # Final summary
    print("\n" + "=" * 60)
    print("SCANNING SESSION COMPLETE")
    print("=" * 60)
    print(f"Total photos scanned: {total_scanned}")
    print(f"Batches completed: {batch_num}")
    print(f"Saved to: {destination_dir.absolute()}")
    print("=" * 60)


# ============================================================================
# MAIN MENU
# ============================================================================

def main():
    """Main menu loop."""
    while True:
        print("\n" + "=" * 60)
        print("Canon LiDE400 Multi-Photo Scanner")
        print("=" * 60)
        print("\nMain Menu:")
        print("  1. Start Scanning")
        print("  2. Calibrate Scanner Positions")
        print("  3. Adjust Scan Settings (DPI, Color Mode)")
        print("  4. Exit")
        print("=" * 60)

        choice = input("\nSelect option: ").strip()

        if choice == '1':
            run_scanning()
        elif choice == '2':
            run_calibration()
        elif choice == '3':
            adjust_settings()
        elif choice == '4':
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid choice. Please enter 1, 2, 3, or 4.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
