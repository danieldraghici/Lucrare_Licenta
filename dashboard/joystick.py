import tkinter as tk
import math
import requests

DIRECTION_FORWARD = "F"
DIRECTION_LEFT = "L"
DIRECTION_RIGHT = "R"
DIRECTION_STOP = "S"
DIRECTION_BACKWARD = "B"


class Joystick:
    def __init__(self, master, size=150, send_callback=None,max_speed=255, **kwargs):
        self.master = master
        self.enabled = True
        self.size = size
        self.center = size // 2
        self.radius = size // 3
        self.knob_radius = 10
        self.deadzone = self.radius * 0.15

        self.canvas = tk.Canvas(master, width=size, height=size,
                                bg='#f0f0f0', highlightthickness=0, **kwargs)

        self.bg_circle = self.canvas.create_oval(
            self.center - self.radius,
            self.center - self.radius,
            self.center + self.radius,
            self.center + self.radius,
            outline="#555", fill="#ddd", width=2
        )
        self.canvas.create_oval(
            self.center - self.deadzone,
            self.center - self.deadzone,
            self.center + self.deadzone,
            self.center + self.deadzone,
            outline="#aaa", fill="#eee", dash=(2, 2)
        )

        self._draw_direction_markers()

        self.knob = self.canvas.create_oval(
            self.center - self.knob_radius,
            self.center - self.knob_radius,
            self.center + self.knob_radius,
            self.center + self.knob_radius,
            outline="#333", fill="#666", width=2, tags="knob"
        )

        self.canvas.create_oval(
            self.center - 2,
            self.center - 2,
            self.center + 2,
            self.center + 2,
            fill="#f00", outline=""
        )

        self.disabled_overlay = self.canvas.create_rectangle(
            0, 0, size, size,
            fill='gray50', stipple='gray50', state='hidden'
        )

        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_move)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        
        self.send_callback = send_callback
        self.last_direction = DIRECTION_STOP
        self.last_speed = 0
        self.max_speed = max_speed
        self.min_speed = 0
        self.motor_left = 0
        self.motor_right = 0

    def _draw_direction_markers(self):
        arrow_size = self.radius * 0.2
        center = self.center

        self.canvas.create_polygon(
            center, center - self.radius + arrow_size,
                    center - arrow_size, center - self.radius + arrow_size * 2,
                    center + arrow_size, center - self.radius + arrow_size * 2,
            fill="#090", outline=""
        )

        self.canvas.create_polygon(
            center, center + self.radius - arrow_size,
                    center - arrow_size, center + self.radius - arrow_size * 2,
                    center + arrow_size, center + self.radius - arrow_size * 2,
            fill="#900", outline=""
        )

        self.canvas.create_polygon(
            center - self.radius + arrow_size, center,
            center - self.radius + arrow_size * 2, center - arrow_size,
            center - self.radius + arrow_size * 2, center + arrow_size,
            fill="#009", outline=""
        )

        self.canvas.create_polygon(
            center + self.radius - arrow_size, center,
            center + self.radius - arrow_size * 2, center - arrow_size,
            center + self.radius - arrow_size * 2, center + arrow_size,
            fill="#009", outline=""
        )

    def _on_press(self, event):
        if not self.enabled:
            return
        self._on_move(event)

    def _on_move(self, event):
        if not self.enabled:
            return

        dx = event.x - self.center
        dy = event.y - self.center
        dist = math.hypot(dx, dy)

        if dist > self.radius:
            dx *= self.radius / dist
            dy *= self.radius / dist
            dist = self.radius

        self.canvas.coords(
            self.knob,
            self.center + dx - self.knob_radius,
            self.center + dy - self.knob_radius,
            self.center + dx + self.knob_radius,
            self.center + dy + self.knob_radius
        )

        if dist > self.deadzone:
            self._send_command(dx, dy, dist)
        else:
            self._send_stop()

    def _on_release(self, event):
        self.canvas.coords(
            self.knob,
            self.center - self.knob_radius,
            self.center - self.knob_radius,
            self.center + self.knob_radius,
            self.center + self.knob_radius
        )
        self._send_stop()

    def _send_command(self, dx, dy, dist):
        norm_x = dx / self.radius
        norm_y = -dy / self.radius

        normalized_dist = min(1.0, (dist - self.deadzone) / (self.radius - self.deadzone))

        self.motor_left = normalized_dist * (norm_y - norm_x) * self.max_speed
        self.motor_right = normalized_dist * (norm_y + norm_x) * self.max_speed

        self.motor_left = max(-self.max_speed, min(self.max_speed, self.motor_left))
        self.motor_right = max(-self.max_speed, min(self.max_speed, self.motor_right))

        if self.send_callback:
            self.send_callback(self.motor_left, self.motor_right)
        else:
            try:
                print(f"Motors: L={self.motor_left:.0f}, R={self.motor_right:.0f}")
                requests.post(
                    'http://localhost:5000/manual',
                    json={'left': self.motor_left, 'right': self.motor_right},
                    timeout=0.5
                )
            except Exception as e:
                print(f"Command send error: {e}")

    def _send_stop(self):
        self.motor_left = 0
        self.motor_right = 0

        if self.send_callback:
            self.send_callback(0, 0)
        else:
            try:
                requests.post(
                    'http://localhost:5000/manual',
                    json={'left': 0, 'right': 0},
                    timeout=0.5
                )
            except Exception as e:
                print(f"Stop command error: {e}")

    def set_enabled(self, enabled):
        self.enabled = enabled
        state = 'hidden' if enabled else 'normal'
        self.canvas.itemconfig(self.disabled_overlay, state=state)

        if not enabled:
            self._send_stop()
            self.canvas.coords(
                self.knob,
                self.center - self.knob_radius,
                self.center - self.knob_radius,
                self.center + self.knob_radius,
                self.center + self.knob_radius
            )

    def set_max_speed(self, max_speed):
        self.max_speed = max_speed

    def grid(self, *args, **kwargs):
        self.canvas.grid(*args, **kwargs)

    def pack(self, *args, **kwargs):
        self.canvas.pack(*args, **kwargs)

    def place(self, *args, **kwargs):
        self.canvas.place(*args, **kwargs)

    def destroy(self):
        self.canvas.destroy()