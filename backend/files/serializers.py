from rest_framework import serializers
from .models import File

class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ['id', 'file', 'original_filename', 'file_type', 'size', 'uploaded_at', 'sha256', 'is_duplicate', 'original_file']
        # sha256 is removed from read_only_fields to allow it to be set on creation of original files
        read_only_fields = ['id', 'uploaded_at', 'is_duplicate', 'original_file']