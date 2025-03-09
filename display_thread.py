import threading
import cv2
import queue
import time

# class DisplayThread(threading.Thread):
#     def __init__(self, display_queue, exit_event):
#         super().__init__()
#         self.display_queue = display_queue
#         self.exit_event = exit_event

#     def run(self):
#         cv2.namedWindow("Processed Frame", cv2.WINDOW_NORMAL)
#         cv2.namedWindow("Yellow Mask", cv2.WINDOW_NORMAL)

#         while not self.exit_event.is_set():
#             try:
#                 frame, mask = self.display_queue.get(timeout=0.1)
#                 if frame is not None:
#                     cv2.imshow("Processed Frame", frame)
#                 if mask is not None:
#                     cv2.imshow("Yellow Mask", mask)
#                 cv2.waitKey(1)
#             except queue.Empty:
#                 continue
#             except Exception as e:
#                 print(f"Display error: {e}")

#         cv2.destroyAllWindows()
class DisplayThread(threading.Thread):
    def __init__(self, display_queue, exit_event, user_data):
        super().__init__()
        self.display_queue = display_queue
        self.exit_event = exit_event
        self.user_data = user_data
        self.alpha = 0.1  # EMA smoothing factor
        self.last_frame_time = time.time()
        self.display_fps = 30.0

    def run(self):
        cv2.namedWindow("Processed Frame", cv2.WINDOW_NORMAL)
        cv2.namedWindow("Yellow Mask", cv2.WINDOW_NORMAL)

        while not self.exit_event.is_set():
            try:
                # Get frame data with timeout for exit checking
                frame, mask = self.display_queue.get(timeout=0.1)
                
                # Calculate display FPS
                current_time = time.time()
                frame_interval = current_time - self.last_frame_time
                self.last_frame_time = current_time
                
                if frame_interval > 0:
                    current_fps = 1.0 / frame_interval
                    # Update EMA for smooth FPS display
                    self.display_fps = self.alpha * current_fps + (1 - self.alpha) * self.display_fps

                # Add FPS overlay to frame
                if frame is not None:
                    fps_text = f"Display FPS: {self.display_fps:.1f}"
                    cv2.putText(frame, fps_text, (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    # Get processing FPS from shared data
                    with self.user_data.fps_lock:
                        processing_fps = self.user_data.ema_fps
                    proc_text = f"Processing FPS: {processing_fps:.1f}"
                    cv2.putText(frame, proc_text, (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                    cv2.imshow("Processed Frame", frame)
                
                if mask is not None:
                    cv2.imshow("Yellow Mask", mask)
                
                # Maintain OpenCV display refresh
                cv2.waitKey(1)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Display error: {e}")

        cv2.destroyAllWindows()
