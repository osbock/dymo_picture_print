import subprocess
import os
import sys
import argparse
from PIL import Image, ImageEnhance
import hitherdither

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

def prepare_image(image_path, label_spec, brightness=1.2, contrast=1.0, dither_alg='floyd'):
    """
    Prepare image for a specific Dymo label.
    """
    img = Image.open(image_path).convert('L')

    # --- Lightening

    brightness_factor=1.2
    enhancer = ImageEnhance.Brightness(img)
    img= enhancer.enhance(brightness_factor)
    
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
    else:
        # Fallback to simple threshold if unknown or 'none'
        return img.convert('1', dither=Image.NONE)

def print_to_dymo_raw(image_path, printer_name, label_code='30256', brightness=1.2, contrast=1.0, dither_alg='floyd'):
    if label_code not in LABEL_SPECS:
        print(f"Error: Unknown label code '{label_code}'. Available: {list(LABEL_SPECS.keys())}")
        return

    spec = LABEL_SPECS[label_code]
    final_image = prepare_image(image_path, spec, brightness, contrast, dither_alg)
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
    parser.add_argument("--dither", choices=['floyd', 'bayer', 'yliluoma', 'cluster', 'none', 'floyd-steinberg', 'atkinson', 'jarvis-judice-ninke', 'stucki', 'burkes', 'sierra3', 'sierra2', 'sierra-2-4a'], default='floyd', help="Dithering algorithm (default: floyd)")
    parser.add_argument("--label", default='30256', help="Dymo Label Code (default: 30256). Choices: " + ", ".join(LABEL_SPECS.keys()))
    
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
        print_to_dymo_raw(target_image, target_printer, args.label, args.brightness, args.contrast, args.dither)
    else:
        print("File not found.")
