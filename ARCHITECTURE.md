# VDO Backend - Architecture Documentation

## Project Overview

This is a Django-based video streaming backend that implements:
- **Video Upload Pipeline**: Automated video processing with FFmpeg to create adaptive bitrate streaming (HLS) chunks
- **Notification System**: Real-time notifications using RabbitMQ and WebSocket
- **View Tracking**: Redis-based view counting with rate limiting and deduplication
- **Async Processing**: Celery-based background task processing

---

## Architecture

### Technology Stack

- **Backend Framework**: Django 6.0
- **API Framework**: Django REST Framework
- **Message Queue**: RabbitMQ 3.13
- **Task Queue**: Celery with Redis broker
- **Real-time Communication**: Django Channels (WebSocket)
- **Video Processing**: FFmpeg
- **Caching**: Redis 7
- **Containerization**: Docker & Docker Compose

### System Components

```
┌─────────────────┐
│   Frontend      │
└────────┬────────┘
         │ HTTP/WebSocket
         ↓
┌─────────────────┐
│  Django API     │
│  (ASGI Server)  │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┬──────────────┐
    ↓         ↓              ↓              ↓
┌───────┐ ┌───────┐    ┌──────────┐   ┌──────────┐
│ Redis │ │RabbitMQ│    │  Celery  │   │  Media   │
│       │ │       │    │  Worker  │   │ Storage  │
└───────┘ └───────┘    └──────────┘   └──────────┘
```

---

## RabbitMQ Notification System

### Architecture Flow

```
User Action → Django API → RabbitMQ Publisher → RabbitMQ Exchange
                                                           ↓
Notification Worker ← RabbitMQ Queue ← RabbitMQ Exchange
        ↓
  Django Channels Layer
        ↓
   WebSocket Client
```

### Components

#### 1. RabbitMQ Publisher (`api/apps/video/publishers.py`)

**Purpose**: Publishes notification messages to RabbitMQ exchange

**Key Function**: `publish_video_like_notification(data)`

**Configuration**:
- **Exchange**: `vdo_notifications` (topic type)
- **Routing Key**: `notification.video.like`
- **Credentials**: admin/admin
- **Host**: rabbitmq:5672

**Usage Example**:
```python
from apps.video.publishers import publish_video_like_notification

data = {
    "data": {
        "send_to": user_id,
        "message": "User liked your video"
    }
}
publish_video_like_notification(data)
```

#### 2. Notification Worker (`notification_worker/consumer.py`)

**Purpose**: Consumes messages from RabbitMQ and forwards to WebSocket clients

**Key Features**:
- Automatic reconnection logic (retries every 5 seconds)
- Consumes messages with routing key pattern: `notification.video.*`
- Forwards notifications to Django Channels layer
- Uses channel groups for targeted notifications

**Flow**:
1. Connects to RabbitMQ with retry logic
2. Declares exchange `vdo_notifications`
3. Creates exclusive queue `vdo_notification_queue`
4. Binds queue to exchange with routing key `notification.video.*`
5. On message received → sends to WebSocket via Django Channels

#### 3. WebSocket Consumer (`api/apps/notification/consumers.py`)

**Purpose**: Handles WebSocket connections for real-time notifications

**Key Features**:
- User-specific channel groups: `user_{user_id}`
- Handles connect/disconnect lifecycle
- Receives and broadcasts messages

**WebSocket URL**: `ws/notifications/{user_id}/`

**Methods**:
- `connect()`: Joins user-specific channel group
- `disconnect()`: Leaves channel group
- `receive()`: Handles incoming WebSocket messages
- `notify_message()`: Sends notifications to client

#### 4. ASGI Configuration (`api/config/asgi.py`)

**Purpose**: Routes HTTP and WebSocket traffic

**Configuration**:
- Uses `ProtocolTypeRouter` to handle both HTTP and WebSocket
- WebSocket routes use `AuthMiddlewareStack`
- HTTP requests use standard Django ASGI application

---

## Video Upload Pipeline

### Architecture Flow

```
User Upload → Django API → Save to Storage → Celery Task
                                                   ↓
                                            FFmpeg Processing
                                                   ↓
                                    ┌──────────────┴──────────────┐
                                    ↓                             ↓
                            Generate HLS Chunks          Generate Thumbnail
                                    ↓                             ↓
                            Master Playlist (m3u8)      Thumbnail Image
                                    ↓                             ↓
                                    └──────────────┬──────────────┘
                                                   ↓
                                        Update Video Model
```

### Components

#### 1. Upload Endpoint (`api/apps/video/views.py`)

**Endpoint**: `POST /api/video/upload/`

**View**: `UploadVideo` (CreateAPIView)

**Process**:
1. Validates video file (max 100MB)
2. Saves video to storage with UUID-based path
3. Triggers Celery task `process_video.delay(video_id, file_path)`

**File Path Pattern**: `videos/{uuid}/{filename}`

#### 2. Video Transcoder (`api/apps/video/transcoder.py`)

**Purpose**: Processes video using FFmpeg to create adaptive bitrate streams

**Key Functions**:

##### `generate_thumbnail(video_file_path, thumbnail_path)`
- Extracts thumbnail at 3 seconds into video
- Quality: `-q:v 2`
- Output: JPEG format

##### `adaptive_variant(video_file_path, resolutions=[360, 720])`
- Creates multiple resolution variants (360p, 720p)
- Generates HLS (HTTP Live Streaming) chunks
- Creates master playlist for adaptive streaming

**FFmpeg Parameters**:
- Video codec: `libx264`
- Audio codec: `aac`
- HLS segment duration: 10 seconds
- HLS list size: 0 (no limit)
- Scaling: `-vf scale=-2:{resolution}` (maintains aspect ratio)

**Bandwidth Configuration**:
- 360p: 800,000 bps
- 720p: 2,500,000 bps
- Other: 5,000,000 bps

**Output Structure**:
```
videos/{uuid}/{video_name}/
├── 360p/
│   ├── index.m3u8 (playlist)
│   ├── index0.ts (segment)
│   ├── index1.ts (segment)
│   └── ...
├── 720p/
│   ├── index.m3u8
│   ├── index0.ts
│   └── ...
├── master.m3u8 (master playlist)
└── thumbnail.jpg
```

**Master Playlist Format**:
```m3u8
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
360p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720
720p/index.m3u8
```

##### `process_video(video_id, file_path)` (Celery Task)
- Asynchronous task using `@shared_task`
- Calls `adaptive_variant()` to process video
- Updates Video model with master playlist and thumbnail paths

#### 3. Video Model (`api/apps/video/models.py`)

**Fields**:
- `uuid`: Unique identifier for video organization
- `title`: Video title
- `file`: Original video file
- `master_playlist`: Path to HLS master playlist
- `thumbnail`: Path to thumbnail image
- `view_count`: Total view count
- `created_at`: Upload timestamp

---

## View Tracking System

### Architecture

```
User Plays Video → Generate Fingerprint → Redis Check
                                                 ↓
                                   ┌─────────────┴─────────────┐
                                   ↓                           ↓
                            New View?                    Rate Limited?
                                   ↓                           ↓
                          Increment Counter              Skip Update
                                   ↓
                          Mark as Dirty
                                   ↓
                          Celery Beat Sync (every 10 min)
                                   ↓
                          Update Database
```

### Components

#### 1. View Tracking Service (`api/apps/video/services.py`)

**Key Functions**:

##### `record_view(video_id, fingerprint)`
- Uses HyperLogLog for unique view detection
- Returns 1 if fingerprint is new, 0 if already counted
- Increments view counter if new
- Marks video as "dirty" for database sync

**Redis Keys**:
- `views:hll:{video_id}`: HyperLogLog set for unique fingerprints
- `views:count:{video_id}`: View counter
- `views:dirty_videos`: Set of videos needing DB sync

##### `track_view(request, video_id)`
- Generates viewer fingerprint
- Implements rate limiting (30 minutes per viewer)
- Calls `record_view()` to update counts

**Rate Limiting**:
- Key: `views:ratelimit:{fingerprint}`
- TTL: 1800 seconds (30 minutes)
- Prevents view spamming

#### 2. Fingerprint Generation (`api/apps/video/utils.py`)

**Function**: `get_viewer_fingerprint(request, video_id)`

**Components**:
- IP address (with X-Forwarded-For support)
- User-Agent string
- User ID (authenticated or 'anon')
- Video ID

**Algorithm**: SHA-256 hash of combined values

#### 3. View Sync Task (`api/apps/video/tasks.py`)

**Task**: `sync_video_views()` (Celery Beat)

**Schedule**: Every 10 minutes

**Process**:
1. Gets list of dirty videos from Redis
2. For each dirty video:
   - Gets view count from Redis
   - Resets Redis counter to 0
   - Updates database view_count
3. Clears dirty videos set

**Atomicity**: Uses `getset()` to safely read and reset counter

---

## Deployment

### Docker Compose Services

#### 1. Redis
- **Image**: redis:7
- **Port**: 6379
- **Purpose**: Caching, Celery broker, view tracking

#### 2. API (Django)
- **Build**: `./api/Dockerfile`
- **Port**: 8000
- **Command**: `python manage.py runserver 0.0.0.0:8000`
- **Depends**: redis
- **Volumes**: Code mounting for development

#### 3. Celery Worker
- **Build**: `./Dockerfile.worker`
- **Command**: `celery -A config worker -l info`
- **Depends**: redis
- **Features**: FFmpeg installed for video processing
- **Volumes**: Code + media storage

#### 4. Celery Beat
- **Build**: `./Dockerfile.worker`
- **Command**: `celery -A config beat -l info`
- **Depends**: redis
- **Purpose**: Scheduled tasks (view sync)

#### 5. RabbitMQ
- **Image**: rabbitmq:3.13-management
- **Ports**: 5672 (AMQP), 15672 (Management UI)
- **Credentials**: admin/admin
- **Volume**: Persistent data storage

#### 6. Notification Worker
- **Build**: `./notification_worker`
- **Command**: `python consumer.py`
- **Depends**: rabbitmq
- **Purpose**: Consumes RabbitMQ messages, forwards to WebSocket

### Dockerfiles

#### API Dockerfile (`api/Dockerfile`)
- Base: python:3.10-slim
- Dependencies: Pillow, Django, etc.
- Default: Daphne ASGI server

#### Worker Dockerfile (`Dockerfile.worker`)
- Base: python:3.11-slim
- Dependencies: FFmpeg + Python packages
- Purpose: Celery worker with video processing

---

## API Endpoints

### Video Endpoints

#### 1. List Videos
- **Method**: GET
- **URL**: `/api/video/`
- **Response**: List of all videos

#### 2. Upload Video
- **Method**: POST
- **URL**: `/api/video/upload/`
- **Body**: multipart/form-data
  - `title`: string
  - `file`: video file (max 100MB)
- **Response**: Created video object
- **Async**: Triggers video processing

#### 3. Play Video
- **Method**: GET
- **URL**: `/api/video/play/?video_id={id}`
- **Response**: Video details with master playlist
- **Side Effect**: Increments view count

#### 4. Like Video
- **Method**: POST
- **URL**: `/api/video/like/`
- **Side Effect**: Publishes notification to RabbitMQ

### WebSocket Endpoints

#### 1. Notifications
- **URL**: `ws://host/ws/notifications/{user_id}/`
- **Purpose**: Real-time notifications
- **Auto-connects to user-specific channel group

---

## File Structure

```
VDO-backend/
├── api/
│   ├── apps/
│   │   ├── video/
│   │   │   ├── models.py          # Video model
│   │   │   ├── views.py           # API views
│   │   │   ├── urls.py            # URL routing
│   │   │   ├── serializers.py     # DRF serializers
│   │   │   ├── transcoder.py      # FFmpeg processing
│   │   │   ├── publishers.py      # RabbitMQ publisher
│   │   │   ├── services.py        # View tracking logic
│   │   │   ├── tasks.py           # Celery tasks
│   │   │   ├── utils.py           # Helper functions
│   │   │   └── templates/video/   # Video player template
│   │   └── notification/
│   │       ├── consumers.py       # WebSocket consumer
│   │       └── routing.py         # WebSocket routing
│   ├── config/
│   │   ├── settings.py            # Django settings
│   │   ├── celery.py              # Celery configuration
│   │   ├── asgi.py                # ASGI config (WebSocket)
│   │   ├── urls.py                # Main URL config
│   │   └── wsgi.py                # WSGI config
│   ├── manage.py                  # Django management
│   ├── requirements.txt           # Python dependencies
│   └── Dockerfile                 # API container image
├── notification_worker/
│   └── consumer.py                # RabbitMQ consumer
├── Dockerfile.worker              # Worker container image
├── docker-compose.yml             # Multi-container orchestration
└── .gitignore
```

---

## Environment Configuration

### Required Services

1. **Redis**: For Celery broker and view tracking
2. **RabbitMQ**: For notification system
3. **FFmpeg**: For video processing (installed in worker)

### Environment Variables

Set in `docker-compose.yml`:
- `CELERY_BROKER_URL`: redis://redis:6379/1
- `CELERY_RESULT_BACKEND`: redis://redis:6379/1
- `RABBITMQ_DEFAULT_USER`: admin
- `RABBITMQ_DEFAULT_PASS`: admin

---

## Key Features

### 1. Adaptive Bitrate Streaming
- Automatic multi-resolution generation (360p, 720p)
- HLS format for HTTP-based streaming
- Master playlist for client-side quality selection

### 2. Real-time Notifications
- RabbitMQ for reliable message delivery
- WebSocket for instant client updates
- User-specific notification targeting

### 3. Scalable View Tracking
- Redis-based counting (high performance)
- HyperLogLog for unique view detection
- Rate limiting to prevent spam
- Periodic database sync (Celery Beat)

### 4. Asynchronous Processing
- Celery for background video processing
- Non-blocking API responses
- Automatic retry on failure

---

## Development Workflow

### Starting the Application

```bash
# Build and start all services
docker-compose up --build

# Start individual services
docker-compose up api redis rabbitmq celery_worker celery_beat notification_worker
```

### Access Points

- **API**: http://localhost:8000
- **RabbitMQ Management**: http://localhost:15672 (admin/admin)
- **Redis**: localhost:6379

### Monitoring

- **Celery Worker Logs**: `docker-compose logs celery_worker`
- **Notification Worker Logs**: `docker-compose logs notification_worker`
- **API Logs**: `docker-compose logs api`

---

## Security Considerations

### Current State
- RabbitMQ credentials hardcoded (should use environment variables)
- No authentication on video endpoints
- Rate limiting implemented for views
- File size validation (100MB limit)

### Recommendations
1. Move sensitive credentials to environment variables
2. Implement JWT authentication for API endpoints
3. Add HTTPS/TLS for production
4. Implement user authorization for video access
5. Add CSRF protection for WebSocket
6. Sanitize video file uploads

---

## Performance Optimizations

1. **HLS Streaming**: Chunked video for better buffering
2. **Redis Caching**: Fast view counting without DB hits
3. **HyperLogLog**: Memory-efficient unique counting
4. **Async Processing**: Non-blocking video transcoding
5. **Rate Limiting**: Prevents Redis overload from spam views

---

## Troubleshooting

### RabbitMQ Connection Issues
- Check RabbitMQ is running: `docker-compose ps rabbitmq`
- Verify credentials in publishers.py and consumer.py
- Check RabbitMQ logs: `docker-compose logs rabbitmq`

### Video Processing Failures
- Verify FFmpeg is installed in worker container
- Check worker logs: `docker-compose logs celery_worker`
- Ensure media volume is mounted correctly

### WebSocket Connection Issues
- Verify ASGI server is running (not WSGI)
- Check routing configuration in asgi.py
- Ensure channels_redis is configured correctly

### View Count Sync Issues
- Check Redis connection
- Verify Celery Beat is running
- Check sync task logs in Celery Beat logs
