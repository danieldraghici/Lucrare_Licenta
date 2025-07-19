import gi
import numpy as np
gi.require_version('Gst', '1.0')
gi.require_version("GstApp", "1.0")
from gi.repository import Gst
import setproctitle
import os
from hailo_apps_infra.hailo_rpi_common import get_default_parser, detect_hailo_arch
from hailo_apps_infra.gstreamer_helper_pipelines import (
    INFERENCE_PIPELINE,
    DISPLAY_PIPELINE,
)
from arduino_control import move_car_with_flush
from image_processing import process_frame
import cv2
import traceback
import debugpy
from server import pipeline_server
from utilities import get_frame_info
from hailo_apps_infra.gstreamer_app import GStreamerApp
from hailo_apps_infra.gstreamer_helper_pipelines import (
    OVERLAY_PIPELINE
)
from source_pipeline import SOURCE_PIPELINE

class CustomGStreamerDetectionApp(GStreamerApp):
    def __init__(self, app_callback, user_data):
        parser = get_default_parser()
        parser.add_argument(
            "--labels-json",
            default=None,
            help="Path to custom labels JSON file",
        )
        parser.add_argument(
            "--headless",
            action="store_true",
            help="Run the application in headless mode (no display).",
        )
        parser.add_argument(
            "--stream-address",
            action="store_true",
            help="Streams address of the video source.",
        )
        
        args = parser.parse_args()
        super().__init__(parser, user_data)
        self.batch_size = 2
        self.video_width=800
        self.video_height=600
        nms_score_threshold = 0.5
        nms_iou_threshold = 0.5
        if args.arch is None:
            detected_arch = detect_hailo_arch()
            if detected_arch is None:
                raise ValueError(
                    "Could not auto-detect Hailo architecture. Please specify --arch manually."
                )
            self.arch = detected_arch
            print(f"Auto-detected Hailo architecture: {self.arch}")
        else:
            self.arch = args.arch

        if args.hef_path is not None:
            self.hef_path = args.hef_path
        elif self.arch == "hailo8":
            self.hef_path = os.path.join(self.current_path, "../resources/yolov8m.hef")
        else:
            self.hef_path = os.path.join(
                self.current_path, "../resources/yolov8s_h8l.hef"
            )
        self.post_process_so = os.path.join(
            self.current_path, "../resources/libyolo_hailortpp_postprocess.so"
        )
        self.options_menu.use_frame = True
        self.source_type="rpi"
        self.labels_json = args.labels_json
        print(f"Labels JSON: {self.labels_json}")
        self.app_callback = app_callback
        self.thresholds_str = (
            f"nms-score-threshold={nms_score_threshold} "
            f"nms-iou-threshold={nms_iou_threshold} "
            f"output-format-type=HAILO_FORMAT_TYPE_FLOAT32"
        )
        setproctitle.setproctitle("Hailo Detection App")
        self.headless = args.headless
        self.stream_address = args.stream_address
        if self.headless:
            self.video_sink = "fakesink"
        elif not self.headless and self.stream_address:
            self.video_sink = "fakesink"
        else:
            self.video_sink = "autovideosink"
        self.create_pipeline()
        self.stream_pipeline = Gst.parse_launch(
            f"appsrc name=stream_src format=time is-live=true leaky-type=downstream max-buffers=1 "
            f"caps=video/x-raw,format=RGB,width=800,height=600,framerate=30/1 ! videorate ! "
            f"videoconvert ! {OVERLAY_PIPELINE(name='hailo_overlay')} ! "
            f"jpegenc ! tcpserversink port=4956 sync=false async=false"
        )
        self.stream_src = self.stream_pipeline.get_by_name("stream_src")
        self.stream_pipeline.set_state(Gst.State.PLAYING)
        debug_sink = self.pipeline.get_by_name("debug_appsink")
        if debug_sink:
            debug_sink.connect("new-sample", self.on_new_sample)
        user_data.frame_counter = 0
        
    def on_new_sample(self, sink) -> Gst.FlowReturn:
        try:
            sample = sink.emit("pull-sample")
            if not sample:
                return Gst.FlowReturn.ERROR
            buf, _, width, height = get_frame_info(sink.get_static_pad("sink"), sample)
            success, mapinfo = buf.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.ERROR
            frame = np.frombuffer(mapinfo.data, dtype=np.uint8)
            frame = frame.reshape((height, width, 3))
            frame_copy = cv2.resize(frame, (800, 600))
            adjusted_frame = cv2.addWeighted(frame_copy, pipeline_server.contrast, np.zeros(frame_copy.shape, frame_copy.dtype), 0, pipeline_server.brightness) 
            
            # Always rotate the frame and prepare for drawing detections
            display_frame = cv2.rotate(adjusted_frame, cv2.ROTATE_180)
            
            # Always draw detection bounding boxes regardless of debug mode
            with self.user_data.lock:
                for det in self.user_data.detections:
                    bbox = det.get_bbox()
                    x_min = int(bbox.xmin() * width)
                    y_min = int(bbox.ymin() * height)
                    x_max = int(bbox.xmax() * width)
                    y_max = int(bbox.ymax() * height)

                    x_min_rot, y_min_rot = width - x_max, height - y_max
                    x_max_rot, y_max_rot = width - x_min, height - y_min

                    sx, sy = 800 / width, 600 / height  # Use actual display frame dimensions
                    x0 = int(x_min_rot * sx)
                    y0 = int(y_min_rot * sy)
                    x1 = int(x_max_rot * sx)
                    y1 = int(y_max_rot * sy)

                    # Ensure coordinates are within frame bounds
                    x0 = max(0, min(x0, 799))
                    y0 = max(0, min(y0, 599))
                    x1 = max(0, min(x1, 799))
                    y1 = max(0, min(y1, 599))

                    cv2.rectangle(display_frame, (x0, y0), (x1, y1), (0, 255, 0), 2)
                    label = f"{det.get_label()}:{det.get_confidence():.2f}"
                    cv2.putText(
                        display_frame,
                        label,
                        (x0, y0 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        1,
                    )
            
            # Add debug overlays only when debug mode is enabled
            if pipeline_server.show_debug:
                with self.user_data.lock:
                    _, display_frame, roi_thresh, _ = process_frame(
                        adjusted_frame.copy(), self.user_data.detections, self.user_data, mode=1
                    )
                
                if roi_thresh is not None:
                    roi_color = (0, 0, 255)
                    alpha = 0.6

                    if roi_thresh.shape[:2] != display_frame.shape[:2]:
                        roi_thresh_resized = cv2.resize(roi_thresh, (display_frame.shape[1], display_frame.shape[0]))
                    else:
                        roi_thresh_resized = roi_thresh

                    mask_indices = roi_thresh_resized > 0
                    overlay = display_frame.copy()
                    overlay[mask_indices] = roi_color
                    cv2.addWeighted(overlay, alpha, display_frame, 1 - alpha, 0, display_frame)
            
            if self.stream_pipeline.get_state(0)[1] != Gst.State.PLAYING:
                return Gst.FlowReturn.OK
                
            gst_buf = Gst.Buffer.new_wrapped(display_frame.tobytes())
            self.stream_src.emit("push-buffer", gst_buf)
            buf.unmap(mapinfo)
            return Gst.FlowReturn.OK

        except Exception as e:
            traceback.print_exc()
            move_car_with_flush(self.user_data.arduino,self.user_data, "S", 0)
            print(f"Error in on_new_sample: {e}")
            
            debugpy.breakpoint()
            return Gst.FlowReturn.ERROR
        
    def get_pipeline_string(self):
        source = SOURCE_PIPELINE()
        inference = INFERENCE_PIPELINE(
            hef_path=self.hef_path,
            post_process_so=self.post_process_so,
            batch_size=self.batch_size,
            config_json=self.labels_json,
            additional_params=self.thresholds_str,
        )

        return (
            f"{source} tee name=src_t "
            "src_t. ! queue name=inference_input_q ! "
            f"{inference} ! "
            "identity name=identity_callback ! "
            f"{DISPLAY_PIPELINE(video_sink=self.video_sink)}"
            "src_t. ! queue name=debug_input_q ! "
            "videoconvert ! video/x-raw,format=RGB ! "
            "appsink name=debug_appsink emit-signals=true"
        )