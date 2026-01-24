# Thermal Picture Print

Python tool to dither and print photos on thermal label printers. Supports Dymo LabelWriter, COMER RX1106HD, and other standard thermal printers. Includes advanced dithering algorithms and image enhancement options for optimal thermal printing results.
![gui](/images/gui_example.png "thermal_print_gui.py")
## Features

- **Broad Printer Support**: Optimized for COMER RX1106HD and Dymo LabelWriter models.
- **Custom Print Options**: Pass arbitrary `lpoptions` directly to fine-tune your printer (darkness, speed, etc.).
- **Multiple Label Sizes**: Support for standard 4x6 shipping labels and many Dymo-specific sizes.
- **Dynamic Label Filtering**: GUI automatically shows relevant labels based on the selected printer.
- **Advanced Dithering**: 15+ dithering options including Floyd-Steinberg, Riemersma, Bayer, and Atkinson.
- **Auto-Orientation**: Automatically aligns the long side of your photo to the long side of the label.
- **Save Dithered Image**: Export your processed 1-bit monochrome images to PNG files.
- **Interactive Fine-Tuning**: Real-time preview of all adjustments in the GUI.

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/thermal_picture_print.git
cd thermal_picture_print
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

4. **(macOS with Homebrew Python only)** Install tkinter for GUI support:
```bash
brew install python-tk@3.13
```
   > Note: If you're using system Python or Python from python.org, tkinter is already included.

## GUI Usage (Recommended)

For an easier, more visual experience, use the GUI version:

```bash
python thermal_print_gui.py
```

### GUI Features

- **Live Preview**: See how your image will look before printing with real-time updates.
- **Interactive Controls**: Adjust brightness and contrast with sliders.
- **Save Image**: Export the dithered result directly to a PNG.
- **Dynamic Selection**: Selecting your printer automatically filters the available label types.
- **Custom Options**: Enter `lpoptions` strings (like `Darkness=10`) directly in the UI.

## Command-Line Usage

### Basic Usage
```bash
python thermal_print.py image.jpg
```

### Advanced Usage
```bash
python thermal_print.py image.jpg --label 4x6 --dither floyd-steinberg --lp-options "Darkness=10" --printer "_RX106HD"
```

### Command-Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `image` | Path to image file | Required (or prompted) |
| `--printer` | Name of printer to use | Auto-detected |
| `--label` | Label code (e.g., `4x6`, `30256`) | `4x6` |
| `--brightness` | Brightness factor (0.5-2.0 recommended) | `1.2` |
| `--contrast` | Contrast factor (0.5-2.0 recommended) | `1.0` |
| `--dither` | Dithering algorithm | `floyd` |
| `--lp-options` | Custom `lp` options (e.g., `Darkness=10`) | None |
| `--riemersma-history`| Riemersma history depth (2-32) | `16` |
| `--riemersma-ratio` | Riemersma error decay ratio (0.1-0.9) | `0.1` |

## Supported Label Types

| Code | Name | Best For |
|------|------|----------|
| `4x6` | Shipping Label (Generic/COMER) | Large photos, shipping |
| `4x4` | Square Label (Generic) | Square artwork |
| `30256` | Dymo Shipping | 450/550 Shipping |
| `30334` | Dymo Medium Rectangle | Stickers |
| `30332` | Dymo Square | Icons |

## Tips for Best Results

1. **Brightness**: Thermal printers tend to print darker. Try `--brightness 1.2` to `1.5`.
2. **Contrast**: Increase contrast (`--contrast 1.1` to `1.3`) to reduce gray noise and improve definition.
3. **Dithering**: Experiment with different algorithms:
   - Use `floyd-steinberg` or `atkinson` for photos.
   - Use `riemersma` for the highest quality gradients and reduced banding.
   - Use `bayer` or `yliluoma` for crisp, textured looks.
4. **Custom Options**: For COMER printers, try adding `Darkness=10` or `PrintSpeed=40` in the Custom Print Options field.

## License

MIT License - Feel free to use and modify!
