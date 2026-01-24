#!/usr/bin/env python3
"""
GUI for Thermal Picture Print
Provides interactive controls for image adjustment and real-time preview
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import queue
import sys

# Import core functions from thermal_print
from thermal_print import LABEL_SPECS, list_printers, prepare_image, print_raw


class ThermalPrintGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Thermal Picture Print")
        self.root.geometry("1000x700")
        
        # State variables
        self.current_image_path = None
        self.original_image = None
        self.preview_image = None
        self.processed_image = None  # Store the latest fully processed PIL image
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
            'stucki', 'burkes', 'sierra3', 'sierra2', 'sierra-2-4a', 'ascii', 'riemersma'
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

        # Riemersma specific controls
        self.riemersma_frame = ttk.Frame(controls_frame)
        self.riemersma_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # History depth slider
        ttk.Label(self.riemersma_frame, text="History Depth:").grid(row=0, column=0, sticky=tk.W, pady=(5, 0))
        self.history_depth_var = tk.IntVar(value=16)
        self.history_depth_slider = tk.Scale(
            self.riemersma_frame, from_=2, to=32,
            variable=self.history_depth_var,
            orient=tk.HORIZONTAL,
            resolution=1,
            showvalue=False
        )
        self.history_depth_slider.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.history_depth_label = ttk.Label(self.riemersma_frame, text="16")
        self.history_depth_label.grid(row=0, column=1, sticky=tk.E, pady=(5, 0))
        self.history_depth_var.trace_add('write', lambda *args: self.history_depth_label.config(text=str(self.history_depth_var.get())))

        # Ratio slider
        ttk.Label(self.riemersma_frame, text="Ratio:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        self.ratio_var = tk.DoubleVar(value=0.1)
        self.ratio_slider = tk.Scale(
            self.riemersma_frame, from_=0.1, to=0.9,
            variable=self.ratio_var,
            orient=tk.HORIZONTAL,
            resolution=0.1,
            showvalue=False
        )
        self.ratio_slider.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.ratio_label = ttk.Label(self.riemersma_frame, text="0.10")
        self.ratio_label.grid(row=2, column=1, sticky=tk.E, pady=(5, 0))
        self.ratio_var.trace_add('write', lambda *args: self.ratio_label.config(text=f"{self.ratio_var.get():.2f}"))

        # Initialize visibility
        self.toggle_riemersma_controls()

        # Label type dropdown
        ttk.Label(controls_frame, text="Label Type:").grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.label_var = tk.StringVar(value="4x6")
        label_options = [f"{code} - {spec['name']}" for code, spec in LABEL_SPECS.items()]
        self.label_combo = ttk.Combobox(
            controls_frame, 
            textvariable=self.label_var, 
            values=label_options,
            state='readonly',
            width=25
        )
        self.label_combo.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.label_combo.current(0)
        self.label_combo.bind('<<ComboboxSelected>>', lambda e: self.update_label_info())
        
        # Refresh preview button
        self.refresh_btn = ttk.Button(
            controls_frame,
            text="Refresh Preview",
            command=self.update_preview,
            state=tk.DISABLED
        )
        self.refresh_btn.grid(row=10, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Printer selection dropdown
        ttk.Label(controls_frame, text="Printer:").grid(row=11, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.printer_var = tk.StringVar()
        self.printer_combo = ttk.Combobox(
            controls_frame, 
            textvariable=self.printer_var,
            state='readonly',
            width=25
        )
        self.printer_combo.grid(row=12, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.printer_combo.bind('<<ComboboxSelected>>', self.update_label_list)
        
        # Custom lp options
        ttk.Label(controls_frame, text="Custom Print Options (lpoptions):").grid(row=13, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.lp_options_var = tk.StringVar()
        self.lp_options_entry = ttk.Entry(
            controls_frame,
            textvariable=self.lp_options_var,
            width=25
        )
        self.lp_options_entry.grid(row=14, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Label info display
        self.info_frame = ttk.LabelFrame(controls_frame, text="Label Information", padding="5")
        self.info_frame.grid(row=15, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        self.info_label = ttk.Label(self.info_frame, text="", justify=tk.LEFT)
        self.info_label.pack()
        self.update_label_info()
        
        # Print button
        self.print_btn = ttk.Button(
            controls_frame, 
            text="Print Image", 
            command=self.print_image,
            state=tk.DISABLED
        )
        self.print_btn.grid(row=16, column=0, columnspan=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # Save button
        self.save_btn = ttk.Button(
            controls_frame,
            text="Save Image",
            command=self.save_image,
            state=tk.DISABLED
        )
        self.save_btn.grid(row=16, column=1, columnspan=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
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
            # Auto-select preferred printer if available
            target_keywords = ["dymo", "rx106", "comer"]
            preferred_printers = [p for p in printers if any(kw in p.lower() for kw in target_keywords)]
            
            if preferred_printers:
                self.printer_combo.set(preferred_printers[0])
            else:
                self.printer_combo.current(0)
            
            # Update label list for selected printer
            self.update_label_list()
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
                self.save_btn.config(state=tk.NORMAL)
                self.refresh_btn.config(state=tk.NORMAL)
                
                # Generate preview
                self.update_preview()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open image:\n{str(e)}")
    
    def get_label_code(self):
        """Extract label code from combo box selection"""
        selection = self.label_var.get()
        return selection.split(' - ')[0]

    def update_label_list(self, event=None):
        """Update label combo box based on selected printer"""
        printer = self.printer_var.get().lower()
        
        # Determine brand filter
        brand_filter = 'dymo' if 'dymo' in printer else 'generic'
        
        # Filter labels
        filtered_labels = [
            f"{code} - {spec['name']}" 
            for code, spec in LABEL_SPECS.items() 
            if spec.get('brand') == brand_filter
        ]
        
        # Update combo values
        self.label_combo['values'] = filtered_labels
        
        # Select first or stay if still available
        current = self.label_var.get()
        # Find if current exists in new list (comparison by code/prefix)
        # Check if the code part matches
        current_code = current.split(' - ')[0]
        match = next((l for l in filtered_labels if l.startswith(f"{current_code} - ")), None)
        
        if match:
            self.label_combo.set(match)
        elif filtered_labels:
            self.label_combo.current(0)
            
        # Add default Dymo lpoptions if switching to a Dymo printer
        if brand_filter == 'dymo':
            current_opts = self.lp_options_var.get()
            dymo_defaults = "DymoPrintDensity=Medium DymoPrintQuality=Graphics"
            # Only set if empty or previously generic to avoid overwriting user changes?
            # For simplicity, if it's currently empty, set it.
            if not current_opts:
                self.lp_options_var.set(dymo_defaults)
        elif brand_filter == 'generic':
            # Clear Dymo defaults if switching back to generic, but only if they match the defaults
            current_opts = self.lp_options_var.get()
            if current_opts == "DymoPrintDensity=Medium DymoPrintQuality=Graphics":
                self.lp_options_var.set("")

        self.update_label_info()
    
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
        self.toggle_riemersma_controls()
        if self.current_image_path:
            self.update_preview()

    def toggle_riemersma_controls(self):
        """Show/hide Riemersma parameters based on selection"""
        if self.dither_var.get() == 'riemersma':
            self.riemersma_frame.grid()
        else:
            self.riemersma_frame.grid_remove()
    
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
            riemersma_history = self.history_depth_var.get()
            riemersma_ratio = self.ratio_var.get()
            
            # Generate processed image
            processed = prepare_image(
                self.current_image_path,
                spec,
                brightness=brightness,
                contrast=contrast,
                dither_alg=dither,
                riemersma_history=riemersma_history,
                riemersma_ratio=riemersma_ratio
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
                    self.processed_image = result_data
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
            riemersma_history = self.history_depth_var.get()
            riemersma_ratio = self.ratio_var.get()
            
            # Disable print button during printing
            self.print_btn.config(state=tk.DISABLED, text="Printing...")
            self.status_label.config(text="Sending to printer...")
            
            # Print in background thread to keep UI responsive
            def print_thread():
                try:
                    print_raw(
                        self.current_image_path,
                        printer,
                        label_code=label_code,
                        brightness=brightness,
                        contrast=contrast,
                        dither_alg=dither,
                        riemersma_history=riemersma_history,
                        riemersma_ratio=riemersma_ratio,
                        custom_options=self.lp_options_var.get()
                    )
                    self.root.after(0, lambda: self.print_complete(None))
                except Exception as e:
                    self.root.after(0, lambda: self.print_complete(str(e)))
            
            threading.Thread(target=print_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print:\n{str(e)}")
            self.print_btn.config(state=tk.NORMAL, text="Print Image")
    
    def print_complete(self, error):
        """Called when print job completes"""
        self.print_btn.config(state=tk.NORMAL, text="Print Image")
        
        if error:
            messagebox.showerror("Print Error", f"Failed to print:\n{error}")
            self.status_label.config(text="Print failed")
        else:
            #messagebox.showinfo("Success", "Print job sent successfully!")
            self.status_label.config(text="Print job sent")

    def save_image(self):
        """Save the processed image to a file"""
        if not self.processed_image or not self.current_image_path:
            messagebox.showwarning("No Image", "Please open an image first")
            return
            
        import os
        # Pre-populate with original filename but .png extension
        base_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
        initial_file = f"{base_name}.png"
        
        file_path = filedialog.asksaveasfilename(
            title="Save Dithered Image",
            defaultextension=".png",
            initialfile=initial_file,
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.processed_image.save(file_path)
                self.status_label.config(text=f"Image saved to {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save image:\n{str(e)}")


def main():
    root = tk.Tk()
    app = ThermalPrintGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
