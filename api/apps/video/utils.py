# views/utils.py
import hashlib

def get_viewer_fingerprint(request, video_id):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    user_id = request.user.id if request.user.is_authenticated else 'anon'
    
    raw = f"{video_id}:{ip}:{user_agent}:{user_id}"
    return hashlib.sha256(raw.encode()).hexdigest()

def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')