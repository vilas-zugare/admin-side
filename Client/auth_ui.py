import tkinter as tk
from tkinter import ttk, messagebox
from api_client import APIClient
from config import Config
 
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=150, height=40, corner_radius=20, bg_color="#007bff", hover_color="#0056b3", text_color="white"):
        super().__init__(parent, width=width, height=height, bg=parent['bg'] if 'bg' in parent.keys() else "#f0f2f5", highlightthickness=0)
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.text = text
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
       
        self.draw_button(self.bg_color)
       
        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
 
    def draw_button(self, color):
        self.delete("all")
        r = self.corner_radius
        w = self.width
        h = self.height
       
        # Draw the rounded shape
        # Top-left arc
        self.create_arc(0, 0, 2*r, 2*r, start=90, extent=90, fill=color, outline=color)
        # Top-right arc
        self.create_arc(w-2*r, 0, w, 2*r, start=0, extent=90, fill=color, outline=color)
        # Bottom-right arc
        self.create_arc(w-2*r, h-2*r, w, h, start=270, extent=90, fill=color, outline=color)
        # Bottom-left arc
        self.create_arc(0, h-2*r, 2*r, h, start=180, extent=90, fill=color, outline=color)
       
        # Rectangles to fill the gaps
        self.create_rectangle(r, 0, w-r, h, fill=color, outline=color)
        self.create_rectangle(0, r, w, h-r, fill=color, outline=color)
       
        # Text
        self.create_text(w/2, h/2, text=self.text, fill=self.text_color, font=("Segoe UI", 10, "bold"))
 
    def on_click(self, event):
        if self.command:
            self.command()
 
    def on_enter(self, event):
        self.configure(cursor="hand2")
        self.draw_button(self.hover_color)
 
    def on_leave(self, event):
        self.configure(cursor="")
        self.draw_button(self.bg_color)
 
class AuthApp:
    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success
        self.api = APIClient()
        self.device_id = Config.get_device_id()
        self.device_name = Config.get_device_name()
       
        self.root.title("Employee Login")
        self.root.geometry("400x500")
        self.root.configure(bg="#f0f2f5")
       
        # Center the window
        self.center_window()
       
        self.setup_styles()
        self.show_login()
 
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
 
    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
       
        # Configure colors and fonts
        bg_color = "#f0f2f5"
        text_color = "#333333"
       
        self.style.configure(".", background=bg_color, foreground=text_color, font=("Segoe UI", 10))
        self.style.configure("TLabel", background=bg_color, foreground=text_color)
        # TButton not used for main actions anymore, but configured just in case
        self.style.configure("TButton", padding=10, font=("Segoe UI", 10, "bold"))
        self.style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground=text_color)
 
    def clear_frame(self):
        for widget in self.root.winfo_children():
            widget.destroy()
 
    def show_login(self):
        self.clear_frame()
       
        # Outer frame for centering
        outer_frame = tk.Frame(self.root, bg="#f0f2f5")
        outer_frame.pack(expand=True, fill="both", padx=20, pady=20)
       
        # Header
        ttk.Label(outer_frame, text="Employee Login", style="Title.TLabel").pack(pady=(0, 30))
       
        # Form
        input_frame = tk.Frame(outer_frame, bg="#f0f2f5")
        input_frame.pack(fill="x")
       
        ttk.Label(input_frame, text="Email Address").pack(anchor="w", pady=(0, 5))
        self.email_entry = ttk.Entry(input_frame, font=("Segoe UI", 10))
        self.email_entry.pack(fill="x", pady=(0, 15), ipady=5)
       
        ttk.Label(input_frame, text="Password").pack(anchor="w", pady=(0, 5))
        self.password_entry = ttk.Entry(input_frame, show="•", font=("Segoe UI", 10))
        self.password_entry.pack(fill="x", pady=(0, 25), ipady=5)
       
        # Actions
        # Custom Rounded Button for Login
        login_btn = RoundedButton(outer_frame, text="LOGIN", command=self.do_login,
                                  width=160, height=45, corner_radius=22,
                                  bg_color="#007bff", hover_color="#0056b3")
        login_btn.pack(pady=(0, 20))
       
        ttk.Separator(outer_frame, orient='horizontal').pack(fill='x', pady=15)
       
        ttk.Label(outer_frame, text="Don't have an account?", font=("Segoe UI", 9)).pack(pady=(0, 10))
       
        # Secondary button (Grey)
        reg_btn = RoundedButton(outer_frame, text="Create Account", command=self.show_register,
                                width=160, height=45, corner_radius=22,
                                bg_color="#6c757d", hover_color="#5a6268")
        reg_btn.pack()
 
    def show_register(self):
        self.clear_frame()
       
        outer_frame = tk.Frame(self.root, bg="#f0f2f5")
        outer_frame.pack(expand=True, fill="both", padx=20, pady=20)
       
        # Header
        ttk.Label(outer_frame, text="Create Account", style="Title.TLabel").pack(pady=(0, 20))
       
        # Form
        input_frame = tk.Frame(outer_frame, bg="#f0f2f5")
        input_frame.pack(fill="x")
       
        ttk.Label(input_frame, text="Full Name").pack(anchor="w", pady=(0, 5))
        self.name_entry = ttk.Entry(input_frame, font=("Segoe UI", 10))
        self.name_entry.pack(fill="x", pady=(0, 15), ipady=5)
       
        ttk.Label(input_frame, text="Email Address").pack(anchor="w", pady=(0, 5))
        self.reg_email_entry = ttk.Entry(input_frame, font=("Segoe UI", 10))
        self.reg_email_entry.pack(fill="x", pady=(0, 15), ipady=5)
       
        ttk.Label(input_frame, text="Password").pack(anchor="w", pady=(0, 5))
        self.reg_password_entry = ttk.Entry(input_frame, show="•", font=("Segoe UI", 10))
        self.reg_password_entry.pack(fill="x", pady=(0, 25), ipady=5)
       
        # Actions
        reg_btn = RoundedButton(outer_frame, text="REGISTER", command=self.do_register,
                                width=160, height=45, corner_radius=22,
                                bg_color="#007bff", hover_color="#0056b3")
        reg_btn.pack(pady=(0, 20))
       
        back_btn = RoundedButton(outer_frame, text="Back to Login", command=self.show_login,
                                 width=160, height=45, corner_radius=22,
                                 bg_color="#6c757d", hover_color="#5a6268")
        back_btn.pack()
 
    def do_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
       
        if not email or not password:
            messagebox.showwarning("Input Error", "Please fill in all fields.")
            return
 
        success, msg = self.api.login(email, password, self.device_id)
        if success:
            messagebox.showinfo("Success", "Login Successful")
            self.root.destroy()
            self.on_success()
        else:
            messagebox.showerror("Login Failed", msg)
 
    def do_register(self):
        name = self.name_entry.get().strip()
        email = self.reg_email_entry.get().strip()
        password = self.reg_password_entry.get().strip()
       
        if not name or not email or not password:
            messagebox.showwarning("Input Error", "Please fill in all fields.")
            return
 
        success, msg = self.api.register(name, email, password, self.device_id, self.device_name)
        if success:
            messagebox.showinfo("Success", msg)
            self.show_login()
        else:
            messagebox.showerror("Registration Failed", msg)
 
def launch_auth_ui(on_success):
    root = tk.Tk()
    app = AuthApp(root, on_success)
    root.mainloop()
 
 