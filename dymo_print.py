import subprocess
import os
import sys
import argparse
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
import hitherdither
import numpy as np


def ascii_dither(img, target_w, target_h):
    """
    Convert grayscale image to ASCII art dithering.
    Uses characters with different densities to represent brightness levels.
    Font size optimized for 300 DPI printing.
    """
    # ASCII characters ordered from light to dark by visual density
    # Using a 70-level character set for much smoother gradation
    ascii_chars = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczMW&8%B@$"
    
    # Font size: 2pt at 300 DPI = 2 * 300/72 = ~8 pixels tall
    # Smaller font = more characters = higher resolution
    font_size = 2  # points
    dpi = 300
    font_height_px = int(font_size * dpi / 72)  # ~8 pixels
    
    # Try to use a monospace font for consistent character width
    # Fall back to default if not available
    try:
        # Try common monospace fonts on macOS
        font = ImageFont.truetype("/System/Library/Fonts/Courier.dfont", font_height_px)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Monaco.dfont", font_height_px)
        except:
            # Fall back to default font
            font = ImageFont.load_default()
    
    # Calculate character dimensions using getbbox
    # Test with a dense character to get max dimensions
    bbox = font.getbbox("@")
    char_width = bbox[2] - bbox[0]
    char_height = bbox[3] - bbox[1]
    
    # Calculate how many characters fit in target dimensions
    cols = target_w // char_width
    rows = target_h // char_height
    
    # Resize image to match character grid
    img_resized = img.resize((cols, rows), Image.Resampling.LANCZOS)
    
    # Create output image
    output = Image.new('L', (target_w, target_h), 255)  # White background
    draw = ImageDraw.Draw(output)
    
    # Convert each pixel to ASCII character
    pixels = img_resized.load()
    for row in range(rows):
        for col in range(cols):
            # Get brightness (0=black, 255=white)
            brightness = pixels[col, row]
            
            # Map brightness to ASCII character
            # Invert because we want dark chars for dark areas
            char_index = int((255 - brightness) / 255 * (len(ascii_chars) - 1))
            char_index = min(char_index, len(ascii_chars) - 1)
            char = ascii_chars[char_index]
            
            # Draw character
            x = col * char_width
            y = row * char_height
            draw.text((x, y), char, fill=0, font=font)  # Black text
    
    return output

def get_hilbert_curve(width, height):
    """
    Generate Hilbert curve coordinates (x, y) for a rectangle.
    Since Hilbert curves are for powers of 2, we use a larger power of 2
    and filter out coordinates outside the rectangle.
    """
    size = 1
    while size < width or size < height:
        size *= 2
    
    def rot(n, x, y, rx, ry):
        if ry == 0:
            if rx == 1:
                x = n - 1 - x
                y = n - 1 - y
            return y, x
        return x, y

    def d2xy(n, d):
        t = d
        x = y = 0
        s = 1
        while s < n:
            rx = 1 & (t // 2)
            ry = 1 & (t ^ rx)
            x, y = rot(s, x, y, rx, ry)
            x += s * rx
            y += s * ry
            t //= 4
            s *= 2
        return x, y

    for d in range(size * size):
        x, y = d2xy(size, d)
        if x < width and y < height:
            yield x, y

def riemersma_dither(img, history_depth=16, ratio=0.1):
    """
    Implement Riemersma Dithering using a Hilbert curve.
    history_depth: number of previous errors to keep
    ratio: exponential decay ratio for error weighting
    """
    # Convert to float and extract pixels
    img_data = np.array(img, dtype=float)
    h, w = img_data.shape
    
    # Pre-calculate weights
    weights = np.zeros(history_depth)
    for i in range(history_depth):
        weights[i] = ratio ** (i / (history_depth - 1))
    weights /= np.sum(weights)  # Normalize
    
    # Error queue
    error_queue = np.zeros(history_depth)
    
    # Process along Hilbert curve
    output = np.zeros_like(img_data, dtype=np.uint8)
    for x, y in get_hilbert_curve(w, h):
        # Calculate expected value with weighted error history
        total_error = np.sum(error_queue * weights)
        old_pixel = img_data[y, x] + total_error
        
        # Quantize
        new_pixel = 255 if old_pixel > 127.5 else 0
        output[y, x] = new_pixel
        
        # Update error history
        error = old_pixel - new_pixel
        error_queue = np.roll(error_queue, 1)
        error_queue[0] = error
        
    return Image.fromarray(output, mode='L')

# Label Specifications
# ID is the CUPS PageSize name.
# Dimensions are in pixels at 300 DPI.
# width_points and height_points are for verification/reference (1/72 inch).
LABEL_SPECS = {
    '30256': {
        'name': 'Shipping (2-5/16" x 4")',
        'id': 'w167h288',
        'width_px': 694,  # ~2.31" * 300
        'height_px': 1200, # 4" * 300
        'rotate': True     # Long edge is usually height
    },
    '30334': {
        'name': '2-1/4" x 1-1/4"',
        'id': 'w162h90', 
        'width_px': 675, # 2.25 * 300
        'height_px': 375, # 1.25 * 300
        'rotate': False # Width > Height, might not need rotation depending on roll
    },
    '30332': {
        'name': '1" x 1"',
        'id': 'w72h72',
        'width_px': 300,
        'height_px': 300,
        'rotate': False
    },
    '30330': {
        'name': 'Return Address (3/4" x 2")',
        'id': 'w54h144', # 0.75 * 72 = 54, 2 * 72 = 144
        'width_px': 225, # 0.75 * 300
        'height_px': 600, # 2 * 300
        'rotate': True
    },
    '30252': {
        'name': 'Address (28mm x 89mm / 1.1" x 3.5")',
        'id': 'w79h252',
        'width_px': 331,  # 28mm = 1.102" * 300
        'height_px': 1051, # 89mm = 3.504" * 300
        'rotate': True
    }
}

def list_printers():
    """Helper to list available printer names on macOS."""
    try:
        # 'lpstat -e' lists all distinct printer destinations
        result = subprocess.check_output(['lpstat', '-e'], text=True)
        printers = result.strip().split('\n')
        return printers
    except FileNotFoundError:
        print("Error: 'lpstat' command not found. Are you on macOS?")
        return []

def prepare_image(image_path, label_spec, brightness=1.2, contrast=1.0, dither_alg='floyd', riemersma_history=16, riemersma_ratio=0.1):
    """
    Prepare image for a specific Dymo label.
    """
    img = Image.open(image_path).convert('L')

    # --- Lightening

    enhancer = ImageEnhance.Brightness(img)
    img= enhancer.enhance(brightness)
    
    # High-Contrast Pre-processing
    # This helps eliminate 'gray noise' that causes banding in thermal prints
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast) 
    
    # 2. Orientation
    # Rotate if needed based on spec (usually for labels that print along the roll)
    if label_spec['rotate']:
        # Check if user image is already portrait/landscape matching the target? 
        # For simple logic: assume input should be fit to the label's main axis.
        # If the label is "tall" (like shipping), we typically rotate "wide" images to fit.
        if img.height < img.width:
             img = img.rotate(90, expand=True)
    
    # 3. Precise Resizing
    target_w = label_spec['width_px']
    target_h = label_spec['height_px']
    
    # Maintain aspect ratio?
    # Strategy: Fit within target dimensions, centering? Or fill?
    # Original logic was "Target 694px height" (which was actually width of roll).
    # dymo_print.py's original logic seemed to assume fitting 
    # to the 694px dimension (which is the roll width).
    
    # Let's try to fit to the label dimensions while maintaining aspect ratio,
    # then center on a white background.
    
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h
    
    if img_ratio > target_ratio:
        # Image is wider than target
        new_w = target_w
        new_h = int(target_w / img_ratio)
    else:
        # Image is taller than target
        new_h = target_h
        new_w = int(target_h * img_ratio)
        
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Create canvas
    canvas = Image.new('L', (target_w, target_h), 255)
    # Center
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2
    canvas.paste(img, (paste_x, paste_y))
    img = canvas

    # 4. Convert to 1-bit monochrome
    if dither_alg == 'floyd':
        return img.convert('1', dither=Image.FLOYDSTEINBERG)
    elif dither_alg == 'bayer':
        # hitherdither requires an RGB image for some reason, or at least works better with palette
        # But for 1-bit, we can try direct. 
        # Actually hitherdither.ordered.bayer.bayer_dithering works on PIL images.
        # Let's check the palette. 
        # We need a bilevel palette.
        palette = hitherdither.palette.Palette(
            [(0, 0, 0), (255, 255, 255)]
        )
        img_rgb = img.convert("RGB")
        return hitherdither.ordered.bayer.bayer_dithering(
            img_rgb, palette, [255/2, 255/2, 255/2], order=8
        ).convert('1')
    elif dither_alg == 'yliluoma':
         palette = hitherdither.palette.Palette(
            [(0, 0, 0), (255, 255, 255)]
        )
         img_rgb = img.convert("RGB")
         return hitherdither.ordered.yliluoma.yliluomas_1_ordered_dithering(
            img_rgb, palette, order=8
        ).convert('1')
    elif dither_alg == 'cluster':
         palette = hitherdither.palette.Palette(
            [(0, 0, 0), (255, 255, 255)]
        )
         img_rgb = img.convert("RGB")
         return hitherdither.ordered.cluster.cluster_dot_dithering(
            img_rgb, palette, thresholds=[255/2, 255/2, 255/2], order=8
        ).convert('1')
    elif dither_alg in ['floyd-steinberg', 'atkinson', 'jarvis-judice-ninke', 'stucki', 'burkes', 'sierra3', 'sierra2', 'sierra-2-4a']:
        palette = hitherdither.palette.Palette(
            [(0, 0, 0), (255, 255, 255)]
        )
        img_rgb = img.convert("RGB")
        return hitherdither.diffusion.error_diffusion_dithering(
            img_rgb, palette, method=dither_alg, order=8
        ).convert('1')
    elif dither_alg == 'ascii':
        # ASCII art dithering - renders text characters based on brightness
        ascii_img = ascii_dither(img, target_w, target_h)
        return ascii_img.convert('1')
    elif dither_alg == 'riemersma':
        # Riemersma dithering - high quality Hilbert curve error diffusion
        return riemersma_dither(img, history_depth=riemersma_history, ratio=riemersma_ratio).convert('1')
    else:
        # Fallback to simple threshold if unknown or 'none'
        return img.convert('1', dither=Image.NONE)

def print_to_dymo_raw(image_path, printer_name, label_code='30256', brightness=1.2, contrast=1.0, dither_alg='floyd', riemersma_history=16, riemersma_ratio=0.1):
    if label_code not in LABEL_SPECS:
        print(f"Error: Unknown label code '{label_code}'. Available: {list(LABEL_SPECS.keys())}")
        return

    spec = LABEL_SPECS[label_code]
    final_image = prepare_image(image_path, spec, brightness, contrast, dither_alg, riemersma_history, riemersma_ratio)
    temp_file = "dymo_final.png"
    final_image.save(temp_file)

    # COMMAND CHANGES:
    # Use spec ID for PageSize
    cmd = [
        "lp", 
        "-d", printer_name, 
        "-o", f"PageSize={spec['id']}",
        "-o", "scaling=100",
        "-o", "ppi=300",
        temp_file
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Sent {image_path} to {printer_name} using media {spec['id']}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

# Usage

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print images to Dymo LabelWriter")
    parser.add_argument("image", nargs="?", help="Path to image file")
    parser.add_argument("--printer", help="Name of the printer to use")
    parser.add_argument("--brightness", type=float, default=1.2, help="Brightness factor (default: 1.2)")
    parser.add_argument("--contrast", type=float, default=1.0, help="Contrast factor (default: 1.0)")
    parser.add_argument("--dither", choices=['floyd', 'bayer', 'yliluoma', 'cluster', 'none', 'floyd-steinberg', 'atkinson', 'jarvis-judice-ninke', 'stucki', 'burkes', 'sierra3', 'sierra2', 'sierra-2-4a', 'ascii', 'riemersma'], default='floyd', help="Dithering algorithm (default: floyd)")
    parser.add_argument("--label", default='30256', help="Dymo Label Code (default: 30256). Choices: " + ", ".join(LABEL_SPECS.keys()))
    parser.add_argument("--riemersma-history", type=int, default=16, help="Riemersma history depth (default: 16)")
    parser.add_argument("--riemersma-ratio", type=float, default=0.1, help="Riemersma error decay ratio (default: 0.1)")
    
    args = parser.parse_args()

    # --- STEP 1: Find your printer ---
    if args.printer:
        target_printer = args.printer
    else:
        available_printers = list_printers()
        
        if not available_printers:
            print("No printers found! Check your connections.")
            sys.exit(1)

        # Simple logic to pick a printer
        # If "Dymo" is in the name, pick it automatically, otherwise ask user or pick first.
        dymo_printers = [p for p in available_printers if "dymo" in p.lower()]
        
        if dymo_printers:
            target_printer = dymo_printers[0]
            print(f"Auto-selected Dymo printer: {target_printer}")
        else:
            print("Available printers:", available_printers)
            target_printer = input("Enter exact printer name from above: ")

    # --- STEP 2: Input Image ---
    if args.image:
        target_image = args.image
    else:
        target_image = input("Enter path to image file: ")

    # --- STEP 3: Print ---
    if os.path.exists(target_image):
        print_to_dymo_raw(target_image, target_printer, args.label, args.brightness, args.contrast, args.dither, args.riemersma_history, args.riemersma_ratio)
    else:
        print("File not found.")
