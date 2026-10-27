from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.response import Response
from apps.video.models import Video
from apps.video.serilaizers import VideoSerializer,CreateVideoSerializer
from apps.video.transcoder import process_video
from django.views import View
from apps.video.services import track_view
# Create your views here.


# class VideoView(View):
#     def get(self,request,uuid):
#         try:
#             video = Video.objects.get(uuid=uuid)
#         except:
#             return JsonResponse({"error": "Video not found"}, status=404)
#         try:
#             track_view(request, video.id)
#         except Exception as e:
#             print(f'Something wrong:{e}')
#             return JsonResponse({"error": "Something went wrong"}, status=500)
#         context = {
#             "master_file":f"/media/{video.master_playlist}"
#         }
#         return render(request,'video/index.html',context)

class VideoView(APIView):
    serializer_class = VideoSerializer
    
    def get(self,request):
        try:
            video_id = request.query_params.get('video_id')
            video = Video.objects.get(id=video_id)
            track_view(request, video.id)
            serializer = VideoSerializer(video)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=404)



class VideoList(generics.ListAPIView):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer    

class UploadVideo(generics.CreateAPIView):
    queryset = Video.objects.all()
    serializer_class =  CreateVideoSerializer

    def perform_create(self, serializer):
        print("Uploading the video.....................")
        video = serializer.save()
        print("uploading done...........")
        process_video.delay(video.id, video.file.path)

from rest_framework.permissions import AllowAny
from .publishers import publish_video_like_notification
from django.views.decorators.csrf import csrf_exempt

class LikeVideo(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    def post(self, request):

        try:

            video_id = request.data.get('video_id')
            send_to = request.data.get('send_to')
            send_from = 0
            payload = request.data.get('payload')

            # {
            #     "type": "notify_message",
            #     "data": {
            #         "send_to": 1,
            #         "send_from": 3,
            #         "video_id": 23,
            #         "payload": {
            #             "message": "User 3 liked your video"
            #         }
            #     }
            # }

            if not video_id or not send_to:
                return Response(
                    {"error": "video_id and send_to required"},
                    status=400
                )

            data = {
                "type": "video.liked",
                "data": {
                    "send_to": send_to,
                    "send_from": send_from,
                    "video_id": video_id,
                    "payload": payload
                }
            }

            publish_video_like_notification(data)

            return Response({
                "message": "Video liked successfully"
            })

        except Exception as e:

            return Response({
                "error": str(e)
            }, status=500)

    def get(self, request):
        return Response({
            "message": "Video liked successfully"
        })