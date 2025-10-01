# Polaroid Batch Scanner

Interactive scanner for digitizing photo collections with smart file management. Works with any SANE-compatible flatbed scanner.

## Features

- **Interactive calibration** - Drag-and-drop to position scan areas, no manual coordinate math
- **Smart naming** - Automatic cartridge numbering (P#001, F#042) with global sequence tracking
- **Multi-batch workflow** - Scan 4 photos, reload, scan 4 more without restarting
- **Preview modes** - Check positioning before high-res scans
- **Mid-session recalibration** - Adjust positions between batches
- **Multiple formats** - TIFF, PNG, or JPEG output
- **Never overwrites** - Built-in file protection
- **Scanner agnostic** - Works with Canon, Epson, HP, etc.

## Installation

```bash
# Install SANE
brew install sane-backends  # macOS
# or: sudo apt install sane-utils  # Linux

# Verify scanner detected
scanimage -L

# Install Python dependencies
pip install python-sane Pillow matplotlib numpy

# Clone and configure
git clone https://github.com/yourusername/polaroid-batch-scanner.git
cd polaroid-batch-scanner

# Edit output folders
nano cartridge_prefixes.json
```

## Quick Start

**First time:**
```bash
python3 scan_4photos.py
# Choose: 2 (Calibrate)
# Choose: 1 (Polaroid) or 2 (Custom)
# Place photos, press Enter
# Drag rectangles on preview
# Press ENTER to save
```

**Scanning:**
```bash
python3 scan_4photos.py
# Choose: 1 (Start Scanning)
# Enter: P# (auto-suggests next number)
# Place photos, press Enter
# Files save as: P#001_20251002_0001.tiff
```

**Between batches:**
- `y` or Enter - Continue scanning
- `n` - Exit
- `p` - Preview positioning
- `c` - Recalibrate

## Main Features

### Calibration

Two modes available:

**Polaroid Mode:** Fixed-size photos (default 3.5" × 4.25", customizable)
- Drag to place rectangles, size is automatic
- Fast for consistent photo sizes

**Custom Mode:** Any photo size/layout
- Drag to draw rectangles of any dimension
- Supports 1-20 photos per scan

**Controls:**
- Drag mouse - Draw/place rectangle
- Click inside - Select rectangle
- Drag corners/edges - Resize
- D key - Delete
- ENTER - Save

### Smart Naming

Files follow pattern: `{PREFIX}#{CART}_{DATE}_{SEQ}.{ext}`

Example: `P#001_20251002_0001.tiff`
- `P` = Personal (configurable prefix)
- `001` = Cartridge number (global across all folders)
- `20251002` = Scan date
- `0001` = Sequence number (auto-increments)

**Auto-suggestions:**
- Type `P#` → system finds next available number
- Sequence continues: 0001, 0002, 0003...
- Reload scanner → next batch continues sequence

### Settings

Adjust via main menu option 3:
- **Resolution**: 75-4800 DPI
- **Color mode**: Color, Grayscale, 16-bit, Lineart
- **Preview mode**: Off, Full bed, Individual photos
- **Output format**: TIFF, PNG, JPEG

## Configuration

### cartridge_prefixes.json
```json
{
  "P": "~/Pictures/Personal",
  "F": "~/Pictures/Family",
  "G": "~/Pictures/Grandparents"
}
```
Add any prefix letter. System prompts for folder on first use.

### config.json
Stores scanner settings and calibrated positions. Edit manually or use interactive calibration.

## Using Other Scanners

Works with any SANE-compatible scanner:

**1. Check compatibility:**
```bash
scanimage -L
```

**2. Use interactive calibration** - automatically adapts to your scanner bed size and dimensions

**3. Common scanners tested:**
- Canon CanoScan LiDE 400 (216mm × 297mm)
- Epson Perfection series
- HP ScanJet series

**4. Check parameters:**
```bash
scanimage --help | grep -E "(resolution|mode)"
```

Most scanners use standard SANE parameters (`-l`, `-t`, `-x`, `-y`). If yours differs, the script will show an error - just report it.

## Troubleshooting

**Scanner not detected**
```bash
scanimage -L
sane-find-scanner
```
Try different USB port, restart scanner.

**"Access denied" or "Invalid argument"**
Scanner busy from previous operation. System retries 3× automatically. If persistent: unplug/replug scanner.

**Wrong cartridge number suggested**
Ensure all output folders are listed in `cartridge_prefixes.json`. System searches all folders for global max.

**Files already exist**
System skips existing files automatically. Check destination folder, use different cartridge number, or delete conflicts.

**Calibration window won't open**
```bash
# macOS: install tkinter
brew install python-tk

# Linux: install tkinter
sudo apt install python3-tk
```

**Photos misaligned in scans**
Press `p` for preview before scanning, or `c` to recalibrate mid-session.

## File Formats

- **TIFF** (default): Lossless, ~20MB per photo at 1200 DPI
- **PNG**: Lossless, ~10MB per photo at 1200 DPI
- **JPEG**: Lossy, ~2MB per photo at 1200 DPI

## Tips

- Start with 300 DPI for testing, increase to 1200 DPI for archival
- Use preview mode first few times to verify positioning
- Clean scanner glass regularly
- Press photos flat against glass
- Use TIFF for archival, JPEG for sharing
- Cartridge numbers are global - `P#005` and `F#005` can't both exist

---

**Platform:** macOS, Linux
**Requires:** Python 3.7+, SANE backends
**Scanner:** Any SANE-compatible flatbed
