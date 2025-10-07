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



def make_write_direct_mode_data(port_id: int, mode: int, *data: int) -> bytes:
    """WriteDirectModeData command [0x51]"""
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x51,
        mode & 0xFF,
    ] + [b & 0xFF for b in data])
    return bytes([len(payload) + 1]) + payload

def make_hub_led_color(color: int) -> bytes:
    """Set Hub LED color using WriteDirectModeData to port 50 (hub LED)"""
    # Port 50 (0x32) is the hub LED port
    # Mode 0 is the color mode
    payload = bytes([
        0x00, 0x81, 0x32, 0x11, 0x51,
        0x00, color & 0xFF
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
        self.speed_var = tk.IntVar(value=0)
        self.time_var = tk.IntVar(value=2000)
        self.degrees_var = tk.IntVar(value=360)
        self.end_state_var = tk.StringVar(value="Brake")
        self.led_color_var = tk.IntVar(value=0)
        self.use_direct_mode = tk.BooleanVar(value=True)  # Use WriteDirectModeData by default
        
        # Color sensor variables
        self.color_sensor_port = tk.IntVar(value=0x12)  # Default to port 0x12 (18) for Train Base color sensor
        self.current_color = tk.StringVar(value="Unknown")
        self.current_color_value = tk.IntVar(value=-1)
        self.color_sensor_enabled = False
        self.color_sensor_mode = tk.IntVar(value=0)  # 0=Color Index, 3=RGB
        self._color_last_rx_ms = 0  # timestamp of last color RX (ms)
        self._color_auto_fallback_pending = False
        
        # Color stabilization/debouncing
        self._color_history = []  # Store recent color readings
        self._color_history_max = 5  # Number of readings to average
        self._last_stable_color = -1  # Last confirmed stable color
        self._color_stability_threshold = 3  # Minimum occurrences to confirm color
        
        # Debug variables
        self.debug_enabled = tk.BooleanVar(value=True)
        self.log_rx = tk.BooleanVar(value=True)
        self.log_tx = tk.BooleanVar(value=True)
        self.received_messages = []
        self.working_ports = set()  # Track which ports have working motors
        
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
        
        # Tab 2: Hub Control
        tab2 = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tab2, text="Hub Control")
        self.create_hub_control_tab(tab2)
        
        # Tab 3: Color Sensor
        tab3 = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tab3, text="Color Sensor")
        self.create_color_sensor_tab(tab3)
        
        # Tab 4: Debug & Diagnostics
        tab4 = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tab4, text="Debug & Diagnostics")
        self.create_debug_tab(tab4)
        
    def create_basic_motor_tab(self, parent):
        # Info label
        info_frame = tk.Frame(parent, bg='#2b2b2b', pady=5)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(info_frame, text="Controlling Port 0 (Motor)", 
                bg='#2b2b2b', fg='#4CAF50', font=('Arial', 10, 'bold')).pack()
        
        # Instant Speed Control
        instant_frame = tk.LabelFrame(parent, text="Instant Speed Control", bg='#2b2b2b', 
                                     fg='#ffffff', font=('Arial', 10, 'bold'), pady=10)
        instant_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(instant_frame, text="Speed: -100 to 100 (changes instantly, skips -30 to +30)", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).pack()
        
        # Create instant speed variable
        self.instant_speed_var = tk.IntVar(value=0)
        
        instant_slider = tk.Scale(instant_frame, from_=-100, to=100, orient=tk.HORIZONTAL,
                                 variable=self.instant_speed_var, bg='#3c3c3c', fg='#ffffff',
                                 highlightthickness=0, length=400, troughcolor='#1e88e5',
                                 command=self.on_instant_speed_change, resolution=1)
        instant_slider.pack(pady=5)
        
        instant_value_label = tk.Label(instant_frame, textvariable=self.instant_speed_var, 
                                       bg='#2b2b2b', fg='#4CAF50', font=('Arial', 14, 'bold'))
        instant_value_label.pack()
        
        # Stop button
        tk.Button(instant_frame, text="Stop", command=self.stop_instant_speed,
                 bg='#f44336', fg='white', font=('Arial', 10, 'bold'), padx=30, pady=5).pack(pady=5)
        
        # Speed Control with Button
        speed_frame = tk.LabelFrame(parent, text="Speed Control (with Button)", bg='#2b2b2b', 
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
        
        tk.Button(test_frame, text="Check RX Handler", command=self.check_rx_handler,
                 bg='#f44336', fg='white', font=('Arial', 9), padx=10, pady=3).pack(side=tk.LEFT, padx=5)
        
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
    
    def create_color_sensor_tab(self, parent):
        # Info label
        info_frame = tk.Frame(parent, bg='#2b2b2b', pady=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(info_frame, text="🎨 Color Sensor Reader", 
                bg='#2b2b2b', fg='#4CAF50', font=('Arial', 14, 'bold')).pack()
        tk.Label(info_frame, text="Read color values from the Train Hub color sensor", 
                bg='#2b2b2b', fg='#ffffff', font=('Arial', 9)).pack()
        
        # Port selection
        port_frame = tk.LabelFrame(parent, text="Sensor Configuration", bg='#2b2b2b', 
                                   fg='#ffffff', font=('Arial', 10, 'bold'), pady=10)
        port_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(port_frame, text="Color Sensor Port:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
        
        # Port 0x12 (18) is the built-in color sensor on Train Base
        port_options = [("Built-in (0x12)", 0x12), ("Port 0", 0), ("Port 1", 1), ("Port 2", 2)]
        for label, port in port_options:
            tk.Radiobutton(port_frame, text=label, variable=self.color_sensor_port,
                          value=port, bg='#2b2b2b', fg='#ffffff', selectcolor='#1e88e5',
                          font=('Arial', 9), activebackground='#2b2b2b',
                          activeforeground='#ffffff').pack(side=tk.LEFT, padx=5)
        
        # Mode selection
        mode_frame = tk.Frame(port_frame, bg='#2b2b2b')
        mode_frame.pack(pady=5)
        tk.Label(mode_frame, text="Mode:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(mode_frame, text="Color Index (0-10)", variable=self.color_sensor_mode,
                      value=0, bg='#2b2b2b', fg='#ffffff', selectcolor='#1e88e5',
                      font=('Arial', 9), activebackground='#2b2b2b',
                      activeforeground='#ffffff').pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(mode_frame, text="RGB Values", variable=self.color_sensor_mode,
                      value=3, bg='#2b2b2b', fg='#ffffff', selectcolor='#1e88e5',
                      font=('Arial', 9), activebackground='#2b2b2b',
                      activeforeground='#ffffff').pack(side=tk.LEFT, padx=5)
        
        # Stabilization settings
        stab_frame = tk.LabelFrame(port_frame, text="Stabilization (reduces flickering)", 
                                   bg='#2b2b2b', fg='#ffffff', font=('Arial', 9))
        stab_frame.pack(pady=5, padx=10, fill=tk.X)
        
        tk.Label(stab_frame, text="Sensitivity:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 9)).pack(side=tk.LEFT, padx=5)
        
        # Sensitivity presets
        tk.Button(stab_frame, text="High (Fast)", 
                 command=lambda: self._set_stabilization(2, 3),
                 bg='#607D8B', fg='white', font=('Arial', 8), padx=5, pady=2).pack(side=tk.LEFT, padx=2)
        tk.Button(stab_frame, text="Medium (Default)", 
                 command=lambda: self._set_stabilization(3, 5),
                 bg='#607D8B', fg='white', font=('Arial', 8), padx=5, pady=2).pack(side=tk.LEFT, padx=2)
        tk.Button(stab_frame, text="Low (Stable)", 
                 command=lambda: self._set_stabilization(4, 7),
                 bg='#607D8B', fg='white', font=('Arial', 8), padx=5, pady=2).pack(side=tk.LEFT, padx=2)
        
        # Control buttons
        btn_frame = tk.Frame(port_frame, bg='#2b2b2b')
        btn_frame.pack(pady=10)
        
        self.enable_color_btn = tk.Button(btn_frame, text="Enable Color Sensor", 
                                         command=self.enable_color_sensor,
                                         bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'),
                                         padx=20, pady=5)
        self.enable_color_btn.pack(side=tk.LEFT, padx=5)
        
        self.disable_color_btn = tk.Button(btn_frame, text="Disable Color Sensor", 
                                          command=self.disable_color_sensor,
                                          bg='#f44336', fg='white', font=('Arial', 10, 'bold'),
                                          padx=20, pady=5, state=tk.DISABLED)
        self.disable_color_btn.pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Test Color Sensor", 
                 command=self.test_color_sensor,
                 bg='#2196F3', fg='white', font=('Arial', 10, 'bold'),
                 padx=20, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Scan All Ports for Sensor", 
                 command=self.scan_all_ports_for_sensor,
                 bg='#9C27B0', fg='white', font=('Arial', 10, 'bold'),
                 padx=20, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Color display
        display_frame = tk.LabelFrame(parent, text="Current Color Reading", bg='#2b2b2b',
                                     fg='#ffffff', font=('Arial', 10, 'bold'), pady=20)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Large color display box
        self.color_display = tk.Frame(display_frame, bg='#1e1e1e', width=300, height=200,
                                     relief=tk.RAISED, borderwidth=3)
        self.color_display.pack(pady=20)
        self.color_display.pack_propagate(False)
        
        self.color_name_label = tk.Label(self.color_display, textvariable=self.current_color,
                                        bg='#1e1e1e', fg='#ffffff', font=('Arial', 24, 'bold'))
        self.color_name_label.pack(expand=True)
        
        # Color value display
        value_frame = tk.Frame(display_frame, bg='#2b2b2b')
        value_frame.pack(pady=10)
        
        tk.Label(value_frame, text="Raw Value:", bg='#2b2b2b', fg='#ffffff',
                font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.color_value_label = tk.Label(value_frame, textvariable=self.current_color_value, bg='#2b2b2b',
                fg='#4CAF50', font=('Arial', 14, 'bold'))
        self.color_value_label.pack(side=tk.LEFT, padx=5)
        
        # Status indicator
        self.color_status_label = tk.Label(value_frame, text="● Inactive", bg='#2b2b2b',
                                          fg='#888888', font=('Arial', 10))
        self.color_status_label.pack(side=tk.LEFT, padx=20)
        
        # Color legend
        legend_frame = tk.LabelFrame(parent, text="Color Values Reference", bg='#2b2b2b',
                                    fg='#ffffff', font=('Arial', 10, 'bold'), pady=10)
        legend_frame.pack(fill=tk.X, padx=10, pady=5)
        
        colors_info = [
            ("0: Black", "#000000"), ("1: Pink", "#FF69B4"), ("2: Purple", "#800080"),
            ("3: Blue", "#0000FF"), ("4: Light Blue", "#87CEEB"), ("5: Cyan", "#00FFFF"),
            ("6: Green", "#00FF00"), ("7: Yellow", "#FFFF00"), ("8: Orange", "#FFA500"),
            ("9: Red", "#FF0000"), ("10: White", "#FFFFFF")
        ]
        
        legend_grid = tk.Frame(legend_frame, bg='#2b2b2b')
        legend_grid.pack(pady=5)
        
        for idx, (text, color) in enumerate(colors_info):
            row = idx // 4
            col = idx % 4
            frame = tk.Frame(legend_grid, bg='#2b2b2b')
            frame.grid(row=row, column=col, padx=5, pady=3)
            
            color_box = tk.Label(frame, bg=color, width=2, height=1, relief=tk.RAISED)
            color_box.pack(side=tk.LEFT, padx=2)
            
            tk.Label(frame, text=text, bg='#2b2b2b', fg='#ffffff',
                    font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        
    # Connection Methods
    def connect_hub(self):
        self.status_label.config(text="Status: Connecting...", fg='#ff9800')
        self.connect_btn.config(state=tk.DISABLED)
        
        # Start async connection in separate thread
        self.async_thread = Thread(target=self.async_connect_worker, daemon=True)
        self.async_thread.start()
        
    def async_connect_worker(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            # First connect
            self.loop.run_until_complete(self.async_connect())
            # Then keep loop running for commands
            self.loop.run_until_complete(self.command_processor())
        except asyncio.CancelledError:
            # Normal cancellation during shutdown
            pass
        except Exception as ex:
            error_msg = str(ex)
            self.root.after(0, lambda msg=error_msg: self.connection_failed(msg))
        finally:
            # Clean up
            try:
                if self.loop and not self.loop.is_closed():
                    # Cancel all pending tasks
                    pending = asyncio.all_tasks(self.loop)
                    for task in pending:
                        task.cancel()
                    # Give tasks a chance to finish
                    if pending:
                        self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    self.loop.close()
            except:
                pass
    
    async def async_connect(self):
        try:
            self.log_debug("Starting connection process...")
            
            # Scan for device
            device = None
            for attempt in range(3):
                try:
                    self.log_debug(f"Scan attempt {attempt + 1}/3...")
                    device = await find_device(name=TARGET_NAME, service=LWP3_SERVICE_UUID, timeout=10.0)
                    self.log_debug(f"Found device: {device}")
                    break
                except asyncio.TimeoutError:
                    self.log_debug(f"Scan attempt {attempt + 1} timed out")
                    if attempt == 2:
                        # Fallback to Bleak
                        self.log_debug("Trying Bleak fallback...")
                        from bleak import BleakScanner
                        devices = await BleakScanner.discover(timeout=8.0)
                        for d in devices:
                            if getattr(d, 'name', None) == TARGET_NAME:
                                device = d
                                self.log_debug(f"Found via Bleak: {device}")
                                break
            
            if device is None:
                raise Exception("Could not find Train Base")
            
            # Connect
            self.log_debug("Creating BLE connection...")
            self.connection = BLEConnection(
                char_rx_UUID=LWP3_CHAR_UUID,
                char_tx_UUID=LWP3_CHAR_UUID,
                max_data_size=20,
            )
            
            self.log_debug("Connecting to device...")
            await self.connection.connect(device)
            self.log_debug("BLE connection established!")
            
            # Give the connection a moment to stabilize
            await asyncio.sleep(0.2)
            
            # Set up data handler
            def log_data(sender, data: bytes):
                self.received_messages.append(data)
                # Always log ALL incoming messages when color sensor is enabled for debugging
                if self.log_rx.get() or self.color_sensor_enabled:
                    self.log_debug(f"RX: {data.hex()} | {self.decode_message(data)}")
                # Parse color sensor data
                self.parse_color_sensor_data(data)
            
            # CRITICAL: Ensure data handler is set BEFORE any other operations
            self.connection.data_handler = log_data
            self.log_debug("✓ Data handler installed")
            
            # Check if BLE client has notifications enabled
            try:
                if hasattr(self.connection, 'client'):
                    self.log_debug(f"BLE Client: {self.connection.client}")
                    self.log_debug(f"Connected: {self.connection.client.is_connected}")
                    # Try to manually enable notifications if not already enabled
                    try:
                        await self.connection.client.start_notify(LWP3_CHAR_UUID, log_data)
                        self.log_debug("✓ Manually enabled BLE notifications")
                    except Exception as e:
                        self.log_debug(f"Note: Could not manually enable notifications (may already be enabled): {e}")
            except Exception as e:
                self.log_debug(f"Could not access BLE client: {e}")
            
            # Test if we can receive data by requesting hub properties
            self.log_debug("Testing RX by requesting hub name...")
            test_cmd = bytes([0x05, 0x00, 0x01, 0x01, 0x05])  # Request hub name
            await self.connection.write(test_cmd)
            await asyncio.sleep(0.5)  # Wait for response
            
            if len(self.received_messages) == 0:
                self.log_debug("⚠ WARNING: No response to hub name request!")
                self.log_debug("⚠ BLE notifications may not be enabled properly!")
                self.log_debug("⚠ The hub is connected but not sending data back!")
                self.log_debug("⚠ This is a known issue with some pybricksdev versions.")
            else:
                self.log_debug(f"✓ RX working! Received {len(self.received_messages)} messages")
            
            self.connected = True
            self.root.after(0, self.connection_success)
            
        except Exception as e:
            self.log_debug(f"Connection error: {e}")
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
        
        # Auto-scan ports on connection
        self.log_debug("Auto-scanning for attached devices...")
        self.root.after(500, self.auto_detect_ports)
        
        messagebox.showinfo("Success", "Connected to Train Base!\nCheck Debug tab for port detection.")
    
    def connection_failed(self, error):
        self.status_label.config(text="Status: Connection Failed", fg='#f44336')
        self.connect_btn.config(state=tk.NORMAL)
        messagebox.showerror("Connection Error", f"Failed to connect:\n{error}")
    
    def disconnect_hub(self):
        if self.connected:
            self.connected = False
            self.command_queue.put(None)  # Signal shutdown
            
            # Schedule async disconnect
            if self.loop and not self.loop.is_closed():
                try:
                    asyncio.run_coroutine_threadsafe(self.async_disconnect(), self.loop)
                except:
                    pass
            
            self.status_label.config(text="Status: Disconnected", fg='#ff9800')
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
    
    async def async_disconnect(self):
        if self.connection:
            try:
                await self.connection.disconnect()
                await asyncio.sleep(0.1)  # Give time for cleanup
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
        port = 0  # Always use port 0
        speed = self.speed_var.get()
        
        if self.use_direct_mode.get():
            # Use WriteDirectModeData (works better for train motors)
            cmd = make_write_direct_mode_data(port, 0x00, speed if speed >= 0 else (speed + 256))
            self.send_command(cmd, f"WriteDirectMode port={port} speed={speed}")
        else:
            # Use StartSpeed (for Technic motors)
            cmd = make_start_speed(
                port,
                speed,
                100,  # max_power always 100
                0  # use_profile always 0
            )
            self.send_command(cmd, f"StartSpeed port={port} speed={speed}")
    
    def stop_motor(self):
        port = 0  # Always use port 0
        if self.use_direct_mode.get():
            cmd = make_write_direct_mode_data(port, 0x00, 0)
            self.send_command(cmd, f"WriteDirectMode stop port={port}")
        else:
            cmd = make_start_speed(port, 0, 100, 0)
            self.send_command(cmd, f"Stop port={port}")
    
    def set_quick_speed(self, speed):
        self.speed_var.set(speed)
        self.start_speed()
    
    def on_instant_speed_change(self, value):
        """Called when instant speed slider changes"""
        speed = int(value)
        
        # Skip the dead zone (-30 to +30), except for 0
        if -30 < speed < 30 and speed != 0:
            # Snap to nearest boundary
            if speed > 0:
                speed = 30
            else:
                speed = -30
            self.instant_speed_var.set(speed)
            return
        
        port = 0  # Always use port 0
        
        if self.connected:
            # Send the speed command (including 0 for stop)
            if self.use_direct_mode.get():
                cmd = make_write_direct_mode_data(port, 0x00, speed if speed >= 0 else (speed + 256))
                self.send_command(cmd, f"Instant speed={speed}")
            else:
                cmd = make_start_speed(port, speed, 100, 0)
                self.send_command(cmd, f"Instant speed={speed}")
    
    def stop_instant_speed(self):
        """Stop motor and reset instant speed slider to 0"""
        port = 0  # Always use port 0
        
        # Explicitly send stop command
        if self.connected:
            if self.use_direct_mode.get():
                cmd = make_write_direct_mode_data(port, 0x00, 0)
                self.send_command(cmd, f"Stop (instant speed)")
            else:
                cmd = make_start_speed(port, 0, 100, 0)
                self.send_command(cmd, f"Stop (instant speed)")
        
        # Reset slider to 0
        self.instant_speed_var.set(0)
    
    
    def set_led_color(self, color):
        cmd = make_hub_led_color(color)
        self.send_command(cmd, f"Set LED color={color}")
    
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
            0x45: "PORT_VALUE_SINGLE",  # This is PORT_VALUE (Single), not PORT_INPUT_FORMAT
            0x47: "PORT_INPUT_FORMAT",
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
                return f"{msg_name} Port=0x{port:02X} ({port}) Event={event_name} IOType=0x{io_type:04X}"
            return f"{msg_name} Port=0x{port:02X} ({port}) Event={event_name}"
        
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
        
        elif msg_type == 0x45 and len(data) >= 5:  # PORT_VALUE (not PORT_INPUT_FORMAT)
            port = data[3]
            if len(data) >= 5:
                value = data[4]
                return f"{msg_name} Port=0x{port:02X} Value={value}"
        
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
        """Request info for port 0"""
        port = 0  # Always use port 0
        self.log_debug(f"Requesting info for port {port}...")
        # Request different info types
        for info_type in [0x00, 0x01, 0x02]:  # Mode info, combinations, etc.
            cmd = make_port_info_request(port, info_type)
            self.send_command(cmd, f"Port info type={info_type} port={port}")
    
    def test_write_direct(self):
        """Test WriteDirectModeData command"""
        port = 0  # Always use port 0
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
        self.log_debug("Watch your train - note which ports make it move!")
        self.working_ports.clear()
        
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
        
        # After all tests, prompt user to mark working ports
        self.root.after(10000, self.prompt_working_ports)
    
    def prompt_working_ports(self):
        """Ask user which ports worked"""
        result = messagebox.askquestion(
            "Port Test Complete",
            "Did you see the motor move?\n\n"
            "Based on typical Train Base setup:\n"
            "• Port 0 and Port 2 usually have motors\n"
            "• Port 1 is often unused or has a different device\n\n"
            "Mark Port 0 and Port 2 as working?",
            icon='question'
        )
        
        if result == 'yes':
            self.working_ports = {0, 2}
            self.update_port_status()
            self.log_debug("✓ Marked Port 0 and Port 2 as working")
            messagebox.showinfo("Success", "Port 0 and Port 2 marked as working!\nUse these ports for motor control.")
    
    def update_port_status(self):
        """Update port status indicators (no-op since port selection removed)"""
        pass
    
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
    
    def auto_detect_ports(self):
        """Auto-detect ports on connection"""
        self.log_debug("=" * 60)
        self.log_debug("AUTOMATIC PORT DETECTION")
        self.log_debug("=" * 60)
        self.log_debug("Waiting for HUB_ATTACHED_IO messages...")
        self.log_debug("These messages show which ports have motors/sensors attached.")
        self.log_debug("")
        self.log_debug("Train Base built-in devices:")
        self.log_debug("  - Port 0x00 (0): Motor A")
        self.log_debug("  - Port 0x01 (1): Motor B")
        self.log_debug("  - Port 0x12 (18): Color Sensor")
        self.log_debug("  - Port 0x13 (19): Speedometer")
        self.log_debug("")
        self.log_debug("If no messages appear, the hub may not send them automatically.")
        self.log_debug("Try clicking 'Scan All Ports' or 'Test All Ports' buttons.")
        self.log_debug("=" * 60)
    
    def check_rx_handler(self):
        """Check if RX handler is working"""
        self.log_debug("=" * 60)
        self.log_debug("RX HANDLER DIAGNOSTICS")
        self.log_debug("=" * 60)
        self.log_debug(f"Connection object: {self.connection}")
        self.log_debug(f"Connected status: {self.connected}")
        self.log_debug(f"Received messages count: {len(self.received_messages)}")
        self.log_debug(f"Log RX enabled: {self.log_rx.get()}")
        
        if len(self.received_messages) > 0:
            self.log_debug(f"\n✓ RX handler IS working! Received {len(self.received_messages)} messages:")
            for i, msg in enumerate(self.received_messages[-5:]):  # Show last 5
                self.log_debug(f"  [{i}] {msg.hex()} - {self.decode_message(msg)}")
        else:
            self.log_debug("\n⚠ WARNING: No messages received from hub!")
            self.log_debug("This could mean:")
            self.log_debug("  1. Hub is not sending feedback (normal for some commands)")
            self.log_debug("  2. RX notifications are not enabled")
            self.log_debug("  3. Connection issue")
            self.log_debug("\nTrying to request hub properties to trigger response...")
            
            # Request hub name (should trigger a response)
            cmd = bytes([0x05, 0x00, 0x01, 0x01, 0x05])  # Request hub name
            self.send_command(cmd, "Request hub name (diagnostic)")
            
            self.log_debug("Sent hub name request. Watch for RX messages above.")
        
        self.log_debug("=" * 60)
    
    def enable_color_sensor(self):
        """Enable color sensor notifications"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to Train Base first!")
            return
        
        port = self.color_sensor_port.get()
        mode = self.color_sensor_mode.get()
        self.log_debug(f"Enabling color sensor on port 0x{port:02X} ({port}) with mode {mode}...")
        
        # Mode 0 = Color Index (0-10), Mode 3 = RGB values
        # Delta = 1 means notify on any change
        cmd = make_port_input_format_setup(port, mode=mode, delta=1, notify=True)
        self.log_debug(f"Sending PORT_INPUT_FORMAT_SETUP command: {cmd.hex()}")
        self.log_debug(f"  Expected format: [length, 0x00, 0x41, port, mode, delta(4 bytes), notify]")
        self.send_command(cmd, f"Enable color sensor port=0x{port:02X} mode={mode}")
        
        self.color_sensor_enabled = True
        self.enable_color_btn.config(state=tk.DISABLED)
        self.disable_color_btn.config(state=tk.NORMAL)
        self.current_color.set("Waiting for data...")
        self.current_color_value.set(-1)
        try:
            self.color_status_label.config(text="● Listening", fg="#ff9800")
        except Exception:
            pass

        mode_name = "Color Index" if mode == 0 else "RGB"
        self.log_debug(f"✓ Color sensor enabled on port 0x{port:02X} ({port}) in {mode_name} mode")
        self.log_debug("Place colored objects in front of the sensor to see readings.")
        # Auto-fallback: if no data within 2 seconds, switch mode and retry
        self.root.after(2000, self._color_auto_fallback_check)
    
    def disable_color_sensor(self):
        """Disable color sensor notifications"""
        if not self.connected:
            return
        
        port = self.color_sensor_port.get()
        mode = self.color_sensor_mode.get()
        self.log_debug(f"Disabling color sensor on port 0x{port:02X} ({port})...")
        
        # Set notify to False to disable notifications
        cmd = make_port_input_format_setup(port, mode=mode, delta=1, notify=False)
        self.send_command(cmd, f"Disable color sensor port=0x{port:02X}")
        
        self.color_sensor_enabled = False
        self.enable_color_btn.config(state=tk.NORMAL)
        self.disable_color_btn.config(state=tk.DISABLED)
        self.current_color.set("Disabled")
        self.current_color_value.set(-1)
        self.color_display.config(bg='#1e1e1e')
        self.color_name_label.config(bg='#1e1e1e')
        
        try:
            self.color_status_label.config(text="● Inactive", fg="#888888")
        except Exception:
            pass
        
        self.log_debug(f"✓ Color sensor disabled on port 0x{port:02X} ({port})")

    def _color_auto_fallback_check(self):
        """Switch mode automatically if no data was received shortly after enabling."""
        if not (self.connected and self.color_sensor_enabled):
            return
        if self.current_color_value.get() == -1:
            cur = self.color_sensor_mode.get()
            alt = 3 if cur == 0 else 0
            self.log_debug(f"No color data yet. Auto-switching mode {cur} -> {alt} and retrying...")
            self.color_sensor_mode.set(alt)
            self.enable_color_sensor()
    
    def scan_all_ports_for_sensor(self):
        """Try to enable color sensor on all possible ports to find the right one"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to Train Base first!")
            return
        
        self.log_debug("=" * 60)
        self.log_debug("SCANNING ALL PORTS FOR COLOR SENSOR")
        self.log_debug("=" * 60)
        self.log_debug("This will try to enable color sensor notifications on multiple ports.")
        self.log_debug("Watch for PORT_VALUE messages to identify the correct port.")
        self.log_debug("")
        
        # Try common ports for Train Base
        test_ports = [0x00, 0x01, 0x02, 0x03, 0x12, 0x13, 0x32, 0x3B, 0x3C]
        
        for i, port in enumerate(test_ports):
            delay = i * 500  # 500ms between each attempt
            self.root.after(delay, lambda p=port: self._try_enable_port(p))
        
        self.log_debug(f"Will test {len(test_ports)} ports: {', '.join(f'0x{p:02X}' for p in test_ports)}")
        self.log_debug("=" * 60)
    
    def _try_enable_port(self, port: int):
        """Helper to try enabling a specific port"""
        self.log_debug(f"\n>>> Trying port 0x{port:02X} ({port})...")
        cmd = make_port_input_format_setup(port, mode=0, delta=1, notify=True)
        self.send_command(cmd, f"Test enable color sensor port=0x{port:02X}")
    
    def test_color_sensor(self):
        """Test color sensor by requesting port info and checking for data"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to Train Base first!")
            return
        
        port = self.color_sensor_port.get()
        self.log_debug("=" * 60)
        self.log_debug(f"COLOR SENSOR TEST - Port 0x{port:02X} ({port})")
        self.log_debug("=" * 60)
        
        # First, scan for all attached devices
        self.log_debug("Step 1: Scanning for all attached devices...")
        self.log_debug("Looking for HUB_ATTACHED_IO (0x04) messages...")
        self.log_debug("These show which ports have devices attached.")
        
        # Request port information
        self.log_debug(f"\nStep 2: Requesting port info for port 0x{port:02X}...")
        for info_type in [0x00, 0x01, 0x02]:
            cmd = make_port_info_request(port, info_type)
            self.send_command(cmd, f"Port info request type={info_type}")
        
        # Try alternate ports if 0x12 doesn't work
        self.log_debug(f"\nStep 3: Trying alternate common color sensor ports...")
        for alt_port in [0x00, 0x01, 0x02, 0x03, 0x12, 0x13]:
            if alt_port != port:
                cmd = make_port_info_request(alt_port, 0x00)
                self.send_command(cmd, f"Port info request port=0x{alt_port:02X}")
        
        # Try to enable the sensor
        self.log_debug(f"\nStep 4: Enabling color sensor on port 0x{port:02X}...")
        self.root.after(2000, self.enable_color_sensor)
        
        self.log_debug(f"\nStep 5: Watch for PORT_VALUE_SINGLE (0x45) or PORT_VALUE (0x43) messages above.")
        self.log_debug(f"Expected port: 0x{port:02X} ({port})")
        self.log_debug("If you see messages for a DIFFERENT port, update the port selection!")
        self.log_debug("=" * 60)
    
    def parse_color_sensor_data(self, data: bytes):
        """Parse incoming color sensor data from PORT_VALUE messages"""
        if len(data) < 3:
            return
        
        msg_type = data[2]
        
        # Accept 0x45 (PORT_VALUE_SINGLE), 0x43 (PORT_VALUE), and 0x47 (PORT_INPUT_FORMAT_SINGLE)
        if msg_type in (0x43, 0x45, 0x47):
            if len(data) < 4:
                return
            port = data[3]
            
            # Log all PORT_VALUE messages for debugging (always log to help diagnose issues)
            self.log_debug(f"PORT_VALUE msg_type=0x{msg_type:02X}: port=0x{port:02X} ({port}), len={len(data)}, data={data.hex()}")
            
            # Check if this is from our color sensor port
            if self.color_sensor_enabled and port == self.color_sensor_port.get():
                mode = self.color_sensor_mode.get()
                self.log_debug(f"✓ Color sensor data received! Mode={mode}, Length={len(data)}, Full data: {' '.join(f'{b:02X}' for b in data)}")
                
                # Update timestamp for auto-fallback check
                import time
                self._color_last_rx_ms = int(time.time() * 1000)
                
                try:
                    self.color_status_label.config(text="● Live", fg="#4CAF50")
                except Exception:
                    pass
                
                if mode == 0:  # Color Index mode
                    color_value = None
                    # Train Base sends 5-byte messages: [05, 00, 45, port, color_value]
                    # Color value is at byte 4 (last byte)
                    if len(data) >= 5:
                        potential_value = data[4]
                        # Check if it's a valid color (0-10) or 0xFF (no color)
                        if 0 <= potential_value <= 10:
                            color_value = potential_value
                            self.log_debug(f"Parsed color index from byte 4 (Train Base format): {color_value}")
                        elif potential_value == 0xFF:
                            self.log_debug(f"No color detected (value=0xFF)")
                            # Don't update display for 0xFF
                            color_value = None
                        else:
                            # Try byte 6 for Mario/other hubs (7+ byte messages)
                            if len(data) >= 7 and 0 <= data[6] <= 10:
                                color_value = data[6]
                                self.log_debug(f"Parsed color index from byte 6 (Mario format): {color_value}")
                            else:
                                self.log_debug(f"Unknown color value at byte 4: {potential_value}")
                    
                    if color_value is not None:
                        # Apply stabilization filter
                        stable_color = self._stabilize_color(color_value)
                        if stable_color is not None:
                            self.log_debug(f"✓ Stable Color Index: {stable_color}")
                            self.root.after(0, lambda v=stable_color: self.update_color_display(v))
                    else:
                        if len(data) >= 5:
                            self.log_debug(f"⚠ Could not parse color from data: {data.hex()}")
                        
                elif mode == 3:  # RGB mode
                    red = green = blue = None
                    # Common layout for RGB: 16-bit LE per channel
                    # Format: [length, hub_id, msg_type, port, R_low, R_high, G_low, G_high, B_low, B_high]
                    if len(data) >= 10:
                        red = data[4] | (data[5] << 8)
                        green = data[6] | (data[7] << 8)
                        blue = data[8] | (data[9] << 8)
                        # Scale down from 10-bit (0-1023) to 8-bit (0-255)
                        red = min(255, red // 4)
                        green = min(255, green // 4)
                        blue = min(255, blue // 4)
                        self.log_debug(f"Parsed RGB (16-bit LE): R={red}, G={green}, B={blue}")
                    # Packed 8-bit RGB at bytes 4,5,6
                    elif len(data) >= 7:
                        red, green, blue = data[4], data[5], data[6]
                        self.log_debug(f"Parsed RGB (8-bit): R={red}, G={green}, B={blue}")
                    
                    if None not in (red, green, blue):
                        self.log_debug(f"✓ RGB: R={red}, G={green}, B={blue}")
                        self.root.after(0, lambda r=red, g=green, b=blue: self.update_rgb_display(r, g, b))
                    else:
                        self.log_debug(f"⚠ Could not parse RGB from payload")
    
    def _set_stabilization(self, threshold: int, history_max: int):
        """Update stabilization parameters"""
        self._color_stability_threshold = threshold
        self._color_history_max = history_max
        self._color_history.clear()  # Reset history when changing settings
        self._last_stable_color = -1
        self.log_debug(f"Stabilization updated: threshold={threshold}, history={history_max}")
    
    def _stabilize_color(self, color_value: int) -> int:
        """
        Stabilize color readings by requiring multiple consistent readings.
        This filters out rapid fluctuations and noise.
        Returns the stable color value, or None if not yet stable.
        """
        # Add to history
        self._color_history.append(color_value)
        
        # Keep only recent readings
        if len(self._color_history) > self._color_history_max:
            self._color_history.pop(0)
        
        # Need enough samples
        if len(self._color_history) < self._color_stability_threshold:
            return None
        
        # Count occurrences of each color in recent history
        from collections import Counter
        color_counts = Counter(self._color_history)
        
        # Get most common color and its count
        most_common_color, count = color_counts.most_common(1)[0]
        
        # Only update if we have enough consistent readings
        if count >= self._color_stability_threshold:
            # Only return if it's different from last stable color (avoid redundant updates)
            if most_common_color != self._last_stable_color:
                self._last_stable_color = most_common_color
                return most_common_color
        
        return None
    
    def update_color_display(self, color_value: int):
        """Update the color display with the detected color"""
        color_names = {
            0: ("Black", "#000000", "#FFFFFF"),
            1: ("Pink", "#FF69B4", "#000000"),
            2: ("Purple", "#800080", "#FFFFFF"),
            3: ("Blue", "#0000FF", "#FFFFFF"),
            4: ("Light Blue", "#87CEEB", "#000000"),
            5: ("Cyan", "#00FFFF", "#000000"),
            6: ("Green", "#00FF00", "#000000"),
            7: ("Yellow", "#FFFF00", "#000000"),
            8: ("Orange", "#FFA500", "#000000"),
            9: ("Red", "#FF0000", "#FFFFFF"),
            10: ("White", "#FFFFFF", "#000000"),
        }
        
        if color_value in color_names:
            name, bg_color, fg_color = color_names[color_value]
            self.current_color.set(name)
            self.current_color_value.set(color_value)
            self.color_display.config(bg=bg_color)
            self.color_name_label.config(bg=bg_color, fg=fg_color)
        else:
            self.current_color.set(f"Unknown ({color_value})")
            self.current_color_value.set(color_value)
            self.color_display.config(bg='#1e1e1e')
            self.color_name_label.config(bg='#1e1e1e', fg='#ffffff')
    
    def update_rgb_display(self, red: int, green: int, blue: int):
        """Update the color display with RGB values"""
        # Convert RGB to hex color
        hex_color = f"#{red:02x}{green:02x}{blue:02x}"
        
        # Calculate brightness to determine text color
        brightness = (red * 299 + green * 587 + blue * 114) / 1000
        text_color = "#000000" if brightness > 128 else "#FFFFFF"
        
        self.current_color.set(f"RGB: {red},{green},{blue}")
        self.current_color_value.set(red)  # Show red value as primary
        self.color_display.config(bg=hex_color)
        self.color_name_label.config(bg=hex_color, fg=text_color)


def main():
    root = tk.Tk()
    app = TrainHubGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
