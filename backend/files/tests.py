from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User # Though not used for auth, good for consistency if needed later
from .models import File
from datetime import datetime, date, timedelta
import os
import shutil
from django.conf import settings
from django.utils import timezone # Added for timezone.utc

# Helper function to create a file for testing
def create_test_file(filename="test.txt", content=b"hello world", content_type="text/plain"):
    return SimpleUploadedFile(name=filename, content=content, content_type=content_type)

class FileAPITests(APITestCase):

    def setUp(self):
        # Create a test user if needed for authenticated endpoints, not strictly necessary for current tests
        # self.user = User.objects.create_user(username='testuser', password='testpassword')
        # self.client.login(username='testuser', password='testpassword') # If login is required

        # Ensure the MEDIA_ROOT for tests is clean before each test
        # This is important for file storage tests to avoid interference between tests.
        # Note: This assumes MEDIA_ROOT is set and is a dedicated test directory.
        # Be cautious if MEDIA_ROOT is your actual development media folder.
        # For this project, the default MEDIA_ROOT is 'media/', which is fine for testing.
        test_media_root = os.path.join(settings.MEDIA_ROOT) # MEDIA_ROOT is usually 'media/'
        if os.path.exists(test_media_root):
            # Remove everything inside the test media root
            for item_name in os.listdir(test_media_root):
                item_path = os.path.join(test_media_root, item_name)
                if os.path.isdir(item_path) and item_name != 'test_uploads_placeholder': # Avoid removing placeholder if any
                    shutil.rmtree(item_path)
                elif os.path.isfile(item_path):
                    os.remove(item_path)
        else:
            os.makedirs(test_media_root, exist_ok=True)
            # Create a placeholder file so git tracks the directory, if needed for your setup
            # with open(os.path.join(test_media_root, 'test_uploads_placeholder.txt'), 'w') as f:
            #     f.write('This folder is for test uploads.')


    def tearDown(self):
        # Clean up files created during tests
        # This is important to ensure tests are idempotent and don't leave artifacts.
        # Similar to setUp, be cautious with the MEDIA_ROOT.
        test_media_root = os.path.join(settings.MEDIA_ROOT)
        # A more robust cleanup would involve tracking created files and deleting them specifically,
        # or ensuring the test runner uses a temporary MEDIA_ROOT that's automatically cleaned.
        # For now, we'll clear it as in setUp.
        if os.path.exists(test_media_root):
            for item_name in os.listdir(test_media_root):
                item_path = os.path.join(test_media_root, item_name)
                # Avoid deleting the base 'files' directory if it's directly under MEDIA_ROOT
                # and your FileField upload_to is just 'files/'
                if item_name == File._meta.get_field('file').upload_to: # checks if item_name is 'files'
                    # If 'files' is the upload_to directory, clean inside it
                    upload_to_dir = item_path
                    if os.path.isdir(upload_to_dir):
                         for sub_item_name in os.listdir(upload_to_dir):
                            sub_item_path = os.path.join(upload_to_dir, sub_item_name)
                            if os.path.isdir(sub_item_path):
                                shutil.rmtree(sub_item_path)
                            else:
                                os.remove(sub_item_path)
                    # Do not remove the 'files' directory itself if it's the direct upload_to target
                elif os.path.isdir(item_path) and item_name != 'test_uploads_placeholder':
                    shutil.rmtree(item_path)
                elif os.path.isfile(item_path):
                    os.remove(item_path)
        
        # Clear all File objects from the database
        File.objects.all().delete()


    def test_file_upload_and_deduplication(self):
        """
        Tests single file upload and subsequent deduplication of the same content.
        """
        url = reverse('file-list') # Assumes 'file-list' is the name for FileViewSet list/create
        
        # 1. Upload a file for the first time
        file_content = b"Unique content for deduplication test"
        original_upload_name = "original.txt"
        mock_file1 = create_test_file(filename=original_upload_name, content=file_content)
        
        response1 = self.client.post(url, {'file': mock_file1}, format='multipart')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response1.data['is_duplicate'])
        original_file_id = response1.data['id']
        original_file_instance = File.objects.get(id=original_file_id)
        self.assertFalse(original_file_instance.is_duplicate)
        self.assertIsNone(original_file_instance.original_file)
        
        # Store the path of the first uploaded file
        original_file_path = original_file_instance.file.name
        self.assertTrue(os.path.exists(os.path.join(settings.MEDIA_ROOT, original_file_path)))

        # 2. Upload the exact same file content again (different filename)
        duplicate_upload_name = "duplicate.txt"
        mock_file2 = create_test_file(filename=duplicate_upload_name, content=file_content) # Same content
        
        response2 = self.client.post(url, {'file': mock_file2}, format='multipart')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response2.data['is_duplicate'])
        duplicate_file_id = response2.data['id']
        duplicate_file_instance = File.objects.get(id=duplicate_file_id)

        # Verify deduplication
        self.assertTrue(duplicate_file_instance.is_duplicate)
        self.assertIsNotNone(duplicate_file_instance.original_file)
        # Compare UUID objects directly, or ensure both are strings. original_file_id is a string from response.data.
        # original_file_instance.id is a UUID object.
        self.assertEqual(duplicate_file_instance.original_file.id, original_file_instance.id)
        
        # Verify the file path on disk is the same
        self.assertEqual(duplicate_file_instance.file.name, original_file_path)
        
        # Verify that only one file object for this content is marked as not a duplicate
        files_with_same_hash = File.objects.filter(sha256=original_file_instance.sha256)
        self.assertEqual(files_with_same_hash.filter(is_duplicate=False).count(), 1)
        self.assertEqual(files_with_same_hash.filter(is_duplicate=True).count(), 1)

        # Verify only one actual file exists in storage for this content
        # This is implicitly tested by duplicate_file_instance.file.name == original_file_path
        # and original_file_path still existing. If mock_file2 created a new file, its path would be different.
        # A more direct check would be to list files in the directory, but that can be complex.
        # The current checks on model fields are usually sufficient.

    def test_storage_stats_endpoint(self):
        """
        Tests the /api/files/stats/ endpoint.
        """
        stats_url = reverse('file-stats') # Assumes 'file-stats' is the name for the stats action

        # Test with no files
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_physical_size'], 0)
        self.assertEqual(response.data['total_logical_size'], 0)
        self.assertEqual(response.data['saved_space'], 0)
        self.assertEqual(response.data['deduplicated_files_count'], 0)
        self.assertEqual(response.data['original_files_count'], 0)
        self.assertEqual(response.data['total_files_count'], 0)

        # Test with only unique files
        file_content1 = b"File content 1"
        file1_size = len(file_content1)
        mock_file1 = create_test_file(filename="file1.txt", content=file_content1)
        self.client.post(reverse('file-list'), {'file': mock_file1}, format='multipart')

        file_content2 = b"File content 2, slightly longer"
        file2_size = len(file_content2)
        mock_file2 = create_test_file(filename="file2.txt", content=file_content2)
        self.client.post(reverse('file-list'), {'file': mock_file2}, format='multipart')
        
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_total_size = file1_size + file2_size
        self.assertEqual(response.data['total_physical_size'], expected_total_size)
        self.assertEqual(response.data['total_logical_size'], expected_total_size)
        self.assertEqual(response.data['saved_space'], 0)
        self.assertEqual(response.data['deduplicated_files_count'], 0)
        self.assertEqual(response.data['original_files_count'], 2)
        self.assertEqual(response.data['total_files_count'], 2)

        # Test with some duplicate files
        # file1 (original.txt, content1) is already uploaded
        # Upload file1 content again as duplicate3.txt
        mock_file_dup = create_test_file(filename="duplicate3.txt", content=file_content1) # Same as file1
        self.client.post(reverse('file-list'), {'file': mock_file_dup}, format='multipart')

        # Upload a new unique file (file3.txt)
        file_content3 = b"File content 3, unique again"
        file3_size = len(file_content3)
        mock_file3 = create_test_file(filename="file3.txt", content=file_content3)
        self.client.post(reverse('file-list'), {'file': mock_file3}, format='multipart')

        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Physical size: file1 + file2 + file3 (duplicate of file1 doesn't add to physical size)
        expected_physical_size = file1_size + file2_size + file3_size
        # Logical size: file1 + file2 + file1_duplicate + file3
        expected_logical_size = file1_size + file2_size + file1_size + file3_size
        
        self.assertEqual(response.data['total_physical_size'], expected_physical_size)
        self.assertEqual(response.data['total_logical_size'], expected_logical_size)
        self.assertEqual(response.data['saved_space'], expected_logical_size - expected_physical_size)
        self.assertEqual(response.data['deduplicated_files_count'], 1) # duplicate3.txt
        self.assertEqual(response.data['original_files_count'], 3) # file1.txt, file2.txt, file3.txt
        self.assertEqual(response.data['total_files_count'], 4) # All File objects

    def test_search_filters(self):
        """
        Tests the search functionality with various filters.
        """
        search_url = reverse('file-search') # Assumes 'file-search' is the name for the search action
        upload_url = reverse('file-list')

        # Populate database
        # Dates need to be datetime objects for the model, then converted to date for filtering if needed
        # For uploaded_at, Django model's auto_now_add=True will handle it, but we need to control it for tests.
        # So, we will manually create File objects for precise date control.
        
        # To control uploaded_at, we need to save File objects directly, not through the API for setup.
        # Or, if using API, we'd need to mock `timezone.now()` which can be complex.
        # Let's create them directly for simplicity in controlling dates.
        
        # File 1: name_alpha.txt, text/plain, 10 bytes, 2023-01-15
        f1_content = b"ten bytes!"
        f1_size = len(f1_content)
        f1_sha256 = "mocksha1" # In real scenario, this would be calculated. For direct save, provide one.
        file1 = File.objects.create(
            original_filename="name_alpha.txt", file_type="text/plain", size=f1_size,
            sha256=f1_sha256, is_duplicate=False,
            file=SimpleUploadedFile("name_alpha.txt", f1_content, "text/plain")
        )
        file1.uploaded_at = datetime(2023, 1, 15, 10, 0, 0, tzinfo=timezone.utc) # Use timezone.utc
        file1.save()

        # File 2: name_beta.log, text/plain, 20 bytes, 2023-01-20
        f2_content = b"twenty bytes content"
        f2_size = len(f2_content)
        f2_sha256 = "mocksha2"
        file2 = File.objects.create(
            original_filename="name_beta.log", file_type="text/plain", size=f2_size,
            sha256=f2_sha256, is_duplicate=False,
            file=SimpleUploadedFile("name_beta.log", f2_content, "text/plain")
        )
        file2.uploaded_at = datetime(2023, 1, 20, 12, 0, 0, tzinfo=timezone.utc) # Use timezone.utc
        file2.save()

        # File 3: image_gamma.jpg, image/jpeg, 30 bytes, 2023-01-20 (same day as file2, different time)
        f3_content = b"thirty bytes image content....."
        f3_size = len(f3_content)
        f3_sha256 = "mocksha3"
        file3 = File.objects.create(
            original_filename="image_gamma.jpg", file_type="image/jpeg", size=f3_size,
            sha256=f3_sha256, is_duplicate=False,
            file=SimpleUploadedFile("image_gamma.jpg", f3_content, "image/jpeg")
        )
        file3.uploaded_at = datetime(2023, 1, 20, 18, 0, 0, tzinfo=timezone.utc) # Use timezone.utc
        file3.save()

        # File 4: data_delta.dat, application/octet-stream, 10 bytes, 2023-01-25
        f4_content = b"other data" # size should be 10 to match file1
        f4_size = len(f4_content)
        f4_sha256 = "mocksha4"
        file4 = File.objects.create(
            original_filename="data_delta.dat", file_type="application/octet-stream", size=f4_size,
            sha256=f4_sha256, is_duplicate=False,
            file=SimpleUploadedFile("data_delta.dat", f4_content, "application/octet-stream")
        )
        file4.uploaded_at = datetime(2023, 1, 25, 9, 0, 0, tzinfo=timezone.utc) # Use timezone.utc
        file4.save()


        # Test date_to filter (Corrected logic: includes files *on* date_to)
        response = self.client.get(search_url, {'date_to': '2023-01-20'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data
        self.assertEqual(len(results), 3) # file1, file2, file3
        result_ids = {item['id'] for item in results}
        self.assertIn(str(file1.id), result_ids) # Compare string UUIDs
        self.assertIn(str(file2.id), result_ids) # Compare string UUIDs
        self.assertIn(str(file3.id), result_ids) # Compare string UUIDs
        self.assertNotIn(str(file4.id), result_ids) # Compare string UUIDs; file4 is on 2023-01-25

        # Test date_from filter
        response = self.client.get(search_url, {'date_from': '2023-01-20'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data
        self.assertEqual(len(results), 3) # file2, file3, file4
        result_ids = {item['id'] for item in results}
        self.assertIn(str(file2.id), result_ids) # Compare string UUIDs
        self.assertIn(str(file3.id), result_ids) # Compare string UUIDs
        self.assertIn(str(file4.id), result_ids) # Compare string UUIDs

        # Test filename filter (partial match)
        response = self.client.get(search_url, {'filename': 'name_'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) # name_alpha, name_beta
        result_ids = {item['id'] for item in response.data}
        self.assertIn(str(file1.id), result_ids) # Compare string UUIDs
        self.assertIn(str(file2.id), result_ids) # Compare string UUIDs

        # Test filename filter (full match)
        response = self.client.get(search_url, {'filename': 'image_gamma.jpg'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(file3.id)) # Compare string UUIDs
        
        # Test file_type filter
        response = self.client.get(search_url, {'file_type': 'text/plain'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) # file1, file2
        result_ids = {item['id'] for item in response.data}
        self.assertIn(str(file1.id), result_ids) # Compare string UUIDs
        self.assertIn(str(file2.id), result_ids) # Compare string UUIDs

        # Test size_min filter
        response = self.client.get(search_url, {'size_min': 15})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) # file2 (20b), file3 (30b)
        result_ids = {item['id'] for item in response.data}
        self.assertIn(str(file2.id), result_ids) # Compare string UUIDs
        self.assertIn(str(file3.id), result_ids) # Compare string UUIDs

        # Test size_max filter
        response = self.client.get(search_url, {'size_max': 15})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # file1 (10b), file4 (10b)
        self.assertEqual(len(response.data), 2) 
        result_ids = {item['id'] for item in response.data}
        self.assertIn(str(file1.id), result_ids) # Compare string UUIDs
        self.assertIn(str(file4.id), result_ids) # Compare string UUIDs


        # Test combination of filters: filename and date_to
        response = self.client.get(search_url, {'filename': 'name', 'date_to': '2023-01-15'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1) # file1 (name_alpha.txt on 2023-01-15)
        self.assertEqual(response.data[0]['id'], str(file1.id)) # Compare string UUIDs
        
        # Test combination: file_type and size_min
        response = self.client.get(search_url, {'file_type': 'text/plain', 'size_min': '15'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1) # file2 (name_beta.log, 20 bytes)
        self.assertEqual(response.data[0]['id'], str(file2.id)) # Compare string UUIDs

        # Test search with no matching results
        response = self.client.get(search_url, {'filename': 'nonexistentfile'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

        # Test search with invalid size parameter (e.g. string)
        response = self.client.get(search_url, {'size_min': 'notanumber'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

        response = self.client.get(search_url, {'size_max': 'anotherinvalid'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

        # Test search with invalid date format
        response = self.client.get(search_url, {'date_from': '01-01-2023'}) # wrong format
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        
        response = self.client.get(search_url, {'date_to': '2023/01/01'}) # wrong format
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

# Placeholder for more tests if needed
# class AnotherFileTest(APITestCase):
#     pass

# To ensure tests are run, this file should end with tests.py and be in an app's directory.
# Django's test runner will automatically discover tests in files named tests.py.
# Run with: python manage.py test files --settings=your_project.settings_test (if you have specific test settings)
# or just 'python manage.py test files' if your default settings are configured for testing.
# Make sure MEDIA_ROOT is properly configured for tests, ideally to a temporary directory.
# For this project, we assume settings.py handles MEDIA_ROOT appropriately.
# The setUp and tearDown methods attempt to manage files in MEDIA_ROOT/files/
# based on the model's upload_to='files/'.

# Note on TIME_ZONE:
# For date/time comparisons to work reliably, especially with auto_now_add=True or when
# manually setting datetime fields, ensure that:
# 1. Your Django project has USE_TZ = True (default and recommended).
# 2. You use timezone-aware datetime objects when creating/comparing data in tests.
#    (e.g., by using django.utils.timezone.now() or datetime(..., tzinfo=...))
# The tests above use datetime with tzinfo=settings.TIME_ZONE. If TIME_ZONE is not set,
# this might default to UTC if USE_TZ is True, or naive datetimes if USE_TZ is False.
# For consistency, explicitly set settings.TIME_ZONE or use django.utils.timezone.utc.
# The File model's `uploaded_at` uses `auto_now_add=True`, which makes it timezone-aware
# if USE_TZ=True. The manual setting of `uploaded_at` in `test_search_filters`
# needs to be consistent with this. Using `settings.TIME_ZONE` (which defaults to 'UTC' if not set, assuming USE_TZ=True)
# is a reasonable approach for tests.
