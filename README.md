# Polaroid Batch Scanner

Interactive multi-photo scanner with smart cartridge management for digitizing photo collections. Originally designed for Canon LiDE400, adaptable to any SANE-compatible scanner.

## Features

- **Interactive Visual Calibration**: Drag-and-drop interface for precise photo positioning with live preview
- **Smart Cartridge Naming**: Automatic global numbering system with customizable prefixes (e.g., P#001, F#042)
- **Multi-Batch Scanning**: Scan multiple sets of photos in sequence without restarting
- **Multiple Preview Modes**: Full bed preview or individual photo preview before high-resolution scanning
- **Flexible Output Formats**: TIFF, PNG, or JPEG with configurable resolution (75-4800 DPI)
- **Mid-Session Recalibration**: Adjust photo positions between batches without exiting
- **Multiple Photo Layouts**: Support for Polaroid (fixed size) or custom dimensions
- **File Protection**: Never overwrites existing files
- **Scanner-Agnostic**: Works with any SANE-compatible flatbed scanner

## Requirements

### Hardware
- SANE-compatible flatbed scanner (Canon LiDE400, Epson Perfection, HP ScanJet, etc.)
- USB connection
- Photos to scan

### Software
- **macOS/Linux** (tested on macOS)
- **Python 3.7+**
- **SANE backends** (`brew install sane-backends` on macOS, `apt install sane-utils` on Linux)
- **Python dependencies**:
  - `python-sane` - Scanner control
  - `Pillow` - Image processing
  - `matplotlib` - Interactive calibration interface
  - `numpy` - Image data handling

## Installation

### 1. Install SANE Backends

**macOS:**
```bash
brew install sane-backends
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install sane-utils libsane
```

### 2. Verify Scanner Detection

Connect your scanner via USB and run:
```bash
scanimage -L
```

Expected output:
```
device `pixma:04A91912' is a CANON CanoScan LiDE 400
```

### 3. Install Python Dependencies

```bash
pip install python-sane Pillow matplotlib numpy
```

Or using a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install python-sane Pillow matplotlib numpy
```

### 4. Clone Repository

```bash
git clone https://github.com/yourusername/polaroid-batch-scanner.git
cd polaroid-batch-scanner
```

### 5. Configure Destinations

Edit `cartridge_prefixes.json` to set your output folders:
```json
{
  "P": "~/Pictures/Personal",
  "F": "~/Pictures/Family"
}
```

## Quick Start

### First-Time Setup

1. **Run the scanner**:
   ```bash
   python3 scan_4photos.py
   ```

2. **Select "Calibrate Scanner Positions" (option 2)**

3. **Choose calibration mode**:
   - **Polaroid mode**: For standard 3.5" × 4.25" photos (or custom dimensions)
   - **Custom mode**: For any photo size/layout

4. **Place photos on scanner and press Enter**

5. **Drag rectangles** on the preview image to mark photo positions

6. **Press ENTER** to save calibration

### Scanning Photos

1. **Run scanner and select "Start Scanning" (option 1)**

2. **Enter cartridge name** (e.g., `P#` for auto-suggestion or `P#042` for specific)

3. **Place photos on scanner** according to calibration

4. **Press Enter** to scan - photos save automatically

5. **Continue or exit** when batch completes

## Main Features

### 1. Interactive Calibration

**Two Modes:**

**Polaroid Mode (Fixed Size):**
- Prompts for photo dimensions (default: 3.5" × 4.25")
- Drag to place rectangles - size is automatic
- Fast positioning for consistent photo sizes

**Custom Mode (Any Size):**
- Specify number of photos (1-20)
- Drag to draw rectangles of any size
- Perfect for mixed layouts or non-standard photos

**Controls:**
- **Drag mouse**: Draw or place rectangle
- **Click inside**: Select rectangle
- **Drag selected**: Move rectangle
- **Drag corners/edges**: Resize rectangle
- **D key**: Delete selected or last rectangle
- **ENTER**: Save configuration
- **ESC**: Cancel

### 2. Smart Cartridge Naming

**Format:** `{PREFIX}#{NUMBER}_{DATE}_{SEQUENCE}.{ext}`

**Examples:**
- `P#001_20251002_0001.tif` - Personal cartridge 1, first photo
- `F#042_20251002_0012.jpg` - Family cartridge 42, twelfth photo

**Features:**
- **Global Numbering**: Cartridge numbers increment globally across all folders
- **Prefix-only Input**: Type `P#` → system suggests next available (`P#010`)
- **Auto-sequence**: Photos in same cartridge/date auto-increment (0001, 0002, 0003...)
- **Multi-batch**: Scan 4 photos, reload, scan 4 more with same cartridge
- **Extensible Prefixes**: Add any letter prefix (G, W, T, etc.)

### 3. Preview Modes

**Three Options:**

**Off**: No preview, direct to scanning
**Full Bed Preview**: 75 DPI scan of entire scanner bed with overlays showing exact scan areas
**Individual Preview**: Separate 75 DPI scan of each photo position for content verification

Change in settings menu (option 3) or press 'p' during multi-batch scanning.

### 4. Mid-Session Recalibration

After completing a batch:
- Press **'c'** to recalibrate
- Adjust photo positions
- Continue scanning with new positions
- Useful for different photo sizes in same session

### 5. Settings Management

**Adjust without editing JSON:**
- **Resolution**: 75, 150, 300, 600, 1200, 2400, 4800 DPI
- **Color Mode**: Color (24-bit), Grayscale (8-bit), 16-bit grayscale, Lineart
- **Preview Mode**: Off, Full Bed, Individual
- **Output Format**: TIFF, PNG, JPEG

Access via main menu option 3.

## Configuration Files

### config.json

Stores scanner settings and photo positions:

```json
{
  "scanner_bed": {
    "width_mm": 215.9,
    "height_mm": 297.0
  },
  "scan_settings": {
    "resolution": 1200,
    "mode": "Color",
    "format": "tiff",
    "preview_mode": "guide"
  },
  "positions": [
    {
      "id": 1,
      "label": "Photo 1",
      "left_mm": 14.65,
      "top_mm": 17.51,
      "width_mm": 91.44,
      "height_mm": 110.49
    }
    // ... more positions
  ]
}
```

### cartridge_prefixes.json

Maps prefix letters to output folders:

```json
{
  "P": "~/Pictures/Personal",
  "F": "~/Pictures/Family",
  "G": "~/Pictures/Grandparents"
}
```

Add new prefixes as needed. System will prompt for destination folder when encountering unknown prefix.

## Adapting to Other Scanners

This software works with any SANE-compatible flatbed scanner. Here's how to adapt it:

### 1. Check Scanner Compatibility

```bash
scanimage -L
```

If your scanner appears in the list, it's compatible.

**Tested scanners:**
- Canon CanoScan LiDE 400
- Epson Perfection series
- HP ScanJet series

### 2. Use Interactive Calibration

The **interactive calibration** system automatically adapts to any scanner:
- Takes a 75 DPI preview of your scanner bed
- You visually mark where your photos are
- System calculates correct coordinates automatically
- No manual coordinate calculations needed

### 3. Scanner Bed Dimensions

Different scanners have different bed sizes:
- **Canon LiDE400**: 216mm × 297mm (A4)
- **Epson Perfection V600**: 216mm × 297mm (A4)
- **HP ScanJet Pro**: 216mm × 356mm (Legal)

Update `scanner_bed` in `config.json` if needed, or let calibration detect it automatically.

### 4. SANE Backend Differences

Some scanners use different parameter names:
- Canon LiDE uses: `-l`, `-t`, `-x`, `-y` (left, top, width, height)
- Some scanners use: `--tl-x`, `--tl-y`, `--br-x`, `--br-y` (top-left, bottom-right)

Check your scanner's parameters:
```bash
scanimage --help
```

The script uses the standard `-l`, `-t`, `-x`, `-y` format supported by most SANE backends.

### 5. Resolution Support

Check supported resolutions:
```bash
scanimage --help | grep resolution
```

Update `AVAILABLE_RESOLUTIONS` in the script if your scanner supports different values.

### 6. Testing New Scanners

1. Run calibration mode
2. Place 1-2 test photos
3. Mark positions visually
4. Run a test scan at low resolution (300 DPI)
5. Verify positioning
6. Adjust if needed and save

## Troubleshooting

### Scanner Not Detected

**Error:** `ERROR: No scanners detected!`

**Solutions:**
1. Check USB connection
2. Try different USB port (USB 2.0 may work better than 3.0)
3. Restart scanner (unplug/replug)
4. Check SANE configuration:
   ```bash
   sane-find-scanner
   scanimage -L
   ```

### Scanner Access Denied

**Error:** `Failed to open scanner: Invalid argument` or `Access to resource has been denied`

**Cause:** Scanner busy from previous operation

**Solution:** System automatically retries 3 times with 2-second delays. If persistent:
- Wait 10 seconds and try again
- Close other scanning software
- Unplug and replug scanner

### Wrong Cartridge Number

**Issue:** System suggests wrong next cartridge number

**Solution:** Ensure `cartridge_prefixes.json` includes ALL folders with scanned photos. System searches all listed folders to find global maximum.

### Files Not Saving

**Error:** `File already exists` warning

**Cause:** File protection prevents overwrites

**Solution:**
- System skips existing files automatically
- Check destination folder for conflicts
- Use different cartridge number or delete existing files

### Calibration Window Not Responding

**Issue:** Can't interact with calibration window

**Solutions:**
- Ensure matplotlib backend supports interactive windows
- Try clicking directly on image area
- Check virtual environment has correct matplotlib version
- On macOS, may need to install: `brew install python-tk`

### Photos Not Aligned Correctly

**Issue:** Scans don't capture photos properly

**Solutions:**
1. Re-run calibration mode
2. Use preview mode to verify positioning
3. Ensure photos are flat against scanner glass
4. Check that scanner glass is clean

## Technical Details

### Architecture

**Core Components:**
- `InteractiveCalibrator`: Custom drag-and-drop interface using matplotlib
- `initialize_scanner()`: SANE initialization with retry logic
- `scan_photo()`: High-resolution scanning with geometry parameters
- `get_next_sequence()`: Smart filename generation with collision detection

**Coordinate System:**
- All positions stored in millimeters
- Converted to pixels at scan time based on DPI
- SANE uses millimeter coordinates: `-l` (left), `-t` (top), `-x` (width), `-y` (height)

### File Formats

**TIFF (default):**
- Lossless compression
- Large files (~20MB at 1200 DPI per photo)
- Industry standard for archival

**PNG:**
- Lossless compression
- Medium files (~10MB at 1200 DPI per photo)
- Good for sharing

**JPEG:**
- Lossy compression
- Small files (~2MB at 1200 DPI per photo)
- Best for web/email

### Naming Scheme

**Pattern:** `{PREFIX}#{CART}_{YYYYMMDD}_{SEQNO}.{ext}`
- `PREFIX`: Single letter (P, F, etc.)
- `CART`: 3-digit cartridge number (001-999)
- `YYYYMMDD`: Scan date
- `SEQNO`: 4-digit sequence (0001-9999)
- `ext`: File extension (tif, png, jpg)

**Global Numbering:**
- Cartridge numbers are global across all prefixes
- If P folder has P#001-010 and F folder has F#011-020, next is #021 for any prefix
- Sequence numbers reset per cartridge/date combination

### Preview System

**Isolation:**
- Preview uses `subprocess` + `scanimage` CLI
- Main scanning uses `python-sane` library
- Completely isolated to prevent device conflicts
- Preview at 75 DPI (fast), main scan at user-selected DPI

### File Size Reference

At 1200 DPI, Color mode, per photo:
- **TIFF**: ~18-22 MB
- **PNG**: ~8-12 MB
- **JPEG**: ~1-3 MB

Scanning time per photo:
- **300 DPI**: ~10 seconds
- **600 DPI**: ~20 seconds
- **1200 DPI**: ~30-40 seconds
- **2400 DPI**: ~120 seconds

## Workflow Examples

### Example 1: New Photo Collection

```bash
# First time setup
python3 scan_4photos.py
# Choose: 2 (Calibrate)
# Choose: 1 (Polaroid)
# Press Enter for standard 3.5" × 4.25" dimensions
# Place adapter on scanner
# Drag to mark 4 rectangles
# Press ENTER to save

# Start scanning
# Choose: 1 (Start Scanning)
# Enter: P#
# System suggests: P#001
# Press Enter (default yes)
# Place 4 photos, press Enter
# Scans 4 photos as P#001_20251002_0001.tif through P#001_20251002_0004.tif

# Continue with same cartridge
# Response: y (or just press Enter)
# Reload scanner with 4 more photos
# Scans as P#001_20251002_0005.tif through P#001_20251002_0008.tif

# Finish
# Response: n
```

### Example 2: Multiple Cartridges, Different Sizes

```bash
# Scan first cartridge (Polaroids)
python3 scan_4photos.py
# Scan P#015 (4 photos)

# Response: c (recalibrate)
# Choose custom dimensions: 4" × 6"
# Adjust rectangles
# Save calibration

# Continue scanning with new positions
# Enter: F#023
# Scan F#023 photos with new layout
```

### Example 3: Preview Before Scanning

```bash
# Enable preview in settings
python3 scan_4photos.py
# Choose: 3 (Settings)
# Choose: 3 (Preview Mode)
# Select: 2 (Individual Preview)

# Start scanning
# Choose: 1 (Start Scanning)
# System shows 75 DPI preview of each photo
# Review in window
# Response: y (continue) or n (cancel)
```

## Contributing

Contributions welcome! Areas for improvement:
- Support for additional SANE backends
- Automatic photo rotation/cropping
- OCR integration for photo backs
- Web interface
- Batch cartridge queuing

## License

MIT License - See LICENSE file for details

## Acknowledgments

- **SANE Project**: Scanner access infrastructure
- **Python-SANE**: Python bindings for SANE
- **Pillow**: Image processing
- **Matplotlib**: Interactive calibration interface

## Support

**For scanner-specific issues:**
- Check SANE documentation: http://www.sane-project.org/
- Verify scanner compatibility: `scanimage -L`
- Review scanner manual

**For software issues:**
- Check error messages carefully
- Review `config.json` syntax
- Ensure all dependencies installed
- Try calibration mode to reset positions

## Version History

**1.0.0** (2025-10-02)
- Initial release
- Interactive visual calibration
- Smart cartridge management
- Multi-batch scanning
- Preview modes
- Mid-session recalibration
- Multiple output formats
- Scanner retry logic

---

**Platform**: macOS, Linux
**Scanner**: SANE-compatible flatbed scanners
**Language**: Python 3.7+
**Status**: Production Ready
