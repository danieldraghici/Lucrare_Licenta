import time
class PIDController:
    def __init__(self, Kp, Ki, Kd, max_integral=100, output_limit=100):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.max_integral = max_integral
        self.output_limit = output_limit
        self.reset()
        
    def reset(self):
        self.prev_error = 0
        self.integral = 0
        
    def set_parameters(self, Kp=None, Ki=None, Kd=None):
        if Kp is not None:
            self.Kp = Kp
        if Ki is not None:
            self.Ki = Ki
        if Kd is not None:
            self.Kd = Kd
    def set_max_integral(self, max_integral):
        self.max_integral = max_integral
    def set_output_limit(self, output_limit):
        self.output_limit = output_limit