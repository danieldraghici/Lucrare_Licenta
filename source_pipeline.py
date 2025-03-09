from hailo_apps_infra.gstreamer_helper_pipelines import QUEUE, OVERLAY_PIPELINE


def SOURCE_PIPELINE(video_format="RGB", name="source"):
    source_element = (
        f"libcamerasrc name={name} af-mode=auto ! videoconvert ! videobox autocrop=true ! "
        f"video/x-raw,format={video_format} ! "
    )
    source_pipeline = (
        f"{source_element} "
        f'{QUEUE(name=f"{name}_scale_q")} ! '
        f"videoflip video-direction=180 ! "
    )

    return source_pipeline


def DISPLAY_PIPELINE(
    video_sink="autovideosink", sync="true", show_fps="false", name="hailo_display"
):
    display_pipeline = (
        f'{OVERLAY_PIPELINE(name=f"{name}_overlay")} ! '
        f'{QUEUE(name=f"{name}_videoconvert_q")} ! '
        f"videoconvert name={name}_videoconvert n-threads=2 qos=false ! "
        f'{QUEUE(name=f"{name}_q")} ! '
        f"jpegenc ! fpsdisplaysink name={name} video-sink={video_sink} sync={sync} text-overlay={show_fps} signal-fps-measurements=true "
    )

    return display_pipeline
