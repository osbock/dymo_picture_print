# Dymo Picture Print

Python script to dither and print photos on a Dymo LabelWriter. Supports multiple label sizes, advanced dithering algorithms, and image enhancement options for optimal thermal printing results.

## Features

- **Multiple Label Sizes**: Support for 6 common Dymo label types (30256, 30334, 30332, 30330, 30252)
- **Advanced Dithering Algorithms**: 11+ dithering options including Floyd-Steinberg, Bayer, Yliluoma, and more
- **Image Enhancement**: Adjustable brightness and contrast for optimal thermal printing
- **Auto-Printer Detection**: Automatically detects Dymo printers on macOS
- **Smart Image Fitting**: Automatically fits images to label dimensions while maintaining aspect ratio

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/dymo_picture_print.git
cd dymo_picture_print
```

2. Create and activate a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage
```bash
python dymo_print.py image.jpg
```

### Advanced Usage
```bash
python dymo_print.py image.jpg --label 30256 --dither floyd-steinberg --brightness 1.3 --contrast 1.1 --printer "DYMO LabelWriter 450"
```

### Command-Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `image` | Path to image file | Required (or prompted) |
| `--printer` | Name of printer to use | Auto-detected |
| `--label` | Dymo label code (see below) | `30256` |
| `--brightness` | Brightness factor (0.5-2.0 recommended) | `1.2` |
| `--contrast` | Contrast factor (0.5-2.0 recommended) | `1.0` |
| `--dither` | Dithering algorithm (see below) | `floyd` |

## Supported Label Types

| Code | Name | Dimensions | Best For |
|------|------|------------|----------|
| `30256` | Shipping Label | 2-5/16" × 4" | Photos, artwork |
| `30334` | Medium Rectangle | 2-1/4" × 1-1/4" | Small photos, stickers |
| `30332` | Square | 1" × 1" | Tiny images, icons |
| `30330` | Return Address | 3/4" × 2" | Narrow photos |
| `30252` | Address Label | 28mm × 89mm | Standard photos |

## Dithering Algorithms

The script supports multiple dithering algorithms from the `hitherdither` library:

### Ordered Dithering
- `bayer` - Bayer matrix dithering (good for photos)
- `yliluoma` - Yliluoma's 1 ordered dithering (high quality)
- `cluster` - Cluster-dot dithering (newspaper-like)

### Error Diffusion Dithering
- `floyd` / `floyd-steinberg` - Floyd-Steinberg (default, great balance)
- `atkinson` - Atkinson dithering (softer, Mac-like)
- `jarvis-judice-ninke` - JJN dithering (detailed)
- `stucki` - Stucki dithering (smooth)
- `burkes` - Burkes dithering (fast)
- `sierra3` - Sierra-3 dithering
- `sierra2` - Sierra-2 dithering
- `sierra-2-4a` - Sierra Lite dithering

### Other
- `none` - Simple threshold (no dithering)

## Examples

### Print a shipping label with Atkinson dithering:
```bash
python dymo_print.py photo.jpg --label 30256 --dither atkinson
```

### Print a bright sticker with Bayer dithering:
```bash
python dymo_print.py logo.png --label 30334 --dither bayer --brightness 1.4
```

### Print with high contrast for better detail:
```bash
python dymo_print.py portrait.jpg --contrast 1.2 --dither floyd-steinberg
```

## Tips for Best Results

1. **Brightness**: Thermal printers tend to print darker. Try `--brightness 1.2` to `1.5` for better results.
2. **Contrast**: Increase contrast (`--contrast 1.1` to `1.3`) to reduce gray noise and improve definition.
3. **Dithering**: Experiment with different algorithms:
   - Use `floyd-steinberg` or `atkinson` for photos
   - Use `bayer` for textured, artistic looks
   - Use `yliluoma` for highest quality (slower)
4. **Image Preparation**: Pre-crop images to match label aspect ratio for best composition.

## Requirements

- macOS with CUPS (for `lp` and `lpstat` commands)
- Python 3.7+
- Pillow (PIL)
- hitherdither library
- Dymo LabelWriter printer

## Troubleshooting

**Printer not detected**: Run `lpstat -e` to list available printers, then use `--printer` with the exact name.

**Image too dark**: Increase `--brightness` to 1.3 or higher.

**Grainy output**: Increase `--contrast` to 1.1 or 1.2 to eliminate gray tones.

**Wrong label size**: Verify your label type and use the matching `--label` code.

## License

MIT License - Feel free to use and modify!
