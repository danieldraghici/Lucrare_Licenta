from hailo_apps_infra.gstreamer_helper_pipelines import QUEUE, OVERLAY_PIPELINE
def SOURCE_PIPELINE(video_format="RGB", name="app_source"):
    return (
        f"appsrc name={name} is-live=true leaky-type=downstream max-buffers=1 ! "
        f"video/x-raw,format={video_format} ! "
    )
def DISPLAY_PIPELINE(
    video_sink="autovideosink", sync="false", show_fps="true", name="hailo_display"
):

    display_pipeline = (
        f'{OVERLAY_PIPELINE(name=f"{name}_overlay")} ! '
        f'{QUEUE(name=f"{name}_videoconvert_q")} ! '
        f'videoconvert name={name}_videoconvert n-threads=2 qos=false ! '
        f'{QUEUE(name=f"{name}_q")} ! '
        f'fpsdisplaysink name={name} video-sink={video_sink} sync=false text-overlay={show_fps} signal-fps-measurements=true '
    )
    return display_pipeline