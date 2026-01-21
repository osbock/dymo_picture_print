#!/usr/bin/env python3
"""
GUI for Dymo Picture Print
Provides interactive controls for image adjustment and real-time preview
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import queue
import sys

# Import core functions from dymo_print
from dymo_print import LABEL_SPECS, list_printers, prepare_image, print_to_dymo_raw


class DymoPrintGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Dymo Picture Print")
        self.root.geometry("1000x700")
        
        # State variables
        self.current_image_path = None
        self.original_image = None
        self.preview_image = None
        self.preview_queue = queue.Queue()
        self.preview_thread = None
        
        # Create UI
        self.create_widgets()
        
        # Load available printers
        self.load_printers()
        
        # Start preview queue processor
        self.process_preview_queue()
    
    def create_widgets(self):
        # Main container with two columns
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=1)
        main_container.rowconfigure(1, weight=1)
        
        # Left panel - Controls
        controls_frame = ttk.LabelFrame(main_container, text="Controls", padding="10")
        controls_frame.grid(row=0, column=0, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # File selection
        file_frame = ttk.Frame(controls_frame)
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        self.file_label = ttk.Label(file_frame, text="No image selected", wraplength=250)
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        open_btn = ttk.Button(file_frame, text="Open Image", command=self.open_image)
        open_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Brightness slider
        ttk.Label(controls_frame, text="Brightness:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.brightness_var = tk.DoubleVar(value=1.2)
        self.brightness_slider = tk.Scale(
            controls_frame, from_=0.5, to=2.0, 
            variable=self.brightness_var, 
            orient=tk.HORIZONTAL,
            resolution=0.1,
            showvalue=False
        )
        self.brightness_slider.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.brightness_label = ttk.Label(controls_frame, text="1.20")
        self.brightness_label.grid(row=1, column=1, sticky=tk.E, pady=(5, 0))
        self.brightness_var.trace_add('write', lambda *args: self.brightness_label.config(text=f"{self.brightness_var.get():.2f}"))
        
        # Contrast slider
        ttk.Label(controls_frame, text="Contrast:").grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
        self.contrast_var = tk.DoubleVar(value=1.0)
        self.contrast_slider = tk.Scale(
            controls_frame, from_=0.5, to=2.0, 
            variable=self.contrast_var, 
            orient=tk.HORIZONTAL,
            resolution=0.1,
            showvalue=False
        )
        self.contrast_slider.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.contrast_label = ttk.Label(controls_frame, text="1.00")
        self.contrast_label.grid(row=3, column=1, sticky=tk.E, pady=(5, 0))
        self.contrast_var.trace_add('write', lambda *args: self.contrast_label.config(text=f"{self.contrast_var.get():.2f}"))
        
        # Dithering method dropdown
        ttk.Label(controls_frame, text="Dithering Method:").grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.dither_var = tk.StringVar(value="floyd")
        dither_options = [
            'floyd', 'bayer', 'yliluoma', 'cluster', 'none',
            'floyd-steinberg', 'atkinson', 'jarvis-judice-ninke', 
            'stucki', 'burkes', 'sierra3', 'sierra2', 'sierra-2-4a'
        ]
        self.dither_combo = ttk.Combobox(
            controls_frame, 
            textvariable=self.dither_var, 
            values=dither_options,
            state='readonly',
            width=25
        )
        self.dither_combo.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.dither_combo.bind('<<ComboboxSelected>>', lambda e: self.on_dither_change())
        
        # Label type dropdown
        ttk.Label(controls_frame, text="Label Type:").grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.label_var = tk.StringVar(value="30256")
        label_options = [f"{code} - {spec['name']}" for code, spec in LABEL_SPECS.items()]
        self.label_combo = ttk.Combobox(
            controls_frame, 
            textvariable=self.label_var, 
            values=label_options,
            state='readonly',
            width=25
        )
        self.label_combo.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.label_combo.current(0)
        self.label_combo.bind('<<ComboboxSelected>>', lambda e: self.update_label_info())
        
        # Refresh preview button
        self.refresh_btn = ttk.Button(
            controls_frame,
            text="Refresh Preview",
            command=self.update_preview,
            state=tk.DISABLED
        )
        self.refresh_btn.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Printer selection dropdown
        ttk.Label(controls_frame, text="Printer:").grid(row=10, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.printer_var = tk.StringVar()
        self.printer_combo = ttk.Combobox(
            controls_frame, 
            textvariable=self.printer_var,
            state='readonly',
            width=25
        )
        self.printer_combo.grid(row=11, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Label info display
        self.info_frame = ttk.LabelFrame(controls_frame, text="Label Information", padding="5")
        self.info_frame.grid(row=12, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        self.info_label = ttk.Label(self.info_frame, text="", justify=tk.LEFT)
        self.info_label.pack()
        self.update_label_info()
        
        # Print button
        self.print_btn = ttk.Button(
            controls_frame, 
            text="Print to Dymo", 
            command=self.print_image,
            state=tk.DISABLED
        )
        self.print_btn.grid(row=13, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # Right panel - Preview
        preview_frame = ttk.LabelFrame(main_container, text="Preview", padding="10")
        preview_frame.grid(row=0, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        
        # Canvas for image preview
        self.canvas = tk.Canvas(preview_frame, bg='white', highlightthickness=1, highlightbackground='gray')
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status label
        self.status_label = ttk.Label(preview_frame, text="Open an image to begin", anchor=tk.CENTER)
        self.status_label.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
    
    def load_printers(self):
        """Load available printers from system"""
        printers = list_printers()
        if printers:
            self.printer_combo['values'] = printers
            # Auto-select Dymo printer if available
            dymo_printers = [p for p in printers if 'dymo' in p.lower()]
            if dymo_printers:
                self.printer_combo.set(dymo_printers[0])
            else:
                self.printer_combo.current(0)
        else:
            self.printer_combo['values'] = ["No printers found"]
            self.printer_combo.current(0)
    
    def open_image(self):
        """Open file dialog and load image"""
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.gif *.bmp *.tiff"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                self.current_image_path = file_path
                self.original_image = Image.open(file_path)
                
                # Update UI
                import os
                self.file_label.config(text=os.path.basename(file_path))
                self.print_btn.config(state=tk.NORMAL)
                self.refresh_btn.config(state=tk.NORMAL)
                
                # Generate preview
                self.update_preview()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open image:\n{str(e)}")
    
    def get_label_code(self):
        """Extract label code from combo box selection"""
        selection = self.label_var.get()
        return selection.split(' - ')[0]
    
    def update_label_info(self):
        """Update label information display"""
        label_code = self.get_label_code()
        if label_code in LABEL_SPECS:
            spec = LABEL_SPECS[label_code]
            info_text = f"Code: {label_code}\n"
            info_text += f"Size: {spec['name']}\n"
            info_text += f"Pixels: {spec['width_px']} × {spec['height_px']}"
            self.info_label.config(text=info_text)
    
    def on_dither_change(self):
        """Called when dithering method changes (still auto-preview)"""
        if self.current_image_path:
            self.update_preview()
    
    def update_preview(self):
        """Generate preview with current settings (threaded)"""
        if self.preview_thread and self.preview_thread.is_alive():
            # A preview is already being generated, skip
            return
        
        # Start preview generation in background thread
        self.status_label.config(text="Generating preview...")
        self.preview_thread = threading.Thread(target=self._generate_preview, daemon=True)
        self.preview_thread.start()
    
    def _generate_preview(self):
        """Background thread function to generate preview"""
        try:
            label_code = self.get_label_code()
            spec = LABEL_SPECS[label_code]
            brightness = self.brightness_var.get()
            contrast = self.contrast_var.get()
            dither = self.dither_var.get()
            
            # Generate processed image
            processed = prepare_image(
                self.current_image_path,
                spec,
                brightness=brightness,
                contrast=contrast,
                dither_alg=dither
            )
            
            # Put result in queue for main thread to display
            self.preview_queue.put(('success', processed))
            
        except Exception as e:
            self.preview_queue.put(('error', str(e)))
    
    def process_preview_queue(self):
        """Process preview generation results (runs in main thread)"""
        try:
            while True:
                result_type, result_data = self.preview_queue.get_nowait()
                
                if result_type == 'success':
                    self.display_preview(result_data)
                elif result_type == 'error':
                    self.status_label.config(text=f"Error: {result_data}")
                    
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.process_preview_queue)
    
    def display_preview(self, processed_image):
        """Display processed image in canvas"""
        try:
            # Get canvas dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # If canvas not yet sized, use default
            if canvas_width <= 1:
                canvas_width = 600
            if canvas_height <= 1:
                canvas_height = 500
            
            # For dithered images, we want to preserve the crisp 1-bit quality
            # Calculate scale to fit in canvas, but prefer integer multiples
            img_width, img_height = processed_image.size
            max_scale = min(canvas_width / img_width, canvas_height / img_height)
            
            # Find best integer scale that fits (1x, 2x, 3x, etc.) or 1.0 if too large
            if max_scale >= 3.0:
                scale = 3
            elif max_scale >= 2.0:
                scale = 2
            elif max_scale >= 1.0:
                scale = 1
            else:
                # Image is larger than canvas - show at 1:1 (will be cropped/centered)
                # This preserves the dithering quality better than downscaling
                scale = 1
            
            # Scale up using NEAREST neighbor to keep sharp pixels
            if scale > 1:
                new_width = img_width * scale
                new_height = img_height * scale
                display_image = processed_image.resize((new_width, new_height), Image.Resampling.NEAREST)
            else:
                display_image = processed_image
            
            # Convert to PhotoImage
            self.preview_image = ImageTk.PhotoImage(display_image)
            
            # Clear canvas and display
            self.canvas.delete("all")
            
            # Center image
            x = canvas_width // 2
            y = canvas_height // 2
            self.canvas.create_image(x, y, image=self.preview_image, anchor=tk.CENTER)
            
            # Update status with scale info
            if scale > 1:
                self.status_label.config(text=f"Preview: {processed_image.size[0]} × {processed_image.size[1]} pixels ({scale}x magnification)")
            else:
                self.status_label.config(text=f"Preview: {processed_image.size[0]} × {processed_image.size[1]} pixels (actual size)")
            
        except Exception as e:
            self.status_label.config(text=f"Display error: {str(e)}")
    
    def print_image(self):
        """Send image to printer"""
        if not self.current_image_path:
            messagebox.showwarning("No Image", "Please open an image first")
            return
        
        printer = self.printer_var.get()
        if not printer or printer == "No printers found":
            messagebox.showwarning("No Printer", "Please select a valid printer")
            return
        
        try:
            label_code = self.get_label_code()
            brightness = self.brightness_var.get()
            contrast = self.contrast_var.get()
            dither = self.dither_var.get()
            
            # Disable print button during printing
            self.print_btn.config(state=tk.DISABLED, text="Printing...")
            self.status_label.config(text="Sending to printer...")
            
            # Print in background thread to keep UI responsive
            def print_thread():
                try:
                    print_to_dymo_raw(
                        self.current_image_path,
                        printer,
                        label_code=label_code,
                        brightness=brightness,
                        contrast=contrast,
                        dither_alg=dither
                    )
                    self.root.after(0, lambda: self.print_complete(None))
                except Exception as e:
                    self.root.after(0, lambda: self.print_complete(str(e)))
            
            threading.Thread(target=print_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print:\n{str(e)}")
            self.print_btn.config(state=tk.NORMAL, text="Print to Dymo")
    
    def print_complete(self, error):
        """Called when print job completes"""
        self.print_btn.config(state=tk.NORMAL, text="Print to Dymo")
        
        if error:
            messagebox.showerror("Print Error", f"Failed to print:\n{error}")
            self.status_label.config(text="Print failed")
        else:
            messagebox.showinfo("Success", "Print job sent successfully!")
            self.status_label.config(text="Print job sent")


def main():
    root = tk.Tk()
    app = DymoPrintGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
