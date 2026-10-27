from .models import Video
from rest_framework import serializers

class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = '__all__'

class CreateVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['title','file']
        
    def validate_file(self, value):
        if value.size > 100 * 1024 * 1024:
            raise serializers.ValidationError("File size must be less than 100MB")
        return value
