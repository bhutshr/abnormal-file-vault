from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import File
from .serializers import FileSerializer
import hashlib
from django.db.models import Q
from datetime import datetime

# Create your views here.

class FileViewSet(viewsets.ModelViewSet):
    queryset = File.objects.all()
    serializer_class = FileSerializer

    @action(detail=False, methods=['get'])
    def search(self, request):
        queryset = File.objects.all()
        
        filename = request.query_params.get('filename', None)
        file_type = request.query_params.get('file_type', None)
        size_min = request.query_params.get('size_min', None)
        size_max = request.query_params.get('size_max', None)
        date_from_str = request.query_params.get('date_from', None)
        date_to_str = request.query_params.get('date_to', None)

        if filename:
            queryset = queryset.filter(original_filename__icontains=filename)
        
        if file_type:
            queryset = queryset.filter(file_type=file_type)
        
        if size_min:
            try:
                queryset = queryset.filter(size__gte=int(size_min))
            except ValueError:
                return Response({'error': 'Invalid size_min format'}, status=status.HTTP_400_BAD_REQUEST)
        
        if size_max:
            try:
                queryset = queryset.filter(size__lte=int(size_max))
            except ValueError:
                return Response({'error': 'Invalid size_max format'}, status=status.HTTP_400_BAD_REQUEST)
        
        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
                queryset = queryset.filter(uploaded_at__gte=date_from)
            except ValueError:
                return Response({'error': 'Invalid date_from format (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
                # To include the whole day, filter up to the end of that day if it's a date without time
                # If uploaded_at is a DateTimeField, this approach is fine.
                # For more precision (e.g., end of day), one might use uploaded_at__lte=datetime.combine(date_to, datetime.max.time())
                # but for simplicity, __lte with date should work for most cases if time component is not critical.
                queryset = queryset.filter(uploaded_at__lte=date_to)
            except ValueError:
                return Response({'error': 'Invalid date_to format (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate SHA256 hash
        sha256 = hashlib.sha256()
        for chunk in file_obj.chunks():
            sha256.update(chunk)
        sha256_hash = sha256.hexdigest()
        
        # Reset file pointer for potential re-read
        file_obj.seek(0)

        # Check for existing non-duplicate file with the same hash
        original_file = File.objects.filter(sha256=sha256_hash, is_duplicate=False).first()

        if original_file:
            # It's a duplicate
            duplicate_instance = File(
                original_filename=file_obj.name,
                file_type=file_obj.content_type,
                size=file_obj.size,
                sha256=sha256_hash,
                is_duplicate=True,
                original_file=original_file
            )
            # Assign the FileField from the original, not the uploaded file_obj
            duplicate_instance.file = original_file.file 
            duplicate_instance.save() 
            
            serializer = self.get_serializer(duplicate_instance)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        else:
            # It's a new file
            data = {
                'file': file_obj, # The actual uploaded file
                'original_filename': file_obj.name,
                'file_type': file_obj.content_type,
                'size': file_obj.size,
                'sha256': sha256_hash,
                # 'is_duplicate' will default to False as per model definition
            }
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer) # This will save file_obj to a new path
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
