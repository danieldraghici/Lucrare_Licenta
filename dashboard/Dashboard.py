import tkinter as tk
from threading import Lock
from tkinter import ttk, messagebox
import threading
from queue import Queue
from PIL import Image, ImageTk
import matplotlib
from joystick import Joystick

matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import cv2
import time
import socketio

# Global variables
sio = socketio.Client()
frame_queue = Queue()
stop_event = threading.Event()
stream_thread = None
STREAM_WIDTH = 640
STREAM_HEIGHT = 640
INITIAL_BG = 'gray25'
detection_counts = {}
current_chart = None
current_image_label = None
sign_images = {}
detection_lock = Lock()
LAST_UPDATE_TIME = 0
UPDATE_INTERVAL = 1
DETECTION_IMAGE_DURATION = 2000
IMAGE_SIZE = (200, 200)

# Declare global UI components
disconnect_btn = None
stop_btn = None
debug_btn = None
tolerance_entry = None
car_speed_entry = None
brightness_slider = None
connection_label = None
joystick = None
joystick_control_frame = None
pid_controls_frame = None
center_frame = None
video_label = None
debug_controls = []
pid_controls = []
mode_var = None
debug_var = None
auto_move_var = None
main_pane = None
right_panel = None


# ---------------------------
# Helper/Utility Functions
# ---------------------------
def safe_emit(event_name, data):
    if sio.connected:
        try:
            sio.emit(event_name, data)
        except Exception as e:
            print(f"Error emitting {event_name}: {e}")
    else:
        print(f"Not connected, skipping {event_name}")


def on_mousewheel(event, canvas):
    if event.delta:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    elif event.num == 4:
        canvas.yview_scroll(-1, "units")
    elif event.num == 5:
        canvas.yview_scroll(1, "units")


def bind_to_mousewheel(widget, canvas):
    widget.bind("<MouseWheel>", lambda e: on_mousewheel(e, canvas))
    widget.bind("<Button-4>", lambda e: on_mousewheel(e, canvas))
    widget.bind("<Button-5>", lambda e: on_mousewheel(e, canvas))


# ---------------------------
# SocketIO Event Handlers
# ---------------------------
def on_connect():
    global tolerance_entry, car_speed_entry
    connection_label.config(fg="green")
    print("🟢 Connected to server")
    toggle_controls(True)
    try:
        safe_emit('set_auto_movement', {'enabled': auto_move_var.get()})
        safe_emit('toggle_debug', {'enabled': debug_var.get()})
        safe_emit('set_brightness', {'value': float(brightness_slider.get())})
        safe_emit('set_tolerance', {'value': int(tolerance_entry.get())})
        safe_emit('set_speed', {'value': int(car_speed_entry.get())})
        safe_emit('set_mode', {'mode': mode_var.get()})
    except Exception as e:
        print(f"Error sending initial values: {str(e)}")


@sio.on('disconnect')
def on_disconnect():
    connection_label.config(fg="red")
    print("🔴 Disconnected")
    toggle_controls(False)
    stop_stream()
    sio.disconnect()


@sio.on('detection')
def on_detection(data):
    show_message(data['msg'])


@sio.on('mode_ack')
def on_mode_ack(data):
    print("Mode is now:", data['mode'])


@sio.on('control_ack')
def on_control_ack(data):
    print("Control state:", data['state'])


@sio.on('move_frequency_ack')
def on_move_frequency_ack(data):
    print("Move frequency updated to:", data['value'])


@sio.on('sign_detected')
def on_sign_detected(data):
    sign_name = data.get('sign', '')
    if sign_name:
        print(f"[SIGN] Received sign detection: {sign_name}")
        with detection_lock:
            if sign_name in detection_counts:
                detection_counts[sign_name] += 1
            else:
                detection_counts[sign_name] = 1
        root.after(0, update_pie_chart)
        root.after(0, show_detection_image, sign_name)


# ---------------------------
# UI Control Functions
# ---------------------------
def toggle_controls(connected):
    if connected:
        connection_label.config(fg="green")
        enable_all_controls()
    else:
        connection_label.config(fg="red")
        disable_all_controls()


def disable_all_controls():
    state = 'disabled'
    if disconnect_btn: disconnect_btn.config(state=state)
    if stop_btn: stop_btn.config(state=state)
    if debug_btn: debug_btn.config(state=state)

    if joystick_control_frame:
        for widget in joystick_control_frame.winfo_children():
            try:
                widget.config(state=state)
            except tk.TclError:
                pass

    if joystick: joystick.set_enabled(False)

    for widget in debug_controls + pid_controls:
        try:
            widget.config(state=state)
        except tk.TclError:
            pass


def enable_all_controls():
    state = 'normal'
    if disconnect_btn: disconnect_btn.config(state=state)
    if stop_btn: stop_btn.config(state=state)
    if debug_btn: debug_btn.config(state=state)

    if joystick_control_frame:
        for widget in joystick_control_frame.winfo_children():
            try:
                widget.config(state=state)
            except tk.TclError:
                pass

    if joystick: joystick.set_enabled(mode_var.get() == 'manual')

    for widget in debug_controls + pid_controls:
        try:
            widget.config(state=state)
        except tk.TclError:
            pass


def on_mode_change():
    if not sio.connected: return
    mode = mode_var.get()
    try:
        safe_emit('set_mode', {'mode': mode})
        if joystick: joystick.set_enabled(mode == 'manual')
    except Exception as e:
        messagebox.showerror("Mode Error", f"Failed to set mode: {str(e)}")


def update_car_speed(val):
    int_val = int(val)
    safe_emit('set_speed', {'value': int_val}) if sio.connected else None
    if joystick: joystick.set_max_speed(int_val)


# ---------------------------
# Detection Functions
# ---------------------------
def show_message(message):
    print(f"[DEBUG] Raw message received: {message}")
    with detection_lock:
        if isinstance(message, str) and message.strip():
            obj_type = message.strip().lower()
            detection_counts[obj_type] = detection_counts.get(obj_type, 0) + 1
            root.after(0, show_detection_image, obj_type)
        periodic_chart_update()


def show_detection_image(obj_type):
    global current_image_label
    if current_image_label:
        current_image_label.destroy()
    obj_type_lower = obj_type.lower()
    if obj_type_lower in sign_images:
        photo_img = sign_images[obj_type_lower]
        current_image_label = tk.Label(
            center_frame,
            image=photo_img,
            borderwidth=0,
            bg=INITIAL_BG
        )
        current_image_label.image = photo_img
        current_image_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        root.after(DETECTION_IMAGE_DURATION, current_image_label.destroy)
    else:
        print(f"No preloaded image for {obj_type}")


def update_pie_chart():
    global current_chart, LAST_UPDATE_TIME
    current_time = time.time()
    if current_time - LAST_UPDATE_TIME < UPDATE_INTERVAL and detection_counts:
        return
    with detection_lock:
        if not detection_counts: return
        labels = list(detection_counts.keys())
        sizes = list(detection_counts.values())
        for widget in chart_frame.winfo_children():
            widget.destroy()
        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)
        if sizes:
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.set_title('Detection Distribution')
        else:
            ax.text(0.5, 0.5, 'No detections yet', ha='center', va='center', fontsize=12)
            ax.axis('off')
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        current_chart = canvas
    LAST_UPDATE_TIME = current_time


def periodic_chart_update():
    global LAST_UPDATE_TIME
    now = time.time()
    if (now - LAST_UPDATE_TIME) >= UPDATE_INTERVAL and detection_counts:
        update_pie_chart()
        LAST_UPDATE_TIME = now
    root.after(5000, periodic_chart_update)


# ---------------------------
# Stream Management
# ---------------------------
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


def stop_stream():
    with frame_queue.mutex:
        frame_queue.queue.clear()
    safe_emit('control_cmd', {'state': 'stop'})
    stop_event.set()
    if video_label:
        video_label.config(image='', bg=INITIAL_BG, text='Stream Stopped',
                           fg='white', font=('Arial', 20))
    global current_image_label
    if current_image_label:
        current_image_label.destroy()
        current_image_label = None


def start_debug_stream():
    global stream_thread
    stop_event.set()
    stop_event.clear()
    stream_thread = threading.Thread(target=play_debug_stream, daemon=True)
    stream_thread.start()
    if video_label:
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
    if video_label:
        video_label.config(bg=INITIAL_BG)
    while cap.isOpened() and not stop_event.is_set():
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT))
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        imgtk = ImageTk.PhotoImage(image=img)
        frame_queue.put(imgtk)
    cap.release()
    stop_event.set()


def update_label():
    last_imgtk = None
    while not frame_queue.empty():
        last_imgtk = frame_queue.get()
    if last_imgtk is not None and video_label:
        video_label.imgtk = last_imgtk
        video_label.config(image=last_imgtk)
    if not stop_event.is_set():
        root.after(10, update_label)


# ---------------------------
# UI Component Creation
# ---------------------------
def create_numeric_input(parent, label, min_val, max_val, default_val, command):
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Label(frame, text=label).pack(side=tk.LEFT)
    validate_cmd = (frame.register(lambda p: p.replace('.', '', 1).isdigit() or p == ""), '%P')
    entry = ttk.Entry(frame, width=5, validate='key', validatecommand=validate_cmd)
    entry.pack(side=tk.LEFT, padx=5)
    entry.insert(0, str(default_val))
    ttk.Label(frame, text=f"({min_val:.1f}-{max_val:.1f})").pack(side=tk.LEFT)

    def update_value(*args):
        try:
            value = float(entry.get())
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


def create_scrollable_frame(parent, title):
    frame = ttk.LabelFrame(parent, text=title)
    frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    canvas = tk.Canvas(frame, highlightthickness=0)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    canvas.bind("<MouseWheel>", lambda e: on_mousewheel(e, canvas))
    canvas.bind("<Button-4>", lambda e: on_mousewheel(e, canvas))
    canvas.bind("<Button-5>", lambda e: on_mousewheel(e, canvas))
    bind_to_mousewheel(scrollable_frame, canvas)

    return scrollable_frame, canvas


def setup_connection_frame():
    global connection_label, disconnect_btn
    frame = ttk.Frame(root)
    frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

    connection_label = tk.Label(frame, text="●", fg="red", font=('Arial', 14))
    connection_label.pack(side=tk.LEFT)

    connect_btn = tk.Button(frame, text="Connect", command=lambda: connect_to_server(show_error=True))
    connect_btn.pack(side=tk.LEFT, padx=5)
    disconnect_btn = tk.Button(frame, text="Disconnect", command=lambda: sio.disconnect())
    disconnect_btn.pack(side=tk.LEFT, padx=5)
    return frame


def setup_control_frame():
    global joystick, joystick_control_frame, debug_btn, stop_btn, pid_controls_frame, mode_var
    frame = tk.Frame(root)
    frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

    # Create joystick and controls
    joystick = Joystick(
        master=frame,
        size=150,
        send_callback=lambda d, s: safe_emit('manual_cmd', {'direction': d,
                                                            'speed': s}) if auto_move_var and auto_move_var.get() else None,
        max_speed=150
    )

    # Joystick mode control
    joystick_control_frame = ttk.LabelFrame(frame, text="Joystick Control")
    joystick_control_frame.pack(side=tk.LEFT, padx=10)

    mode_var = tk.StringVar(value='auto')
    ttk.Radiobutton(joystick_control_frame, text="Auto", variable=mode_var, value='auto', command=on_mode_change).pack(
        side=tk.LEFT)
    ttk.Radiobutton(joystick_control_frame, text="Manual", variable=mode_var, value='manual',
                    command=on_mode_change).pack(side=tk.LEFT)

    # Pack joystick
    joystick.canvas.pack(side=tk.LEFT, padx=10)

    # PID controls
    pid_controls_frame = ttk.LabelFrame(frame, text="PID Controls")
    pid_controls_frame.pack(side=tk.LEFT, fill=tk.X, padx=10, pady=5)

    # Control buttons
    debug_btn = tk.Button(frame, text="Debug Stream", command=start_debug_stream)
    debug_btn.pack(side=tk.LEFT, padx=5)
    stop_btn = tk.Button(frame, text="Stop Stream", command=stop_stream)
    stop_btn.pack(side=tk.LEFT, padx=5)

    return frame


def setup_center_frame():
    global center_frame, video_label
    center_frame = tk.Frame(main_pane, width=STREAM_WIDTH, height=STREAM_HEIGHT, bg=INITIAL_BG)
    video_label = tk.Label(center_frame, bg=INITIAL_BG, fg='white', font=('Arial', 20),
                           text='Stream Stopped', width=STREAM_WIDTH, height=STREAM_HEIGHT)
    video_label.pack(expand=True, fill=tk.BOTH)
    main_pane.add(center_frame, minsize=STREAM_WIDTH, stretch='never')
    return center_frame


def setup_right_panel():
    global right_panel, chart_frame
    right_panel = ttk.Notebook(main_pane)
    main_pane.add(right_panel, minsize=300, stretch='never')

    # Create vertical panes for image controls, movement controls, and chart
    right_vertical_pane = tk.PanedWindow(right_panel, orient=tk.VERTICAL)
    right_vertical_pane.pack(fill=tk.BOTH, expand=True)

    # Add the three frames
    setup_debug_controls_frame(right_vertical_pane)
    setup_chart_frame(right_vertical_pane)

    return right_panel


def setup_debug_controls_frame(parent):
    # Create Image Processing Controls Frame
    setup_image_controls_frame(parent)

    # Create Vehicle Movement Controls Frame
    setup_movement_controls_frame(parent)


def setup_image_controls_frame(parent):
    global debug_var, debug_check
    image_controls_frame = ttk.LabelFrame(parent, text="Image Processing Controls")
    image_controls_frame.pack_propagate(False)
    parent.add(image_controls_frame, height=250)

    # Debug overlay checkbox
    debug_var = tk.BooleanVar(value=False)
    debug_check = ttk.Checkbutton(
        image_controls_frame,
        text="Show Debug Overlays",
        variable=debug_var,
        command=lambda: safe_emit('toggle_debug', {'enabled': debug_var.get()}) if sio.connected else None
    )
    debug_check.pack(padx=10, pady=10)

    # Create scrollable area for image controls
    image_canvas = tk.Canvas(image_controls_frame)
    image_scrollbar = ttk.Scrollbar(image_controls_frame, orient="vertical", command=image_canvas.yview)
    image_scrollable_frame = ttk.Frame(image_canvas)

    image_scrollable_frame.bind("<Configure>", lambda e: image_canvas.configure(scrollregion=image_canvas.bbox("all")))
    image_canvas.create_window((0, 0), window=image_scrollable_frame, anchor="nw")
    image_canvas.configure(yscrollcommand=image_scrollbar.set)

    image_canvas.pack(side="left", fill="both", expand=True)
    image_scrollbar.pack(side="right", fill="y")

    # Bind mouse events
    image_canvas.bind("<MouseWheel>", lambda e: on_mousewheel(e, image_canvas))
    image_canvas.bind("<Button-4>", lambda e: on_mousewheel(e, image_canvas))
    image_canvas.bind("<Button-5>", lambda e: on_mousewheel(e, image_canvas))
    bind_to_mousewheel(image_scrollable_frame, image_canvas)

    # Add image processing controls
    create_brightness_contrast_controls(image_scrollable_frame)
    create_image_processing_controls(image_scrollable_frame)

    # Bind mouse wheel to all children
    for widget in image_scrollable_frame.winfo_children():
        bind_to_mousewheel(widget, image_canvas)


def setup_movement_controls_frame(parent):
    global auto_move_var, auto_move_check
    movement_controls_frame = ttk.LabelFrame(parent, text="Vehicle Movement Controls")
    movement_controls_frame.pack_propagate(False)
    parent.add(movement_controls_frame, height=250)

    # Auto movement checkbox
    auto_move_var = tk.BooleanVar(value=False)
    auto_move_check = ttk.Checkbutton(
        movement_controls_frame,
        text="Enable Movement",
        variable=auto_move_var,
        command=lambda: safe_emit('set_auto_movement', {'enabled': auto_move_var.get()}) if sio.connected else None
    )
    auto_move_check.pack(padx=10, pady=10)

    # Create scrollable area for movement controls
    movement_canvas = tk.Canvas(movement_controls_frame)
    movement_scrollbar = ttk.Scrollbar(movement_controls_frame, orient="vertical", command=movement_canvas.yview)
    movement_scrollable_frame = ttk.Frame(movement_canvas)

    movement_scrollable_frame.bind("<Configure>",
                                   lambda e: movement_canvas.configure(scrollregion=movement_canvas.bbox("all")))
    movement_canvas.create_window((0, 0), window=movement_scrollable_frame, anchor="nw")
    movement_canvas.configure(yscrollcommand=movement_scrollbar.set)

    movement_canvas.pack(side="left", fill="both", expand=True)
    movement_scrollbar.pack(side="right", fill="y")

    # Bind mouse events
    movement_canvas.bind("<MouseWheel>", lambda e: on_mousewheel(e, movement_canvas))
    movement_canvas.bind("<Button-4>", lambda e: on_mousewheel(e, movement_canvas))
    movement_canvas.bind("<Button-5>", lambda e: on_mousewheel(e, movement_canvas))
    bind_to_mousewheel(movement_scrollable_frame, movement_canvas)

    # Add vehicle movement controls
    create_movement_controls(movement_scrollable_frame)

    # Bind mouse wheel to all children
    for widget in movement_scrollable_frame.winfo_children():
        bind_to_mousewheel(widget, movement_canvas)


def create_brightness_contrast_controls(parent):
    global brightness_slider
    # Brightness control
    brightness_frame = ttk.Frame(parent)
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
            brightness_label.config(text=f"{float(val):.2f}"),
            safe_emit('set_brightness', {'value': float(val)})
        ]
    )
    brightness_slider.set(0)
    brightness_slider.pack(side=tk.LEFT, expand=True, fill=tk.X)

    # Contrast control
    contrast_frame = ttk.Frame(parent)
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
            safe_emit('set_contrast', {'value': float(val)})
        ]
    )
    contrast_slider.set(1.0)
    contrast_slider.pack(side=tk.LEFT, expand=True, fill=tk.X)

    debug_controls.extend([brightness_label, brightness_slider, contrast_label, contrast_slider])


def create_image_processing_controls(parent):
    # Image processing related controls
    other_controls = [
        ("Height Modifier:", 0.0, 1.0, 0.3, lambda val: safe_emit('set_height_modifier', {'value': float(val)})),
        ("Black Threshold:", 0, 500, 100, lambda val: safe_emit('set_black_threshold', {'value': val})),
        ("Erode count:", 0, 500, 2, lambda val: safe_emit('set_erode_count', {'value': val})),
        ("Dilate count:", 0, 500, 3, lambda val: safe_emit('set_dilate_count', {'value': val}))
    ]

    for label, min_val, max_val, default, command in other_controls:
        entry = create_numeric_input(parent, label, min_val, max_val, default, command)
        debug_controls.append(entry)


def create_movement_controls(parent):
    global tolerance_entry, car_speed_entry

    # Create movement controls with global references
    tolerance_entry = create_numeric_input(parent, "Movement Tolerance:", 0, 1000, 100,
                                           lambda val: safe_emit('set_tolerance',
                                                                 {'value': val}) if sio.connected else None)
    debug_controls.append(tolerance_entry)

    car_speed_entry = create_numeric_input(parent, "Car Speed:", 0, 255, 90, update_car_speed)
    debug_controls.append(car_speed_entry)

    # Create other movement controls
    movement_controls = [
        ("Forward Frames:", 0, 500, 25, lambda val: safe_emit('set_forward_frames', {'value': val})),
        ("Direction Frames:", 0, 500, 25, lambda val: safe_emit('set_direction_frames', {'value': val})),
        ("Stop Frames:", 0, 500, 25, lambda val: safe_emit('set_stop_frames', {'value': val})),
        ("Move Frequency:", 0, 100, 5, lambda val: safe_emit('set_move_frequency', {'value': val}))
    ]

    for label, min_val, max_val, default, command in movement_controls:
        entry = create_numeric_input(parent, label, min_val, max_val, default, command)
        debug_controls.append(entry)


def setup_pid_controls():
    controls = [
        ("Kp:", 0.0, 1.0, 0.6, lambda val: safe_emit('set_kp_modifier', {'value': float(val)})),
        ("Ki:", 0.0, 1.0, 0.02, lambda val: safe_emit('set_ki_modifier', {'value': float(val)})),
        ("Kd:", 0.0, 1.0, 0.15, lambda val: safe_emit('set_kd_modifier', {'value': float(val)}))
    ]
    for label, min_val, max_val, default, command in controls:
        entry = create_numeric_input(pid_controls_frame, label, min_val, max_val, default, command)
        pid_controls.append(entry)


def setup_chart_frame(parent):
    global chart_frame
    chart_frame = ttk.LabelFrame(parent, text="Object Detection")
    chart_frame.pack_propagate(False)
    parent.add(chart_frame, height=300)

    chart_placeholder = ttk.Label(chart_frame, text="Object detection chart will appear here", font=('Arial', 12))
    chart_placeholder.pack(expand=True, fill=tk.BOTH)


def preload_sign_images():
    global sign_images
    sign_names = ['stop', 'accesul_interzis', 'inainte_sau_la_dreapta', 'inainte_sau_la_stanga',
                  'la_dreapta', 'la_stanga', 'accesul_interzis']
    for sign in sign_names:
        try:
            img = Image.open(f"images/{sign}.png")
            img = img.resize(IMAGE_SIZE, Image.LANCZOS)
            photo_img = ImageTk.PhotoImage(img)
            sign_images[sign] = photo_img
        except Exception as e:
            print(f"Could not preload image for {sign}: {e}")


# ---------------------------
# Main Application Setup
# ---------------------------
if __name__ == '__main__':
    root = tk.Tk()
    root.title("Dashboard")
    root.geometry(f"{STREAM_WIDTH + 300}x{STREAM_HEIGHT + 300}")  # Adjusted height

    # Initialize control lists
    debug_controls = []
    pid_controls = []

    # Preload resources
    preload_sign_images()

    # Setup the top connection frame
    setup_connection_frame()

    # Setup bottom control frame FIRST (so it reserves space at bottom)
    control_frame = setup_control_frame()

    # Setup PID controls
    setup_pid_controls()

    # Create the main paned window AFTER control frame (so it fills remaining space)
    main_pane = tk.PanedWindow(root, orient=tk.HORIZONTAL, bg='#f0f0f0', sashrelief=tk.RAISED, sashwidth=5)
    main_pane.pack(side=tk.TOP, expand=True, fill=tk.BOTH, padx=5, pady=5)

    # Setup center and right panels
    setup_center_frame()
    setup_right_panel()

    # Final setup
    disable_all_controls()
    periodic_chart_update()

    # Register socketio events
    sio.on('connect', on_connect)
    sio.on('disconnect', on_disconnect)

    root.mainloop()

    # Cleanup
    if sio.connected:
        sio.disconnect()