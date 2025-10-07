"""
LEGO Train Hub Control GUI
Comprehensive control interface for LEGO Powered Up Train Hub
"""

import asyncio
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from threading import Thread
from pybricksdev.ble import BLEConnection, find_device
from typing import Optional
import queue
from datetime import datetime

# LWP3 Protocol Constants
LWP3_SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123"
LWP3_CHAR_UUID = "00001624-1212-efde-1623-785feabcd123"
TARGET_NAME = "Train Base"

# Build LWP3 Commands
def make_start_speed(port_id: int, speed: int, max_power: int = 100, use_profile: int = 0) -> bytes:
    """StartSpeed command [0x07]"""
    if speed < -100 or speed > 100:
        raise ValueError("speed must be in [-100..100]")
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x07,
        (speed + 256) % 256,
        max_power & 0xFF,
        use_profile & 0xFF,
    ])
    return bytes([len(payload) + 1]) + payload

def make_start_speed_for_time(port_id: int, time_ms: int, speed: int,
                              max_power: int = 100, end_state: int = 127, use_profile: int = 0) -> bytes:
    """StartSpeedForTime command [0x09]"""
    if speed < -100 or speed > 100:
        raise ValueError("speed must be in [-100..100]")
    if max_power < 0 or max_power > 100:
        raise ValueError("max_power must be in [0..100]")
    time_l = time_ms & 0xFF
    time_h = (time_ms >> 8) & 0xFF
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x09,
        time_l, time_h,
        (speed + 256) % 256,
        max_power & 0xFF,
        end_state & 0xFF,
        use_profile & 0xFF,
    ])
    return bytes([len(payload) + 1]) + payload

def make_start_speed_for_degrees(port_id: int, degrees: int, speed: int,
                                 max_power: int = 100, end_state: int = 127, use_profile: int = 0) -> bytes:
    """StartSpeedForDegrees command [0x0B]"""
    if speed < -100 or speed > 100:
        raise ValueError("speed must be in [-100..100]")
    deg_bytes = degrees.to_bytes(4, byteorder='little', signed=True)
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x0B,
    ]) + deg_bytes + bytes([
        (speed + 256) % 256,
        max_power & 0xFF,
        end_state & 0xFF,
        use_profile & 0xFF,
    ])
    return bytes([len(payload) + 1]) + payload

def make_start_power(port_id: int, power: int) -> bytes:
    """StartPower command - unregulated power [0x01]"""
    if power < -100 or power > 100:
        raise ValueError("power must be in [-100..100]")
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x01,
        (power + 256) % 256,
    ])
    return bytes([len(payload) + 1]) + payload

def make_set_acc_time(port_id: int, time_ms: int, profile_no: int = 0) -> bytes:
    """SetAccTime command [0x05]"""
    time_l = time_ms & 0xFF
    time_h = (time_ms >> 8) & 0xFF
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x05,
        time_l, time_h,
        profile_no & 0xFF,
    ])
    return bytes([len(payload) + 1]) + payload

def make_set_dec_time(port_id: int, time_ms: int, profile_no: int = 0) -> bytes:
    """SetDecTime command [0x06]"""
    time_l = time_ms & 0xFF
    time_h = (time_ms >> 8) & 0xFF
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x06,
        time_l, time_h,
        profile_no & 0xFF,
    ])
    return bytes([len(payload) + 1]) + payload

def make_write_direct_mode_data(port_id: int, mode: int, *data: int) -> bytes:
    """WriteDirectModeData command [0x51]"""
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x51,
        mode & 0xFF,
    ] + [b & 0xFF for b in data])
    return bytes([len(payload) + 1]) + payload

def make_hub_led_color(color: int) -> bytes:
    """Set Hub LED color (port 50 is the hub LED)"""
    payload = bytes([
        0x00, 0x81, 0x32, 0x11, 0x51, 0x00, color & 0xFF
    ])
    return bytes([len(payload) + 1]) + payload

def make_hub_action(action: int) -> bytes:
    """Hub action command (0x02 = Disconnect, 0x2F = Shutdown, 0x30 = VCC Port On, 0x31 = VCC Port Off)"""
    payload = bytes([0x00, 0x02, action & 0xFF])
    return bytes([len(payload) + 1]) + payload

def make_port_info_request(port_id: int, info_type: int) -> bytes:
    """Request port information [0x21]"""
    payload = bytes([0x00, 0x21, port_id & 0xFF, info_type & 0xFF])
    return bytes([len(payload) + 1]) + payload

def make_port_input_format_setup(port_id: int, mode: int, delta: int = 1, notify: bool = True) -> bytes:
    """Setup port input format [0x41]"""
    payload = bytes([
        0x00, 0x41, port_id & 0xFF, mode & 0xFF,
        delta & 0xFF, 0x00, 0x00, 0x00,  # delta as int32
        1 if notify else 0
    ])
    return bytes([len(payload) + 1]) + payload


class TrainHubGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LEGO Train Hub Control Center")
        self.root.geometry("900x800")
        self.root.configure(bg='#2b2b2b')
        
        # Connection state
        self.connection: Optional[BLEConnection] = None
        self.connected = False
        self.command_queue = queue.Queue()
        self.loop = None
        self.async_thread = None
        
        # Control variables
        self.port_var = tk.IntVar(value=0)
        self.speed_var = tk.IntVar(value=0)
        self.power_var = tk.IntVar(value=0)
        self.max_power_var = tk.IntVar(value=100)
        self.time_var = tk.IntVar(value=2000)
        self.degrees_var = tk.IntVar(value=360)
        self.acc_time_var = tk.IntVar(value=1000)
        self.dec_time_var = tk.IntVar(value=1000)
        self.use_profile_var = tk.BooleanVar(value=False)
        self.end_state_var = tk.StringVar(value="Brake")
        self.led_color_var = tk.IntVar(value=0)
        
        # Debug variables
        self.debug_enabled = tk.BooleanVar(value=True)
        self.log_rx = tk.BooleanVar(value=True)
        self.log_tx = tk.BooleanVar(value=True)
        self.received_messages = []
        
        self.create_widgets()
        
    def create_widgets(self):
        # Title
        title_frame = tk.Frame(self.root, bg='#1e1e1e', pady=10)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="🚂 LEGO Train Hub Control Center", 
                font=('Arial', 18, 'bold'), bg='#1e1e1e', fg='#ffffff').pack()
        
        # Connection Frame
        conn_frame = tk.LabelFrame(self.root, text="Connection", bg='#2b2b2b', fg='#ffffff', 
                                   font=('Arial', 10, 'bold'), pady=10)
        conn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.connect_btn = tk.Button(conn_frame, text="Connect to Train Base", 
                                     command=self.connect_hub, bg='#4CAF50', fg='white',
                                     font=('Arial', 10, 'bold'), padx=20, pady=5)
        self.connect_btn.pack(side=tk.LEFT, padx=10)
        
        self.disconnect_btn = tk.Button(conn_frame, text="Disconnect", 
                                       command=self.disconnect_hub, bg='#f44336', fg='white',
                                       font=('Arial', 10, 'bold'), padx=20, pady=5, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=10)
        
        self.status_label = tk.Label(conn_frame, text="Status: Not Connected", 
                                     bg='#2b2b2b', fg='#ff9800', font=('Arial', 10))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Style for notebook
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background='#2b2b2b', borderwidth=0)
        style.configure('TNotebook.Tab', background='#3c3c3c', foreground='white', 
                       padding=[20, 10], font=('Arial', 9, 'bold'))
        style.map('TNotebook.Tab', background=[('selected', '#1e88e5')], 
                 foreground=[('selected', 'white')])
        
        # Tab 1: Basic Motor Control
        tab1 = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tab1, text="Basic Motor Control")
        self.create_basic_motor_tab(tab1)
        
        # Tab 2: Advanced Motor Control
        tab2 = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tab2, text="Advanced Motor Control")
        self.create_advanced_motor_tab(tab2)
        
        # Tab 3: Hub Control
        tab3 = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tab3, text="Hub Control")
        self.create_hub_control_tab(tab3)
        
        # Tab 4: Profiles & Settings
        tab4 = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tab4, text="Profiles & Settings")
        self.create_profiles_tab(tab4)
        
        # Tab 5: Debug & Diagnostics
        tab5 = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tab5, text="Debug & Diagnostics")
        self.create_debug_tab(tab5)
        
    def create_basic_motor_tab(self, parent):
        # Port Selection
        port_frame = tk.LabelFrame(parent, text="Port Selection", bg='#2b2b2b', fg='#ffffff',
                                   font=('Arial', 10, 'bold'), pady=10)
        port_frame.pack(fill=tk.X, padx=10, pady=5)
        
        for i, port_name in enumerate(["Port 0 (Motor A)", "Port 1 (Motor B)", "Port 2 (Motor C)"]):
            tk.Radiobutton(port_frame, text=port_name, variable=self.port_var, value=i,
                          bg='#2b2b2b', fg='#ffffff', selectcolor='#1e88e5',
                          font=('Arial', 9), activebackground='#2b2b2b',
                          activeforeground='#ffffff').pack(side=tk.LEFT, padx=20)
        
        # Speed Control
        speed_frame = tk.LabelFrame(parent, text="Speed Control (Regulated)", bg='#2b2b2b', 
                                   fg='#ffffff', font=('Arial', 10, 'bold'), pady=10)
        speed_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(speed_frame, text="Speed: -100 to 100", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).pack()
        
        speed_slider = tk.Scale(speed_frame, from_=-100, to=100, orient=tk.HORIZONTAL,
                               variable=self.speed_var, bg='#3c3c3c', fg='#ffffff',
                               highlightthickness=0, length=400, troughcolor='#1e88e5')
        speed_slider.pack(pady=5)
        
        speed_value_label = tk.Label(speed_frame, textvariable=self.speed_var, 
                                     bg='#2b2b2b', fg='#4CAF50', font=('Arial', 14, 'bold'))
        speed_value_label.pack()
        
        btn_frame = tk.Frame(speed_frame, bg='#2b2b2b')
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Start Speed", command=self.start_speed,
                 bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Stop Motor", command=self.stop_motor,
                 bg='#f44336', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Quick Speed Buttons
        quick_frame = tk.Frame(speed_frame, bg='#2b2b2b')
        quick_frame.pack(pady=5)
        
        for speed in [-100, -50, 0, 50, 100]:
            tk.Button(quick_frame, text=f"{speed:+d}", 
                     command=lambda s=speed: self.set_quick_speed(s),
                     bg='#607D8B', fg='white', font=('Arial', 9), padx=10, pady=3).pack(side=tk.LEFT, padx=3)
        
        # Power Control (Unregulated)
        power_frame = tk.LabelFrame(parent, text="Power Control (Unregulated)", bg='#2b2b2b',
                                   fg='#ffffff', font=('Arial', 10, 'bold'), pady=10)
        power_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(power_frame, text="Power: -100 to 100", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).pack()
        
        power_slider = tk.Scale(power_frame, from_=-100, to=100, orient=tk.HORIZONTAL,
                               variable=self.power_var, bg='#3c3c3c', fg='#ffffff',
                               highlightthickness=0, length=400, troughcolor='#ff9800')
        power_slider.pack(pady=5)
        
        tk.Button(power_frame, text="Apply Power", command=self.start_power,
                 bg='#ff9800', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).pack(pady=5)
        
    def create_advanced_motor_tab(self, parent):
        # Timed Movement
        timed_frame = tk.LabelFrame(parent, text="Timed Movement", bg='#2b2b2b', fg='#ffffff',
                                   font=('Arial', 10, 'bold'), pady=10)
        timed_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(timed_frame, text="Duration (ms):", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).grid(row=0, column=0, padx=10, pady=5, sticky='w')
        tk.Scale(timed_frame, from_=100, to=10000, orient=tk.HORIZONTAL,
                variable=self.time_var, bg='#3c3c3c', fg='#ffffff',
                highlightthickness=0, length=300).grid(row=0, column=1, padx=10, pady=5)
        tk.Label(timed_frame, textvariable=self.time_var, bg='#2b2b2b', fg='#4CAF50',
                font=('Arial', 10, 'bold')).grid(row=0, column=2, padx=10, pady=5)
        
        tk.Label(timed_frame, text="Speed:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).grid(row=1, column=0, padx=10, pady=5, sticky='w')
        tk.Label(timed_frame, textvariable=self.speed_var, bg='#2b2b2b', fg='#4CAF50',
                font=('Arial', 10, 'bold')).grid(row=1, column=1, padx=10, pady=5, sticky='w')
        
        tk.Button(timed_frame, text="Run for Time", command=self.start_speed_for_time,
                 bg='#2196F3', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).grid(row=2, column=1, pady=10)
        
        # Degree-based Movement
        degree_frame = tk.LabelFrame(parent, text="Degree-based Movement", bg='#2b2b2b', fg='#ffffff',
                                    font=('Arial', 10, 'bold'), pady=10)
        degree_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(degree_frame, text="Degrees:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).grid(row=0, column=0, padx=10, pady=5, sticky='w')
        tk.Scale(degree_frame, from_=0, to=3600, orient=tk.HORIZONTAL,
                variable=self.degrees_var, bg='#3c3c3c', fg='#ffffff',
                highlightthickness=0, length=300).grid(row=0, column=1, padx=10, pady=5)
        tk.Label(degree_frame, textvariable=self.degrees_var, bg='#2b2b2b', fg='#4CAF50',
                font=('Arial', 10, 'bold')).grid(row=0, column=2, padx=10, pady=5)
        
        tk.Label(degree_frame, text="Speed:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).grid(row=1, column=0, padx=10, pady=5, sticky='w')
        tk.Label(degree_frame, textvariable=self.speed_var, bg='#2b2b2b', fg='#4CAF50',
                font=('Arial', 10, 'bold')).grid(row=1, column=1, padx=10, pady=5, sticky='w')
        
        tk.Button(degree_frame, text="Run for Degrees", command=self.start_speed_for_degrees,
                 bg='#9C27B0', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).grid(row=2, column=1, pady=10)
        
        # Max Power & End State
        settings_frame = tk.LabelFrame(parent, text="Movement Settings", bg='#2b2b2b', fg='#ffffff',
                                      font=('Arial', 10, 'bold'), pady=10)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(settings_frame, text="Max Power (%):", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).grid(row=0, column=0, padx=10, pady=5, sticky='w')
        tk.Scale(settings_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                variable=self.max_power_var, bg='#3c3c3c', fg='#ffffff',
                highlightthickness=0, length=300).grid(row=0, column=1, padx=10, pady=5)
        tk.Label(settings_frame, textvariable=self.max_power_var, bg='#2b2b2b', fg='#4CAF50',
                font=('Arial', 10, 'bold')).grid(row=0, column=2, padx=10, pady=5)
        
        tk.Label(settings_frame, text="End State:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).grid(row=1, column=0, padx=10, pady=5, sticky='w')
        
        end_state_frame = tk.Frame(settings_frame, bg='#2b2b2b')
        end_state_frame.grid(row=1, column=1, padx=10, pady=5, sticky='w')
        
        for state in ["Float", "Hold", "Brake"]:
            tk.Radiobutton(end_state_frame, text=state, variable=self.end_state_var, value=state,
                          bg='#2b2b2b', fg='#ffffff', selectcolor='#1e88e5',
                          font=('Arial', 9), activebackground='#2b2b2b',
                          activeforeground='#ffffff').pack(side=tk.LEFT, padx=10)
        
    def create_hub_control_tab(self, parent):
        # Hub LED Control
        led_frame = tk.LabelFrame(parent, text="Hub LED Color", bg='#2b2b2b', fg='#ffffff',
                                 font=('Arial', 10, 'bold'), pady=10)
        led_frame.pack(fill=tk.X, padx=10, pady=5)
        
        colors = [
            ("Off", 0), ("Pink", 1), ("Purple", 2), ("Blue", 3),
            ("Light Blue", 4), ("Cyan", 5), ("Green", 6), ("Yellow", 7),
            ("Orange", 8), ("Red", 9), ("White", 10)
        ]
        
        color_grid = tk.Frame(led_frame, bg='#2b2b2b')
        color_grid.pack(pady=10)
        
        for idx, (name, value) in enumerate(colors):
            row = idx // 4
            col = idx % 4
            tk.Button(color_grid, text=name, command=lambda v=value: self.set_led_color(v),
                     bg='#607D8B', fg='white', font=('Arial', 9), padx=10, pady=5,
                     width=12).grid(row=row, column=col, padx=5, pady=5)
        
        # Hub Actions
        action_frame = tk.LabelFrame(parent, text="Hub Actions", bg='#2b2b2b', fg='#ffffff',
                                    font=('Arial', 10, 'bold'), pady=10)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(action_frame, text="⚠️ Warning: These actions will affect hub connection",
                bg='#2b2b2b', fg='#ff9800', font=('Arial', 9, 'italic')).pack(pady=5)
        
        action_btn_frame = tk.Frame(action_frame, bg='#2b2b2b')
        action_btn_frame.pack(pady=10)
        
        tk.Button(action_btn_frame, text="Shutdown Hub", command=self.shutdown_hub,
                 bg='#f44336', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).pack(side=tk.LEFT, padx=10)
        tk.Button(action_btn_frame, text="Disconnect Hub", command=self.hub_disconnect_action,
                 bg='#ff9800', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).pack(side=tk.LEFT, padx=10)
        
        # Emergency Stop
        emergency_frame = tk.LabelFrame(parent, text="Emergency Controls", bg='#2b2b2b', fg='#ffffff',
                                       font=('Arial', 10, 'bold'), pady=10)
        emergency_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(emergency_frame, text="🛑 EMERGENCY STOP ALL", command=self.emergency_stop,
                 bg='#d32f2f', fg='white', font=('Arial', 14, 'bold'), padx=30, pady=15).pack(pady=10)
        
    def create_profiles_tab(self, parent):
        # Acceleration Profile
        acc_frame = tk.LabelFrame(parent, text="Acceleration Profile", bg='#2b2b2b', fg='#ffffff',
                                 font=('Arial', 10, 'bold'), pady=10)
        acc_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(acc_frame, text="Acceleration Time (ms):", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).grid(row=0, column=0, padx=10, pady=5, sticky='w')
        tk.Scale(acc_frame, from_=0, to=10000, orient=tk.HORIZONTAL,
                variable=self.acc_time_var, bg='#3c3c3c', fg='#ffffff',
                highlightthickness=0, length=300).grid(row=0, column=1, padx=10, pady=5)
        tk.Label(acc_frame, textvariable=self.acc_time_var, bg='#2b2b2b', fg='#4CAF50',
                font=('Arial', 10, 'bold')).grid(row=0, column=2, padx=10, pady=5)
        
        tk.Button(acc_frame, text="Set Acceleration Profile", command=self.set_acc_profile,
                 bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).grid(row=1, column=1, pady=10)
        
        # Deceleration Profile
        dec_frame = tk.LabelFrame(parent, text="Deceleration Profile", bg='#2b2b2b', fg='#ffffff',
                                 font=('Arial', 10, 'bold'), pady=10)
        dec_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(dec_frame, text="Deceleration Time (ms):", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).grid(row=0, column=0, padx=10, pady=5, sticky='w')
        tk.Scale(dec_frame, from_=0, to=10000, orient=tk.HORIZONTAL,
                variable=self.dec_time_var, bg='#3c3c3c', fg='#ffffff',
                highlightthickness=0, length=300).grid(row=0, column=1, padx=10, pady=5)
        tk.Label(dec_frame, textvariable=self.dec_time_var, bg='#2b2b2b', fg='#4CAF50',
                font=('Arial', 10, 'bold')).grid(row=0, column=2, padx=10, pady=5)
        
        tk.Button(dec_frame, text="Set Deceleration Profile", command=self.set_dec_profile,
                 bg='#ff9800', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).grid(row=1, column=1, pady=10)
        
        # Use Profile Toggle
        profile_frame = tk.LabelFrame(parent, text="Profile Usage", bg='#2b2b2b', fg='#ffffff',
                                     font=('Arial', 10, 'bold'), pady=10)
        profile_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Checkbutton(profile_frame, text="Use Acceleration/Deceleration Profiles",
                      variable=self.use_profile_var, bg='#2b2b2b', fg='#ffffff',
                      selectcolor='#1e88e5', font=('Arial', 10),
                      activebackground='#2b2b2b', activeforeground='#ffffff').pack(pady=10)
        
        tk.Label(profile_frame, text="When enabled, motor commands will use the configured profiles\nfor smooth acceleration and deceleration.",
                bg='#2b2b2b', fg='#9e9e9e', font=('Arial', 9, 'italic')).pack(pady=5)
    
    def create_debug_tab(self, parent):
        # Debug Console
        console_frame = tk.LabelFrame(parent, text="Debug Console", bg='#2b2b2b', fg='#ffffff',
                                     font=('Arial', 10, 'bold'), pady=5)
        console_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Console text area
        self.debug_console = scrolledtext.ScrolledText(console_frame, height=15, bg='#1e1e1e',
                                                       fg='#00ff00', font=('Consolas', 9),
                                                       wrap=tk.WORD)
        self.debug_console.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Console controls
        console_ctrl_frame = tk.Frame(console_frame, bg='#2b2b2b')
        console_ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(console_ctrl_frame, text="Clear Console", command=self.clear_console,
                 bg='#607D8B', fg='white', font=('Arial', 9), padx=10, pady=3).pack(side=tk.LEFT, padx=5)
        
        tk.Checkbutton(console_ctrl_frame, text="Log RX", variable=self.log_rx,
                      bg='#2b2b2b', fg='#ffffff', selectcolor='#1e88e5',
                      font=('Arial', 9)).pack(side=tk.LEFT, padx=10)
        
        tk.Checkbutton(console_ctrl_frame, text="Log TX", variable=self.log_tx,
                      bg='#2b2b2b', fg='#ffffff', selectcolor='#1e88e5',
                      font=('Arial', 9)).pack(side=tk.LEFT, padx=10)
        
        # Diagnostic Tools
        diag_frame = tk.LabelFrame(parent, text="Diagnostic Tools", bg='#2b2b2b', fg='#ffffff',
                                  font=('Arial', 10, 'bold'), pady=10)
        diag_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Port detection
        port_detect_frame = tk.Frame(diag_frame, bg='#2b2b2b')
        port_detect_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(port_detect_frame, text="Port Detection:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        
        tk.Button(port_detect_frame, text="Scan All Ports", command=self.scan_all_ports,
                 bg='#2196F3', fg='white', font=('Arial', 9), padx=10, pady=3).pack(side=tk.LEFT, padx=5)
        
        tk.Button(port_detect_frame, text="Request Port Info", command=self.request_port_info,
                 bg='#9C27B0', fg='white', font=('Arial', 9), padx=10, pady=3).pack(side=tk.LEFT, padx=5)
        
        # Test commands
        test_frame = tk.Frame(diag_frame, bg='#2b2b2b')
        test_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(test_frame, text="Test Commands:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        
        tk.Button(test_frame, text="Test WriteDirectMode", command=self.test_write_direct,
                 bg='#ff9800', fg='white', font=('Arial', 9), padx=10, pady=3).pack(side=tk.LEFT, padx=5)
        
        tk.Button(test_frame, text="Test All Ports", command=self.test_all_ports,
                 bg='#4CAF50', fg='white', font=('Arial', 9), padx=10, pady=3).pack(side=tk.LEFT, padx=5)
        
        # Raw command sender
        raw_frame = tk.LabelFrame(parent, text="Raw Command Sender", bg='#2b2b2b', fg='#ffffff',
                                 font=('Arial', 10, 'bold'), pady=10)
        raw_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(raw_frame, text="Hex bytes (space separated):", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).pack(anchor='w', padx=10, pady=5)
        
        self.raw_cmd_entry = tk.Entry(raw_frame, bg='#3c3c3c', fg='#ffffff',
                                      font=('Consolas', 10), width=60)
        self.raw_cmd_entry.pack(fill=tk.X, padx=10, pady=5)
        self.raw_cmd_entry.insert(0, "09 00 81 00 11 07 32 64 00")
        
        tk.Button(raw_frame, text="Send Raw Command", command=self.send_raw_command,
                 bg='#f44336', fg='white', font=('Arial', 9, 'bold'), padx=15, pady=5).pack(pady=5)
        
        # Info display
        info_frame = tk.LabelFrame(parent, text="Connection Info", bg='#2b2b2b', fg='#ffffff',
                                  font=('Arial', 10, 'bold'), pady=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.info_text = tk.Text(info_frame, height=4, bg='#1e1e1e', fg='#ffffff',
                                font=('Consolas', 9), wrap=tk.WORD)
        self.info_text.pack(fill=tk.X, padx=10, pady=5)
        self.info_text.insert('1.0', 'Not connected')
        self.info_text.config(state=tk.DISABLED)
        
        self.log_debug("Debug console initialized")
        
    # Connection Methods
    def connect_hub(self):
        self.status_label.config(text="Status: Connecting...", fg='#ff9800')
        self.connect_btn.config(state=tk.DISABLED)
        
        # Start async connection in separate thread
        self.async_thread = Thread(target=self.async_connect_worker, daemon=True)
        self.async_thread.start()
        
    def async_connect_worker(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.async_connect())
            # Keep loop running for commands
            self.loop.run_until_complete(self.command_processor())
        except Exception as e:
            self.root.after(0, lambda: self.connection_failed(str(e)))
        finally:
            if self.loop:
                self.loop.close()
    
    async def async_connect(self):
        try:
            # Scan for device
            device = None
            for attempt in range(3):
                try:
                    device = await find_device(name=TARGET_NAME, service=LWP3_SERVICE_UUID, timeout=10.0)
                    break
                except asyncio.TimeoutError:
                    if attempt == 2:
                        # Fallback to Bleak
                        from bleak import BleakScanner
                        devices = await BleakScanner.discover(timeout=8.0)
                        for d in devices:
                            if getattr(d, 'name', None) == TARGET_NAME:
                                device = d
                                break
            
            if device is None:
                raise Exception("Could not find Train Base")
            
            # Connect
            self.connection = BLEConnection(
                char_rx_UUID=LWP3_CHAR_UUID,
                char_tx_UUID=LWP3_CHAR_UUID,
                max_data_size=20,
            )
            await self.connection.connect(device)
            
            # Set up data handler
            def log_data(sender, data: bytes):
                self.received_messages.append(data)
                if self.log_rx.get():
                    self.log_debug(f"RX: {data.hex()} | {self.decode_message(data)}")
            self.connection.data_handler = log_data
            
            self.connected = True
            self.root.after(0, self.connection_success)
            
        except Exception as e:
            raise e
    
    async def command_processor(self):
        """Process commands from the queue"""
        while self.connected:
            try:
                # Check for commands with timeout
                try:
                    cmd = self.command_queue.get(timeout=0.1)
                    if cmd is None:  # Shutdown signal
                        break
                    await self.connection.write(cmd)
                except queue.Empty:
                    pass
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"Command error: {e}")
    
    def connection_success(self):
        self.status_label.config(text="Status: Connected ✓", fg='#4CAF50')
        self.connect_btn.config(state=tk.DISABLED)
        self.disconnect_btn.config(state=tk.NORMAL)
        self.log_debug("✓ Successfully connected to Train Base")
        self.update_connection_info()
        messagebox.showinfo("Success", "Connected to Train Base!")
    
    def connection_failed(self, error):
        self.status_label.config(text="Status: Connection Failed", fg='#f44336')
        self.connect_btn.config(state=tk.NORMAL)
        messagebox.showerror("Connection Error", f"Failed to connect:\n{error}")
    
    def disconnect_hub(self):
        if self.connected:
            self.connected = False
            self.command_queue.put(None)  # Signal shutdown
            
            # Schedule async disconnect
            if self.loop:
                asyncio.run_coroutine_threadsafe(self.async_disconnect(), self.loop)
            
            self.status_label.config(text="Status: Disconnected", fg='#ff9800')
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
    
    async def async_disconnect(self):
        if self.connection:
            try:
                await self.connection.disconnect()
            except:
                pass
    
    # Command Methods
    def send_command(self, cmd: bytes, description: str = ""):
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to Train Base first!")
            return
        if self.log_tx.get():
            desc = f" ({description})" if description else ""
            self.log_debug(f"TX: {cmd.hex()}{desc}")
        self.command_queue.put(cmd)
    
    def get_end_state_value(self) -> int:
        state_map = {"Float": 0, "Hold": 126, "Brake": 127}
        return state_map[self.end_state_var.get()]
    
    def start_speed(self):
        port = self.port_var.get()
        speed = self.speed_var.get()
        cmd = make_start_speed(
            port,
            speed,
            self.max_power_var.get(),
            1 if self.use_profile_var.get() else 0
        )
        self.send_command(cmd, f"StartSpeed port={port} speed={speed}")
    
    def stop_motor(self):
        port = self.port_var.get()
        cmd = make_start_speed(port, 0, 100, 0)
        self.send_command(cmd, f"Stop port={port}")
    
    def set_quick_speed(self, speed):
        self.speed_var.set(speed)
        self.start_speed()
    
    def start_power(self):
        port = self.port_var.get()
        power = self.power_var.get()
        cmd = make_start_power(port, power)
        self.send_command(cmd, f"StartPower port={port} power={power}")
    
    def start_speed_for_time(self):
        cmd = make_start_speed_for_time(
            self.port_var.get(),
            self.time_var.get(),
            self.speed_var.get(),
            self.max_power_var.get(),
            self.get_end_state_value(),
            1 if self.use_profile_var.get() else 0
        )
        self.send_command(cmd)
    
    def start_speed_for_degrees(self):
        cmd = make_start_speed_for_degrees(
            self.port_var.get(),
            self.degrees_var.get(),
            self.speed_var.get(),
            self.max_power_var.get(),
            self.get_end_state_value(),
            1 if self.use_profile_var.get() else 0
        )
        self.send_command(cmd)
    
    def set_acc_profile(self):
        cmd = make_set_acc_time(self.port_var.get(), self.acc_time_var.get(), 0)
        self.send_command(cmd)
        messagebox.showinfo("Profile Set", f"Acceleration profile set to {self.acc_time_var.get()}ms")
    
    def set_dec_profile(self):
        cmd = make_set_dec_time(self.port_var.get(), self.dec_time_var.get(), 0)
        self.send_command(cmd)
        messagebox.showinfo("Profile Set", f"Deceleration profile set to {self.dec_time_var.get()}ms")
    
    def set_led_color(self, color):
        cmd = make_hub_led_color(color)
        self.send_command(cmd)
    
    def shutdown_hub(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to shutdown the hub?"):
            cmd = make_hub_action(0x2F)
            self.send_command(cmd)
            self.disconnect_hub()
    
    def hub_disconnect_action(self):
        cmd = make_hub_action(0x02)
        self.send_command(cmd)
        self.disconnect_hub()
    
    def emergency_stop(self):
        # Stop all ports
        self.log_debug("🛑 EMERGENCY STOP - Stopping all ports")
        for port in [0, 1, 2]:
            cmd = make_start_speed(port, 0, 100, 0)
            self.send_command(cmd, f"Emergency stop port={port}")
        messagebox.showinfo("Emergency Stop", "All motors stopped!")
    
    # Debug Methods
    def log_debug(self, message: str):
        """Log message to debug console"""
        if not self.debug_enabled.get():
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_msg = f"[{timestamp}] {message}\n"
        
        # Update console in main thread
        self.root.after(0, self._append_to_console, log_msg)
    
    def _append_to_console(self, message: str):
        """Append message to console (must be called from main thread)"""
        self.debug_console.config(state=tk.NORMAL)
        self.debug_console.insert(tk.END, message)
        self.debug_console.see(tk.END)
        self.debug_console.config(state=tk.DISABLED)
    
    def clear_console(self):
        """Clear debug console"""
        self.debug_console.config(state=tk.NORMAL)
        self.debug_console.delete('1.0', tk.END)
        self.debug_console.config(state=tk.DISABLED)
        self.log_debug("Console cleared")
    
    def decode_message(self, data: bytes) -> str:
        """Decode LWP3 message for display"""
        if len(data) < 3:
            return "Invalid"
        
        length = data[0]
        hub_id = data[1]
        msg_type = data[2]
        
        msg_types = {
            0x01: "HUB_PROPERTIES",
            0x02: "HUB_ACTIONS",
            0x03: "HUB_ALERTS",
            0x04: "HUB_ATTACHED_IO",
            0x05: "GENERIC_ERROR",
            0x21: "PORT_INFO",
            0x43: "PORT_VALUE",
            0x44: "PORT_VALUE_COMBINED",
            0x45: "PORT_INPUT_FORMAT",
            0x47: "PORT_INPUT_FORMAT_COMBINED",
            0x81: "PORT_OUTPUT_CMD",
            0x82: "PORT_OUTPUT_CMD_FEEDBACK",
        }
        
        msg_name = msg_types.get(msg_type, f"UNKNOWN(0x{msg_type:02X})")
        
        if msg_type == 0x04 and len(data) >= 5:  # HUB_ATTACHED_IO
            port = data[3]
            event = data[4]
            events = {0: "DETACHED", 1: "ATTACHED", 2: "ATTACHED_VIRTUAL"}
            event_name = events.get(event, f"0x{event:02X}")
            if event == 1 and len(data) >= 7:
                io_type = (data[6] << 8) | data[5]
                return f"{msg_name} Port={port} Event={event_name} IOType=0x{io_type:04X}"
            return f"{msg_name} Port={port} Event={event_name}"
        
        elif msg_type == 0x82 and len(data) >= 5:  # PORT_OUTPUT_CMD_FEEDBACK
            port = data[3]
            feedback = data[4]
            feedback_names = {
                0x01: "BUFFER_EMPTY_CMD_IN_PROGRESS",
                0x02: "BUFFER_EMPTY_CMD_COMPLETED",
                0x04: "CURRENT_CMD_DISCARDED",
                0x08: "IDLE",
                0x10: "BUSY_FULL"
            }
            fb_name = feedback_names.get(feedback, f"0x{feedback:02X}")
            return f"{msg_name} Port={port} Feedback={fb_name}"
        
        return msg_name
    
    def update_connection_info(self):
        """Update connection info display"""
        if self.connection:
            info = f"Connected: Yes\n"
            info += f"Target: {TARGET_NAME}\n"
            info += f"Service UUID: {LWP3_SERVICE_UUID}\n"
            info += f"Char UUID: {LWP3_CHAR_UUID}"
            
            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete('1.0', tk.END)
            self.info_text.insert('1.0', info)
            self.info_text.config(state=tk.DISABLED)
    
    def scan_all_ports(self):
        """Scan all ports for attached devices"""
        self.log_debug("Scanning all ports for attached devices...")
        for port in range(0, 10):  # Scan ports 0-9
            cmd = make_port_info_request(port, 0x00)  # Request port value
            self.send_command(cmd, f"Port info request port={port}")
    
    def request_port_info(self):
        """Request info for selected port"""
        port = self.port_var.get()
        self.log_debug(f"Requesting info for port {port}...")
        # Request different info types
        for info_type in [0x00, 0x01, 0x02]:  # Mode info, combinations, etc.
            cmd = make_port_info_request(port, info_type)
            self.send_command(cmd, f"Port info type={info_type} port={port}")
    
    def test_write_direct(self):
        """Test WriteDirectModeData command"""
        port = self.port_var.get()
        self.log_debug(f"Testing WriteDirectModeData on port {port}...")
        
        # Try mode 0 with speed 50
        cmd = make_write_direct_mode_data(port, 0x00, 50)
        self.send_command(cmd, f"WriteDirectMode port={port} mode=0 data=50")
        
        self.root.after(2000, lambda: self.send_command(
            make_write_direct_mode_data(port, 0x00, 0),
            f"WriteDirectMode port={port} mode=0 data=0 (stop)"
        ))
    
    def test_all_ports(self):
        """Test all ports sequentially"""
        self.log_debug("Testing all ports sequentially...")
        
        for port in [0, 1, 2]:
            # Test with WriteDirectModeData
            self.log_debug(f"Testing port {port} with WriteDirectModeData...")
            delay = port * 3000
            
            self.root.after(delay, lambda p=port: self.send_command(
                make_write_direct_mode_data(p, 0x00, 50),
                f"Test port={p} WriteDirectMode speed=50"
            ))
            
            self.root.after(delay + 1500, lambda p=port: self.send_command(
                make_write_direct_mode_data(p, 0x00, 0),
                f"Test port={p} WriteDirectMode speed=0"
            ))
    
    def send_raw_command(self):
        """Send raw hex command"""
        try:
            hex_str = self.raw_cmd_entry.get().strip()
            hex_bytes = hex_str.replace(' ', '').replace('0x', '')
            cmd = bytes.fromhex(hex_bytes)
            self.log_debug(f"Sending raw command: {cmd.hex()}")
            self.send_command(cmd, "Raw command")
        except Exception as e:
            self.log_debug(f"ERROR: Invalid hex format - {e}")
            messagebox.showerror("Invalid Format", f"Invalid hex format:\n{e}")


def main():
    root = tk.Tk()
    app = TrainHubGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
