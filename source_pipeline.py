from hailo_apps_infra.gstreamer_helper_pipelines import QUEUE

def SOURCE_PIPELINE(video_format='RGB', video_width=640, video_height=640, name='source'):
    source_element = (
        f'libcamerasrc name={name} ! capsfilter caps=video/x-raw ! '
        f'video/x-raw, format=NV12, width={video_width}, height={video_height} ! '
    )
    source_pipeline = (
        f'{source_element} '
        f'{QUEUE(name=f"{name}_scale_q")} ! '
        f'videoscale name={name}_videoscale n-threads=2 ! videoflip video-direction=180 ! '
        f'videoconvert n-threads=3 name={name}_convert qos=false ! '
        f'video/x-raw, format={video_format}, width={video_width}, height={video_height}, pixel-aspect-ratio=1/1 ! '
    )

    return source_pipeline