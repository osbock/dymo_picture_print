import subprocess
import os
import sys
import argparse
from PIL import Image, ImageEnhance
import hitherdither

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

def prepare_image_for_shipping_label(image_path, brightness=1.2, contrast=1.0, dither_alg='floyd'):
    """
    Optimized for 2-5/16" x 4" (30256) Dymo Labels.
    Physical Width: 2.31" @ 300 DPI = ~694 pixels.
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
    # On a shipping label roll, the 2.31" side is the 'height' of the print head.
    if img.height > img.width:
        img = img.rotate(90, expand=True)

    # 3. Precise Resizing
    # Target 694px height (the width of the 2-5/16" roll at 300 DPI)
    target_h = 694 
    aspect = img.width / img.height
    target_w = int(target_h * aspect)
    
    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

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

def print_to_dymo_raw(image_path, printer_name, brightness=1.2, contrast=1.0, dither_alg='floyd'):
    final_image = prepare_image_for_shipping_label(image_path, brightness, contrast, dither_alg)
    temp_file = "dymo_final.png"
    final_image.save(temp_file)

    # COMMAND CHANGES:
    # -o PageSize=w167h288: Matches your lpoptions exactly
    # -o scaling=100: Prevents the driver from re-interpolating the pixels
    # -o ppi=300: Tells the driver the density of the source file
    cmd = [
        "lp", 
        "-d", printer_name, 
        "-o", "PageSize=w167h288",
        "-o", "scaling=100",
        "-o", "ppi=300",
        temp_file
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Sent {image_path} to {printer_name} using media w167h288")
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
        print_to_dymo_raw(target_image, target_printer, args.brightness, args.contrast, args.dither)
    else:
        print("File not found.")
