from celery import shared_task
import redis
from django.conf import settings
from .models import Video
from django.db.models import F
from django.db import transaction

r = redis.Redis.from_url(settings.REDIS_URL,decode_responses=True)


@shared_task
def sync_video_views():

    dirty_videos = r.smembers("views:dirty_videos")

    if not dirty_videos:
        return
    
    updates = {}
    for video_id in dirty_videos:
        count_key=  f'views:count:{video_id}'
        view_count= int(r.getset(count_key,0) or 0)
        
        v = Video.objects.get(id=video_id)
        v.view_count += view_count
        v.save()
        print(f"final view count : {v.view_count}")

    r.delete("views:dirty_videos")

    return "updatefasdfad"