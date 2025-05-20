import tkinter as tk
from threading import Lock
from tkinter import ttk, messagebox
import threading
from queue import Queue
from PIL import Image, ImageTk
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import cv2
import requests
import time
import socketio
sio = socketio.Client()
frame_queue = Queue()
stop_event = threading.Event()
stream_thread = None
STREAM_WIDTH = 640
STREAM_HEIGHT = 640
overlay_visible = False
INITIAL_BG = 'gray25'
detection_counts = {}
current_chart = None
person_overlay_label = None
def on_connect():
    connection_label.config(fg="green")
    print("🟢 Connected to server")
    toggle_controls(True)

    try:
        # Checkboxes
        sio.emit('set_auto_movement', {'enabled': auto_move_var.get()})
        sio.emit('toggle_debug', {'enabled': debug_var.get()})

        # Brightness (convert 0-200 scale to 0.0-2.0)
        brightness_value = float(brightness_slider.get()) / 100
        sio.emit('set_brightness', {'value': brightness_value})

        # Numeric inputs
        sio.emit('set_tolerance', {'value': int(tolerance_entry.get())})
        sio.emit('set_speed', {'value': int(car_speed_entry.get())})
        sio.emit('set_modifier', {'value': int(modifier_entry.get())})
        sio.emit('set_max_speed', {'value': int(max_speed_entry.get())})
        sio.emit('set_min_speed', {'value': int(min_speed_entry.get())})
        sio.emit('set_mode', {'mode': mode_var.get()})

    except Exception as e:
        print(f"Error sending initial values: {str(e)}")

@sio.on('disconnect')
def on_disconnect():
    connection_label.config(fg="red")
    print("🔴 Disconnected")
    toggle_controls(False)
    sio.disconnect()

sio.on('connect', on_connect)
sio.on('disconnect', on_disconnect)

def on_detection(data):
    show_message(data['msg'])

def on_mode_ack(data):
    print("Mode is now:", data['mode'])

def on_control_ack(data):
    print("Control state:", data['state'])

sio.on('detection', on_detection)
sio.on('mode_ack', on_mode_ack)
sio.on('control_ack', on_control_ack)


def on_mode_change():
    if not sio.connected:
        return

    mode = mode_var.get()
    try:
        sio.emit('set_mode', {'mode': mode})
        joystick.set_enabled(mode == 'manual')
    except Exception as e:
        messagebox.showerror("Mode Error", f"Failed to set mode: {str(e)}")

def update_pie_chart():
    global current_chart
    for widget in chart_frame.winfo_children():
        widget.destroy()

    fig = Figure(figsize=(8, 6), dpi=100)
    ax = fig.add_subplot(111)

    if detection_counts:
        labels = [label.replace('_', ' ').title() for label in detection_counts.keys()]
        sizes = list(detection_counts.values())

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct=lambda pct: f'{pct:.1f}%' if pct > 5 else '',
            startangle=90,
            pctdistance=0.85,
            labeldistance=1.05,
            textprops={'fontsize': 10}
        )

        ax.legend(
            wedges,
            labels,
            title="Objects",
            loc="center left",
            bbox_to_anchor=(1, 0, 0.5, 1),
            fontsize=9
        )
        ax.set_title('Object Detection Distribution', pad=20, fontweight='bold')
        ax.axis('equal')
    else:
        ax.text(0.5, 0.5, 'No detections yet',
                horizontalalignment='center',
                verticalalignment='center',
                fontsize=12)
        ax.axis('off')
    fig.subplots_adjust(left=0.1, right=0.7)

    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    current_chart = canvas
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    toolbar = NavigationToolbar2Tk(canvas, chart_frame)
    toolbar.update()
    canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

detection_lock = Lock()
LAST_UPDATE_TIME = 0
UPDATE_INTERVAL = 1

DETECTION_IMAGE_DURATION = 2000
current_image_label = None
IMAGE_SIZE = (200, 200)


def show_detection_image(obj_type):
    global current_image_label

    if current_image_label:
        current_image_label.destroy()

    try:
        img_path = f"images/{obj_type.lower()}.png"
        img = Image.open(img_path)
        img = img.resize(IMAGE_SIZE, Image.LANCZOS)
        photo_img = ImageTk.PhotoImage(img)
        current_image_label = tk.Label(
            center_frame,
            image=photo_img,
            borderwidth=0,
            bg=INITIAL_BG
        )
        current_image_label.image = photo_img
        current_image_label.place(
            relx=0.5,
            rely=0.5,
            anchor=tk.CENTER
        )

        # Schedule image removal
        root.after(DETECTION_IMAGE_DURATION, current_image_label.destroy)
    except Exception as e:
        print(f"Couldn't load image for {obj_type}: {str(e)}")
def show_message(message):
    global detection_counts

    print(f"[DEBUG] Raw message received: {message}")

    with detection_lock:
        try:
            if isinstance(message, str) and message.strip():
                obj_type = message.strip().lower()
                print(f"[DEBUG] Processing valid message: '{obj_type}'")

                detection_counts[obj_type] = detection_counts.get(obj_type, 0) + 1
                show_detection_image(obj_type)
                print(f"[DEBUG] Updated counts - {obj_type}: {detection_counts[obj_type]}")
            else:
                print(f"[DEBUG] Ignoring invalid message: {message}")
        except Exception as e:
            print(f"[ERROR] Message processing failed: {str(e)}")
    periodic_chart_update()

def get_messages():
    try:
        response = requests.get('http://localhost:5000/receive', timeout=1)
        new_messages = response.json().get('messages', [])
        return new_messages[-1] if new_messages else None
    except Exception:
        return None

def message_worker():
    while not stop_event.is_set():
        try:
            response = requests.get('http://localhost:5000/receive', timeout=1)
            if response.status_code == 204:
                time.sleep(1)
                continue

            response.raise_for_status()
            new_messages = response.json().get('messages', [])
            print(f"[NETWORK] Received {len(new_messages)} messages: {new_messages}")

            for msg in new_messages:
                show_message(msg)

        except requests.exceptions.RequestException as e:
            print(f"[NETWORK] Connection error: {e}")
        time.sleep(1)

def hide_overlay():
    global overlay_visible, person_overlay_label
    overlay_visible = False
    if person_overlay_label:
        person_overlay_label.destroy()
        person_overlay_label = None
initial=True
def connect_to_server(show_error=True):
    try:
        if not sio.connected:
            sio.connect('http://localhost:5000', wait_timeout=5)
            toggle_controls(True)
            return True
    except Exception as e:
        toggle_controls(False)
        if show_error:
            messagebox.showerror("Connection Error", f"Server connection failed: {str(e)}")
        return False
    return True


def toggle_controls(connected):
    state = 'normal' if connected else 'disabled'

    joystick_control_frame.winfo_children()[0].config(state=state)
    joystick_control_frame.winfo_children()[1].config(state=state)
    joystick.set_enabled(connected and mode_var.get() == 'manual')
    if state=='normal':
        connection_label.config(fg="green")
    else:
        connection_label.config(fg="red")

    for widget in [stop_btn, debug_btn]:
        widget.config(state=state)

    entry.config(state=state)
def stop_stream():
    sio.emit('control_cmd', {'state': 'stop'})
    stop_event.set()
    video_label.config(image='', bg=INITIAL_BG, text='Stream Stopped',
                       fg='white', font=('Arial', 20))


def periodic_chart_update():
    global LAST_UPDATE_TIME
    now = time.time()
    if (now - LAST_UPDATE_TIME) >= UPDATE_INTERVAL and detection_counts:
        update_pie_chart()
        LAST_UPDATE_TIME = now

    root.after(5000, periodic_chart_update)
from PIL import Image

def start_debug_stream():
    global stream_thread
    stop_event.set()
    stop_event.clear()
    stream_thread = threading.Thread(target=play_debug_stream, daemon=True)
    stream_thread.start()
    video_label.config(text='', bg=INITIAL_BG)
    root.after(10, update_label)

def play_debug_stream():
    global stop_event
    stop_event.clear()
    stream_url = "http://localhost:4956"
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        messagebox.showerror("Stream Error", "Failed to open debug stream")
        return
    sio.emit('control_cmd', {'state': 'start'})
    on_connect()
    video_label.config(bg=INITIAL_BG)
    while cap.isOpened() and not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT))
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        imgtk = ImageTk.PhotoImage(image=img)
        frame_queue.put(imgtk)
    cap.release()
    stop_event.set()
def check_connection():
    if not sio.connected:
        connect_to_server(show_error=False)
def update_label():
    last_imgtk = None
    while not frame_queue.empty():
        last_imgtk = frame_queue.get()
    if last_imgtk is not None:
        video_label.imgtk = last_imgtk
        video_label.config(image=last_imgtk)
    if not stop_event.is_set():
        root.after(10, update_label)


def create_numeric_input(parent, label, min_val, max_val, default_val, command):
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Label(frame, text=label).pack(side=tk.LEFT)

    validate_cmd = (frame.register(lambda p: p.replace('.', '', 1).isdigit() or p == ""), '%P')

    entry = ttk.Entry(
        frame,
        width=5,
        validate='key',
        validatecommand=validate_cmd
    )
    entry.pack(side=tk.LEFT, padx=5)
    entry.insert(0, str(default_val))

    ttk.Label(frame, text=f"({min_val:.1f}-{max_val:.1f})").pack(side=tk.LEFT)

    def update_value(*args):
        try:
            value = float(entry.get())  # Changed to float
            clamped = max(min_val, min(value, max_val))
            if value != clamped:
                entry.delete(0, tk.END)
                entry.insert(0, f"{clamped:.2f}")
            command(clamped)
        except ValueError:
            pass

    entry.bind("<FocusOut>", lambda e: update_value())
    entry.bind("<Return>", lambda e: update_value())

    return entry
from joystick import Joystick
# ---------------- GUI Setup ----------------
if __name__ == '__main__':
    root = tk.Tk()
    root.title("Dashboard")
    root.geometry(f"{STREAM_WIDTH + 150}x{STREAM_HEIGHT + 100}")
    connection_frame = ttk.Frame(root)
    connection_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

    connection_label = tk.Label(connection_frame, text="●", fg="red", font=('Arial', 14))
    connection_label.pack(side=tk.LEFT)

    reconnect_btn = tk.Button(
        connection_frame,
        text="Reconnect",
        command=lambda: connect_to_server(show_error=True)
    )
    reconnect_btn.pack(side=tk.LEFT, padx=5)
    control_frame = tk.Frame(root)
    control_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
    joystick = Joystick(
        master=control_frame,
        size=150,
        send_callback=lambda d, s: sio.emit('manual_cmd', {'direction': d, 'speed': s})
    )

    joystick_control_frame = ttk.LabelFrame(control_frame, text="Joystick Control")
    joystick_control_frame.pack(side=tk.LEFT, padx=10)

    mode_var = tk.StringVar(value='auto')
    on_mode_change()
    ttk.Radiobutton(
        joystick_control_frame,
        text="Auto",
        variable=mode_var,
        value='auto',
        command=on_mode_change
    ).pack(side=tk.LEFT)

    ttk.Radiobutton(
        joystick_control_frame,
        text="Manual",
        variable=mode_var,
        value='manual',
        command=on_mode_change
    ).pack(side=tk.LEFT)

    joystick.canvas.pack(side=tk.LEFT, padx=10)
    entry = tk.Entry(control_frame, width=30)
    entry.pack(side=tk.LEFT, padx=5)
    stop_btn = tk.Button(control_frame, text="Stop Stream", command=stop_stream)
    stop_btn.pack(side=tk.LEFT, padx=5)
    debug_btn = tk.Button(control_frame, text="Debug Stream", command=start_debug_stream)
    debug_btn.pack(side=tk.LEFT, padx=5)
    main_pane = tk.PanedWindow(root, orient=tk.HORIZONTAL, bg='#f0f0f0',
                                sashrelief=tk.RAISED, sashwidth=5)
    main_pane.pack(expand=True, fill=tk.BOTH)

    center_frame = tk.Frame(main_pane, width=STREAM_WIDTH, height=STREAM_HEIGHT, bg=INITIAL_BG)
    video_label = tk.Label(center_frame, bg=INITIAL_BG, fg='white', font=('Arial', 20),
                           text='Stream Stopped', width=STREAM_WIDTH, height=STREAM_HEIGHT)
    video_label.pack(expand=True, fill=tk.BOTH)
    main_pane.add(center_frame, minsize=STREAM_WIDTH, stretch='never')

    right_notebook = ttk.Notebook(main_pane, width=150)
    main_pane.add(right_notebook, minsize=150, stretch='never')
    debug_controls_frame = ttk.Frame(right_notebook)
    right_notebook.add(debug_controls_frame, text="Debug Controls")
    pid_controls_frame = ttk.Frame(right_notebook)
    right_notebook.add(pid_controls_frame, text="PID Controls")
    chart_frame = ttk.Frame(right_notebook)
    right_notebook.add(chart_frame, text="Object Detection")
    debug_var = tk.BooleanVar(value=False)
    debug_check = ttk.Checkbutton(
        debug_controls_frame,
        text="Show Debug Overlays",
        variable=debug_var,
        command=lambda: sio.emit('toggle_debug', {'enabled': debug_var.get()}) if sio.connected else None
    )
    debug_check.pack(padx=10, pady=10)
    brightness_frame = ttk.Frame(debug_controls_frame)
    brightness_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Label(brightness_frame, text="Brightness:").pack(side=tk.LEFT)

    brightness_label = ttk.Label(brightness_frame, text="0")
    brightness_label.pack(side=tk.LEFT, padx=5)

    brightness_slider = ttk.Scale(
        brightness_frame,
        from_=-100,
        to=100,
        orient=tk.HORIZONTAL,
        command=lambda val: [
            brightness_label.config(text=f"{float(val)}"),
            sio.emit('set_brightness', {'value': float(val)})
        ]
    )
    brightness_slider.set(0)  # Default neutral value
    brightness_slider.pack(side=tk.LEFT, expand=True, fill=tk.X)
    contrast_frame = ttk.Frame(debug_controls_frame)
    contrast_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Label(contrast_frame, text="Contrast:").pack(side=tk.LEFT)

    contrast_label = ttk.Label(contrast_frame, text="1.0x")
    contrast_label.pack(side=tk.LEFT, padx=5)

    contrast_slider = ttk.Scale(
        contrast_frame,
        from_=0.5,
        to=3.0,
        orient=tk.HORIZONTAL,
        command=lambda val: [
            contrast_label.config(text=f"{float(val):.1f}x"),
            sio.emit('set_contrast', {'value': float(val)})
        ]
    )
    contrast_slider.set(1.0)
    contrast_slider.pack(side=tk.LEFT, expand=True, fill=tk.X)
    auto_move_frame = ttk.Frame(debug_controls_frame)
    auto_move_frame.pack(fill=tk.X, padx=10, pady=5)

    auto_move_var = tk.BooleanVar(value=False)
    auto_move_check = ttk.Checkbutton(
        auto_move_frame,
        text="Enable Auto Movement",
        variable=auto_move_var,
        command=lambda: sio.emit('set_auto_movement', {'enabled': auto_move_var.get()})
        if sio.connected else None
    )
    auto_move_check.pack(side=tk.LEFT)
    tolerance_entry = create_numeric_input(
        debug_controls_frame,
        "Movement Tolerance:",
        0, 1000, 100,
        lambda val: sio.emit('set_tolerance', {'value': val}) if sio.connected else None
    )

    car_speed_entry = create_numeric_input(
        debug_controls_frame,
        "Car Speed:",
        0, 255, 90,
        lambda val: sio.emit('set_speed', {'value': val}) if sio.connected else None
    )

    modifier_entry = create_numeric_input(
        debug_controls_frame,
        "Speed Modifier:",
        0.0,
        1.0,
        1.0,
        lambda val: sio.emit('set_modifier', {'value': float(val)})  # Add float conversion
    )

    max_speed_entry = create_numeric_input(
        debug_controls_frame,
        "Max Speed:",
        0, 255, 130,
        lambda val: sio.emit('set_max_speed', {'value': val}) if sio.connected else None
    )

    min_speed_entry = create_numeric_input(
        debug_controls_frame,
        "Min Speed:",
        0, 255, 80,
        lambda val: sio.emit('set_min_speed', {'value': val}) if sio.connected else None
    )
    forward_frames_entry = create_numeric_input(
        debug_controls_frame,
        "Forward Frames:",
        0, 500, 25,
        lambda val: sio.emit('set_forward_frames', {'value': val}) if sio.connected else None
    )
    direction_frames_entry = create_numeric_input(
        debug_controls_frame,
        "Direction Frames:",
        0, 500, 25,
        lambda val: sio.emit('set_direction_frames', {'value': val}) if sio.connected else None
    )
    stop_frames_entry = create_numeric_input(
        debug_controls_frame,
        "Stop Frames:",
        0, 500, 25,
        lambda val: sio.emit('set_stop_frames', {'value': val}) if sio.connected else None
    )
    height_modifier_entry = create_numeric_input(
        debug_controls_frame,
        "Height Modifier:",
        0.0,
        1.0,
        0.3,
        lambda val: sio.emit('set_height_modifier', {'value': float(val)})  # Add float conversion
    )
    black_threshold_entry = create_numeric_input(
        debug_controls_frame,
        "Black Threshold:",
        0, 500, 100,
        lambda val: sio.emit('set_black_threshold', {'value': val}) if sio.connected else None
    )
    erode_count_entry = create_numeric_input(
        debug_controls_frame,
        "Erode count:",
        0, 500, 2,
        lambda val: sio.emit('set_erode_count', {'value': val}) if sio.connected else None
    )
    dilate_count_entry = create_numeric_input(
        debug_controls_frame,
        "Dilate count:",
        0, 500, 3,
        lambda val: sio.emit('set_dilate_count', {'value': val}) if sio.connected else None
    )
    kp_modifier_entry = create_numeric_input(
        pid_controls_frame,
        "Kp:",
        0.0,
        1.0,
        0.6,
        lambda val: sio.emit('set_kp_modifier', {'value': float(val)})
    )
    ki_modifier_entry = create_numeric_input(
        pid_controls_frame,
        "Ki:",
        0.0,
        1.0,
        0.02,
        lambda val: sio.emit('set_ki_modifier', {'value': float(val)})
    )
    kd_modifier_entry = create_numeric_input(
        pid_controls_frame,
        "Kd:",
        0.0,
        1.0,
        0.15,
        lambda val: sio.emit('set_kd_modifier', {'value': float(val)})
    )
    max_integral_entry = create_numeric_input(
        pid_controls_frame,
        "Max Integral:",
        0, 500, 100,
        lambda val: sio.emit('set_max_integral', {'value': val}) if sio.connected else None
    )
    output_limit_entry = create_numeric_input(
        pid_controls_frame,
        "Output Limit:",
        0, 500, 40,
        lambda val: sio.emit('set_output_limit', {'value': val}) if sio.connected else None
    )
    periodic_chart_update()
    try:
        connect_to_server()
    except Exception as e:
        messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
    root.mainloop()
    if sio.connected:
        sio.disconnect()