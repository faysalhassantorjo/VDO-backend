import redis
from django.conf import settings

r = redis.Redis.from_url(settings.REDIS_URL,decode_responses=True)

def record_view(video_id, fingerprint):
    hll_key=    f'views:hll:{video_id}'
    count_key=  f'views:count:{video_id}'
    dirty_key=  f'views:dirty_videos'


    # HyperLogLog data structure diye check korbo ei fingerprint ta \
    # ache ki na 'hll_key' er modde, jodi na thake taile add kore dibw \
    # 'hll_key' er moddhe

    is_new= r.pfadd(hll_key, fingerprint) # returns 1 if the fingerprint is new


    if is_new:
        # jodi new hoy taile authentic view hoyce, tarmane view_count increment korbo
        pipe = r.pipeline(transaction=True)
        pipe.incr(count_key)
        # ekhon ei video ta 'dirty' mark korte hobe karon it has new view. pore \# db te update korbo
        pipe.sadd(dirty_key, video_id)
        print("view update korce")
        pipe.execute()
    
    return int(r.get(count_key) or 0 )

from .utils import get_viewer_fingerprint
def track_view(request, video_id):
    fingerprint = get_viewer_fingerprint(request, video_id)

    rate_key = f'views:ratelimit:{fingerprint}'


    # # check  if the fingerprint is in redis
    if r.exists(rate_key):
        print(f"rate_key: {r.get(rate_key)}")

        # taile views update korbo na 
        count = int(r.get(f'view:count:{video_id}') or 0)

        print("rate limit hoiche")
        return count
    
    # else
    r.setex(rate_key, 1800, 1)
    count = record_view(video_id, fingerprint)
    return count
