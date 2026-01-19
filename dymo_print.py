import subprocess
import os
import sys
from PIL import Image, ImageEnhance

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

def prepare_image_for_shipping_label(image_path):
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
    img = enhancer.enhance(1.0) 
    
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
    return img.convert('1', dither=Image.FLOYDSTEINBERG)

def print_to_dymo_raw(image_path, printer_name):
    final_image = prepare_image_for_shipping_label(image_path)
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
    # --- STEP 1: Find your printer ---
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
    # You can hardcode this or pass it as an argument
    if len(sys.argv) > 1:
        target_image = sys.argv[1]
    else:
        target_image = input("Enter path to image file: ")

    # --- STEP 3: Print ---
    if os.path.exists(target_image):
        print_to_dymo_raw(target_image, target_printer)
    else:
        print("File not found.")
