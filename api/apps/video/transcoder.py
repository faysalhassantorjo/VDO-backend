from apps.video.models import Video
import os
import subprocess
from django.conf import settings
from celery import shared_task

def generate_thumbnail(video_file_path,thumbnail_path):
    command = [
        'ffmpeg',
        '-ss', '3',
        '-i', video_file_path,
        '-vframes', '1',
        '-q:v', '2',
        thumbnail_path
    ]
    subprocess.run(command, check=True)
    relative_thumbnail_path = os.path.relpath(thumbnail_path, settings.MEDIA_ROOT)
    relative_thumbnail_path = relative_thumbnail_path.replace("\\", "/")
    return relative_thumbnail_path

def adaptive_variant(video_file_path, resolutions=[360, 720]):


    # media/videos/uuid/video.mp4
    base_name = os.path.splitext(os.path.basename(video_file_path))[0]

    # media/videos/uuid/video/
    output_dir = os.path.join(os.path.dirname(video_file_path), base_name)
    os.makedirs(output_dir, exist_ok=True)

    thumbnail_path = os.path.join(output_dir, "thumbnail.jpg")
    
    thumbnail = generate_thumbnail(video_file_path,thumbnail_path)

    variants = []

    for resolution in resolutions:
        res_dir = os.path.join(output_dir, f"{resolution}p")
        os.makedirs(res_dir, exist_ok=True)

        # estimated bandwidth
        if resolution == 360:
            bandwidth = 800000
        elif resolution == 720:
            bandwidth = 2500000
        else:
            bandwidth = 5000000

        variants.append({
            "resolution": resolution,
            "bandwidth": bandwidth
        })

        command = [
            'ffmpeg',
            '-i', video_file_path,
            '-vf', f'scale=-2:{resolution}',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-hls_time', '10',
            '-hls_list_size', '0',
            '-f', 'hls',
            os.path.join(res_dir, 'index.m3u8')
        ]

        subprocess.run(command, check=True)

    # create master playlist
    master_path = os.path.join(output_dir, 'master.m3u8')

    with open(master_path, 'w') as f:
        f.write('#EXTM3U\n')

        for variant in variants:
            width = 640 if variant["resolution"] == 360 else 1280

            f.write(
                f'#EXT-X-STREAM-INF:BANDWIDTH={variant["bandwidth"]},'
                f'RESOLUTION={width}x{variant["resolution"]}\n'
            )
            f.write(f'{variant["resolution"]}p/index.m3u8\n')

    # return relative path for DB
    relative_master_path = os.path.relpath(master_path, settings.MEDIA_ROOT)
    relative_master_path = relative_master_path.replace("\\", "/")

    return [relative_master_path , thumbnail]

@shared_task
def process_video(video_id, file_path):
    try:
        master_path, thumbnail = adaptive_variant(file_path)

        video = Video.objects.get(id=video_id)
        video.master_playlist = master_path
        video.thumbnail = thumbnail
        video.save()

    except Exception as e:
        print("Processing failed:", e)