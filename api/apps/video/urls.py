from django.urls import path
from apps.video import views

urlpatterns=[
    path('',views.VideoList.as_view(),name='video'),
    path('upload/',views.UploadVideo.as_view(),name='upload'),
    path('play/',views.VideoView.as_view(),name='play'),
    path('like/',views.LikeVideo.as_view(),name='like'),
    # path('play/<str:uuid>/',views.VideoView.as_view(),name='play'),
]
