from hailo_apps.python.core.common.buffer_utils import get_caps_from_pad


def get_frame_info(pad, info):
    if hasattr(info, 'get_buffer'):
        frame_buffer = info.get_buffer()
    else:
        frame_buffer = info
    frame_format, frame_width, frame_height = (None, None, None)
    if hasattr(pad, 'get_current_caps'):
        frame_format, frame_width, frame_height = (
        get_caps_from_pad(pad) if frame_buffer else (None, None, None)
    )
    return frame_buffer, frame_format, frame_width, frame_height


def get_bbox_coords(bbox, width, height):
    return [
        int(v)
        for v in (
            bbox.xmin() * width,
            bbox.ymin() * height,
            bbox.width() * width,
            bbox.height() * height,
        )
    ]
