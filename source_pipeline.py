from hailo_apps_infra.gstreamer_helper_pipelines import QUEUE

def SOURCE_PIPELINE(video_format='RGB', name='source'):
    source_element = (
        f'libcamerasrc name={name} af-mode=auto ! '
        f'video/x-raw, format={video_format} ! '
    )
    source_pipeline = (
        f'{source_element} '
        f'{QUEUE(name=f"{name}_scale_q")} ! '
        f'videoscale name={name}_videoscale n-threads=2 ! videoflip video-direction=180 ! '
        f'videoconvert n-threads=3 name={name}_convert qos=false ! '
    )

    return source_pipeline