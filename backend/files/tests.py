import os
import shutil
import hashlib
from datetime import datetime, timedelta

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import override_settings

from rest_framework.test import APITestCase
from rest_framework import status

from .models import File

# Use a temporary media root for tests
TEST_MEDIA_ROOT = os.path.join(settings.BASE_DIR, 'test_media_root_files')

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class FileDeduplicationTests(APITestCase):
    def setUp(self):
        # Ensure the test media directory exists and is empty
        if not os.path.exists(TEST_MEDIA_ROOT):
            os.makedirs(TEST_MEDIA_ROOT)
        else:
            # Clean up any old test files
            for filename in os.listdir(TEST_MEDIA_ROOT):
                file_path = os.path.join(TEST_MEDIA_ROOT, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f'Failed to delete {file_path}. Reason: {e}')
        
        self.upload_url = reverse('file-list') # Assumes 'file-list' is the name for FileViewSet list/create

    def tearDown(self):
        # Clean up the test media directory
        if os.path.exists(TEST_MEDIA_ROOT):
            shutil.rmtree(TEST_MEDIA_ROOT)

    def _upload_file(self, filename="test.txt", content=b"hello world", content_type="text/plain"):
        file_content = SimpleUploadedFile(filename, content, content_type=content_type)
        return self.client.post(self.upload_url, {'file': file_content}, format='multipart')

    def test_new_file_upload(self):
        """Test uploading a new, unique file."""
        content = b"This is a unique file."
        response = self._upload_file("unique.txt", content)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(File.objects.count(), 1)
        
        file_obj = File.objects.first()
        self.assertFalse(file_obj.is_duplicate)
        self.assertIsNotNone(file_obj.sha256)
        self.assertIsNone(file_obj.original_file)
        
        # Check SHA256
        sha256 = hashlib.sha256()
        sha256.update(content)
        expected_sha256 = sha256.hexdigest()
        self.assertEqual(file_obj.sha256, expected_sha256)
        
        # Check physical file exists
        self.assertTrue(os.path.exists(file_obj.file.path))
        # Ensure it's in our test media root
        self.assertTrue(file_obj.file.path.startswith(TEST_MEDIA_ROOT))


    def test_duplicate_file_upload(self):
        """Test uploading a file that is a duplicate of an existing one."""
        content = b"This is the first file."
        filename = "first_file.txt"
        
        # Upload original file
        response1 = self._upload_file(filename, content)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        original_file_obj = File.objects.get(sha256=response1.data['sha256'])
        
        # Upload the same file again
        response2 = self._upload_file("duplicate_file.txt", content) # Different name, same content
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(File.objects.count(), 2) # Two DB entries
        
        duplicate_file_obj = File.objects.get(id=response2.data['id'])
        
        self.assertTrue(duplicate_file_obj.is_duplicate)
        self.assertEqual(duplicate_file_obj.sha256, original_file_obj.sha256)
        self.assertEqual(duplicate_file_obj.original_file, original_file_obj)
        
        # Assert that a new physical file was NOT saved for the duplicate
        self.assertEqual(duplicate_file_obj.file.path, original_file_obj.file.path)
        
        # Verify physical file count (should still be 1 unique file in uploads folder)
        # Note: file_upload_path generates UUIDs, so we count files in the 'uploads' subdir of TEST_MEDIA_ROOT
        uploads_dir = os.path.join(TEST_MEDIA_ROOT, 'uploads')
        if os.path.exists(uploads_dir):
             self.assertEqual(len(os.listdir(uploads_dir)), 1)
        else:
            # If the first file upload failed to create the directory (which it shouldn't)
            self.fail("Uploads directory was not created.")


    def test_multiple_duplicate_uploads(self):
        """Test uploading multiple duplicates of the same file."""
        content = b"Content for multiple duplicates test."
        filename_orig = "multi_orig.txt"
        
        # Upload original
        response_orig = self._upload_file(filename_orig, content)
        self.assertEqual(response_orig.status_code, status.HTTP_201_CREATED)
        original_file_obj = File.objects.get(id=response_orig.data['id'])
        
        # Upload first duplicate
        response_dup1 = self._upload_file("multi_dup1.txt", content)
        self.assertEqual(response_dup1.status_code, status.HTTP_201_CREATED)
        dup1_obj = File.objects.get(id=response_dup1.data['id'])
        
        # Upload second duplicate
        response_dup2 = self._upload_file("multi_dup2.txt", content)
        self.assertEqual(response_dup2.status_code, status.HTTP_201_CREATED)
        dup2_obj = File.objects.get(id=response_dup2.data['id'])
        
        self.assertEqual(File.objects.count(), 3)
        
        # Check first duplicate
        self.assertTrue(dup1_obj.is_duplicate)
        self.assertEqual(dup1_obj.original_file, original_file_obj)
        self.assertEqual(dup1_obj.file.path, original_file_obj.file.path)
        
        # Check second duplicate
        self.assertTrue(dup2_obj.is_duplicate)
        self.assertEqual(dup2_obj.original_file, original_file_obj)
        self.assertEqual(dup2_obj.file.path, original_file_obj.file.path)

        uploads_dir = os.path.join(TEST_MEDIA_ROOT, 'uploads')
        if os.path.exists(uploads_dir):
             self.assertEqual(len(os.listdir(uploads_dir)), 1) # Still only one physical file
        else:
            self.fail("Uploads directory was not created.")


class FileSearchApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a diverse set of File objects
        cls.search_url = reverse('file-search') # Assumes 'file-search' is the name for the search action

        # To properly test file paths and ensure files exist for these test data,
        # we need to "upload" them. We can't just create File model instances directly
        # if we want the file.path to be meaningful and point to an actual (test) file.
        # However, for API filtering tests based on metadata, direct creation or mocking storage might be simpler.
        # For now, let's create them with minimal file content, assuming the search view doesn't
        # heavily rely on actual file content for these metadata filters.
        # A proper setup would involve using SimpleUploadedFile for each if file.path matters.
        # For this example, we'll create the files and manually set their paths to something nominal,
        # or rely on the default behavior of FileField which might not save if not explicitly told to.
        # This part needs careful consideration of how FileViewSet.search interacts with file paths.
        # For simplicity, we'll focus on metadata.

        # Create a temporary directory for test files for setUpTestData
        # This is tricky because @override_settings for MEDIA_ROOT applies per-test-method or per-class
        # for APITestCase, not necessarily for setUpTestData in the same way.
        # For robust file path testing in setUpTestData, one might need a more complex setup
        # or to ensure that file creation here uses the overridden TEST_MEDIA_ROOT.
        # Let's assume direct File object creation is sufficient for metadata search tests.

        cls.file1 = File.objects.create(
            original_filename="report_final.pdf",
            file_type="application/pdf",
            size=1024 * 500,  # 500KB
            uploaded_at=datetime(2023, 1, 15, 10, 0, 0),
            sha256="sha256_report_final_pdf" # Mocked SHA
        )
        # Manually save a dummy file for file1 to make its path valid for tests if needed
        # This is a simplified approach for setUpTestData.
        dummy_content = b"dummy pdf content"
        suf = SimpleUploadedFile(cls.file1.original_filename, dummy_content, content_type=cls.file1.file_type)
        # The default storage will save this under the MEDIA_ROOT active during this phase.
        # If TEST_MEDIA_ROOT is not active here, it goes to the real one.
        # This highlights a complexity of file management in setUpTestData.
        # A better approach for tests needing real files is often to create them in setUp of the test class.
        # For now, we'll proceed assuming metadata is primary for search.
        # cls.file1.file.save(cls.file1.original_filename, suf, save=True) # This would save a file

        cls.file2 = File.objects.create(
            original_filename="image_profile.jpg",
            file_type="image/jpeg",
            size=1024 * 150,  # 150KB
            uploaded_at=datetime(2023, 3, 20, 14, 30, 0),
            sha256="sha256_image_profile_jpg"
        )
        # cls.file2.file.save("image_profile.jpg", SimpleUploadedFile(...), save=True)


        cls.file3 = File.objects.create(
            original_filename="archive_data.zip",
            file_type="application/zip",
            size=1024 * 1024 * 2,  # 2MB
            uploaded_at=datetime(2023, 5, 10, 18, 45, 0),
            sha256="sha256_archive_data_zip"
        )

        cls.file4 = File.objects.create(
            original_filename="report_draft.pdf", # Another PDF
            file_type="application/pdf",
            size=1024 * 300,  # 300KB
            uploaded_at=datetime(2023, 1, 10, 9, 0, 0),
            sha256="sha256_report_draft_pdf"
        )
        
        cls.file5_text_report = File.objects.create(
            original_filename="text_report_final.txt", 
            file_type="text/plain",
            size=1024 * 10, # 10KB
            uploaded_at=datetime(2023, 1, 15, 11, 0, 0), # Same day as file1
            sha256="sha256_text_report_final_txt"
        )

    def test_search_no_filters(self):
        """Test search with no filters, should return all files."""
        response = self.client.get(self.search_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5) # We created 5 files

    def test_search_by_filename_exact(self):
        response = self.client.get(self.search_url, {'filename': 'report_final.pdf'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.file1.id))

    def test_search_by_filename_partial_case_insensitive(self):
        response = self.client.get(self.search_url, {'filename': 'Report'}) # Partial and different case
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3) # report_final.pdf, report_draft.pdf, text_report_final.txt
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file4.id), ids_in_response)
        self.assertIn(str(self.file5_text_report.id), ids_in_response)


    def test_filter_by_file_type(self):
        response = self.client.get(self.search_url, {'file_type': 'application/pdf'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file4.id), ids_in_response)

    def test_filter_by_size_min(self):
        response = self.client.get(self.search_url, {'size_min': 1024 * 500}) # >= 500KB
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) # file1 (500KB), file3 (2MB)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file3.id), ids_in_response)

    def test_filter_by_size_max(self):
        response = self.client.get(self.search_url, {'size_max': 1024 * 400}) # <= 400KB
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3) # file2 (150KB), file4 (300KB), file5 (10KB)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file2.id), ids_in_response)
        self.assertIn(str(self.file4.id), ids_in_response)
        self.assertIn(str(self.file5_text_report.id), ids_in_response)


    def test_filter_by_size_min_max(self):
        response = self.client.get(self.search_url, {'size_min': 1024 * 200, 'size_max': 1024 * 600}) # 200KB <= size <= 600KB
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) # file1 (500KB), file4 (300KB)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file4.id), ids_in_response)

    def test_filter_by_date_from(self):
        response = self.client.get(self.search_url, {'date_from': '2023-03-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) # file2, file3
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file2.id), ids_in_response)
        self.assertIn(str(self.file3.id), ids_in_response)

    def test_filter_by_date_to(self):
        # uploaded_at__lte means up to and including the date specified (end of that day effectively)
        response = self.client.get(self.search_url, {'date_to': '2023-01-15'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3) # file1, file4, file5
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file4.id), ids_in_response)
        self.assertIn(str(self.file5_text_report.id), ids_in_response)


    def test_filter_by_date_from_to(self):
        response = self.client.get(self.search_url, {'date_from': '2023-01-12', 'date_to': '2023-04-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3) # file1, file2, file5
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file2.id), ids_in_response)
        self.assertIn(str(self.file5_text_report.id), ids_in_response)


    def test_combined_filters(self):
        # PDFs, larger than 400KB, uploaded after 2023-01-01
        response = self.client.get(self.search_url, {
            'file_type': 'application/pdf',
            'size_min': 1024 * 400,
            'date_from': '2023-01-01' 
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.file1.id)) # Only report_final.pdf

    def test_invalid_size_parameter(self):
        response = self.client.get(self.search_url, {'size_min': 'not_a_number'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_date_parameter(self):
        response = self.client.get(self.search_url, {'date_from': 'not_a_date'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_date_parameter_format(self):
        response = self.client.get(self.search_url, {'date_from': '15-01-2023'}) # DD-MM-YYYY instead of YYYY-MM-DD
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

# Note: The FileSearchApiTests setUpTestData creates File objects directly.
# For tests that depend on the file.path being valid and pointing to a real (test) file,
# those files would need to be created using SimpleUploadedFile and saved within an
# environment where TEST_MEDIA_ROOT is active (e.g., in the setUp method of the class
# if @override_settings is used at the class level).
# The current search tests primarily focus on metadata filtering, so direct object creation is mostly fine,
# but this is a common pitfall in Django file testing.
# The FileDeduplicationTests correctly handles file creation in its test methods using the overridden MEDIA_ROOT.
# If FileViewSet.search logic starts to depend on reading file content or more detailed path attributes,
# the setUpTestData for FileSearchApiTests would need to be more robust in its file creation,
# potentially by moving file creation into `setUp` and using `_upload_file` helper or similar.
# Or, by ensuring TEST_MEDIA_ROOT is active and usable during setUpTestData (which can be tricky).
# For now, the sha256 is mocked for these search test objects as well.
# A full test suite might also include tests for edge cases like empty filename search, etc.
# Also, the file URLs in the response data are not explicitly tested here but would be part of a complete test.
# The 'file' field in the response for search results would be the URL to the file.
# If `file.file.save()` was called for each test file in `setUpTestData` with `TEST_MEDIA_ROOT` active,
# these URLs would point to valid locations within `TEST_MEDIA_ROOT`.
# Since that's not done here for simplicity, the `file` field in the API response for these
# search tests might be null or point to an invalid path if not handled carefully by the serializer/model.
# The current `File` model's `file` field can be null.
# The `FileSerializer` includes 'file' in its fields.
# The `file_upload_path` in `models.py` ensures files go into an 'uploads' subdirectory.
# The test `test_new_file_upload` in `FileDeduplicationTests` verifies this.
# The `FileSearchApiTests` does not currently verify the `file` field in responses.
# This could be a point of future improvement for these tests.

```python
import os
import shutil
import hashlib
from datetime import datetime, timedelta

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import override_settings # Important for controlling MEDIA_ROOT

from rest_framework.test import APITestCase
from rest_framework import status

from .models import File # Assuming your File model is in the same app

# Use a temporary media root for tests to avoid polluting the main media root
# and to make cleanup easier.
TEST_MEDIA_ROOT = os.path.join(settings.BASE_DIR, 'test_media_root_files_app') # Unique name

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class FileDeduplicationTests(APITestCase):
    """
    Tests for the file deduplication logic during uploads.
    """
    def setUp(self):
        # Ensure the test media directory exists and is empty before each test
        if not os.path.exists(TEST_MEDIA_ROOT):
            os.makedirs(TEST_MEDIA_ROOT)
        # else: # APITestCase should handle test isolation for media files if configured
        #     # Clean up any old test files from previous runs if needed,
        #     # though APITestCase usually creates a new temp media root or handles cleanup.
        #     # For explicit control:
        #     for filename in os.listdir(TEST_MEDIA_ROOT):
        #         file_path = os.path.join(TEST_MEDIA_ROOT, filename)
        #         if os.path.isfile(file_path) or os.path.islink(file_path):
        #             os.unlink(file_path)
        #         elif os.path.isdir(file_path):
        #             shutil.rmtree(file_path)
        
        self.upload_url = reverse('file-list') # From DRF router, for list and create

    def tearDown(self):
        # Clean up the test media directory after all tests in the class are done
        # This is good practice if @override_settings is at class level.
        # APITestCase might handle this automatically if settings are right.
        if os.path.exists(TEST_MEDIA_ROOT):
             pass # shutil.rmtree(TEST_MEDIA_ROOT) # APITestCase should handle this. If not, enable.


    def _upload_file(self, filename="test.txt", content=b"hello world", content_type="text/plain"):
        """Helper method to upload a file."""
        file_data = SimpleUploadedFile(filename, content, content_type=content_type)
        # Ensure client is authenticated if required by view, not the case here for FileViewSet
        return self.client.post(self.upload_url, {'file': file_data}, format='multipart')

    def test_new_file_upload(self):
        content = b"This is a unique file for testing."
        filename = "unique_file.txt"
        
        response = self._upload_file(filename, content)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(File.objects.count(), 1)
        
        file_obj = File.objects.first()
        self.assertFalse(file_obj.is_duplicate)
        self.assertIsNotNone(file_obj.sha256)
        self.assertIsNone(file_obj.original_file)
        
        # Verify SHA256
        expected_sha256 = hashlib.sha256(content).hexdigest()
        self.assertEqual(file_obj.sha256, expected_sha256)
        
        # Verify physical file existence and location
        self.assertTrue(os.path.exists(file_obj.file.path))
        self.assertTrue(file_obj.file.path.startswith(TEST_MEDIA_ROOT))
        # Ensure it is in the 'uploads' subdirectory as per file_upload_path
        self.assertTrue(os.path.join('uploads', '') in file_obj.file.path.replace(TEST_MEDIA_ROOT, ''))


    def test_duplicate_file_upload(self):
        content = b"This content will be duplicated."
        original_filename = "original.txt"
        duplicate_filename = "duplicate.txt"
        
        # Upload the original file
        response_orig = self._upload_file(original_filename, content)
        self.assertEqual(response_orig.status_code, status.HTTP_201_CREATED)
        original_file_obj = File.objects.get(id=response_orig.data['id'])
        
        # Upload the duplicate file (same content, different name)
        response_dup = self._upload_file(duplicate_filename, content)
        self.assertEqual(response_dup.status_code, status.HTTP_201_CREATED)
        self.assertEqual(File.objects.count(), 2) # Two database entries
        
        duplicate_file_obj = File.objects.get(id=response_dup.data['id'])
        
        self.assertTrue(duplicate_file_obj.is_duplicate)
        self.assertEqual(duplicate_file_obj.sha256, original_file_obj.sha256)
        self.assertEqual(duplicate_file_obj.original_file, original_file_obj)
        
        # Key check: physical file path should be the same as original
        self.assertEqual(duplicate_file_obj.file.path, original_file_obj.file.path)
        
        # Verify only one physical file was saved in the 'uploads' directory
        uploads_dir = os.path.join(TEST_MEDIA_ROOT, 'uploads')
        self.assertTrue(os.path.exists(uploads_dir))
        self.assertEqual(len(os.listdir(uploads_dir)), 1)

    def test_multiple_duplicate_uploads(self):
        content = b"Content for testing multiple duplicates."
        
        # Upload original
        response_orig = self._upload_file("multi_original.txt", content)
        self.assertEqual(response_orig.status_code, status.HTTP_201_CREATED)
        original_file_obj = File.objects.get(id=response_orig.data['id'])
        
        # Upload first duplicate
        response_dup1 = self._upload_file("multi_dup1.txt", content)
        self.assertEqual(response_dup1.status_code, status.HTTP_201_CREATED)
        dup1_obj = File.objects.get(id=response_dup1.data['id'])
        
        # Upload second duplicate
        response_dup2 = self._upload_file("multi_dup2.txt", content)
        self.assertEqual(response_dup2.status_code, status.HTTP_201_CREATED)
        dup2_obj = File.objects.get(id=response_dup2.data['id'])
        
        self.assertEqual(File.objects.count(), 3) # Three DB entries
        
        self.assertTrue(dup1_obj.is_duplicate)
        self.assertEqual(dup1_obj.original_file, original_file_obj)
        self.assertEqual(dup1_obj.file.path, original_file_obj.file.path)
        
        self.assertTrue(dup2_obj.is_duplicate)
        self.assertEqual(dup2_obj.original_file, original_file_obj)
        self.assertEqual(dup2_obj.file.path, original_file_obj.file.path)

        uploads_dir = os.path.join(TEST_MEDIA_ROOT, 'uploads')
        self.assertTrue(os.path.exists(uploads_dir))
        self.assertEqual(len(os.listdir(uploads_dir)), 1) # Still only one physical file


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT) # Apply to this class too
class FileSearchApiTests(APITestCase):
    """
    Tests for the file search and filtering API endpoint.
    """
    @classmethod
    def setUpTestData(cls):
        # Note: APITestCase runs setUpTestData outside the transaction wrapper of individual tests.
        # File creation here needs to be careful if file paths are critical.
        # For these tests, we'll create File objects and mock their sha256 and file paths
        # if the actual file content isn't strictly necessary for filtering logic.
        # However, the FileDeduplicationTests approach of uploading in setUp is more robust for file paths.

        cls.search_url = reverse('file-search') # Custom action route name

        # Create a temporary directory that will be managed by @override_settings
        # and APITestCase's own media management.
        if not os.path.exists(TEST_MEDIA_ROOT):
            os.makedirs(TEST_MEDIA_ROOT)
        
        # Helper to create file objects for testing search.
        # This simulates a file being "uploaded" and saved.
        def create_test_file(filename, content_bytes, content_type,
                             upload_date_override, sha256_override=None):
            
            path_prefix = os.path.join(TEST_MEDIA_ROOT, 'uploads')
            if not os.path.exists(path_prefix):
                os.makedirs(path_prefix)

            # Create a unique path for the dummy file based on a hash or UUID like the model does
            # For testing, a simpler unique name is fine.
            dummy_file_name_on_disk = f"{hashlib.md5(content_bytes).hexdigest()}_{filename}"
            dummy_file_path = os.path.join(path_prefix, dummy_file_name_on_disk)
            
            with open(dummy_file_path, 'wb') as f:
                f.write(content_bytes)

            file_instance = File(
                original_filename=filename,
                file_type=content_type,
                size=len(content_bytes),
                uploaded_at=upload_date_override,
                sha256=sha256_override or hashlib.sha256(content_bytes).hexdigest(),
                # file field needs a path relative to MEDIA_ROOT
                file=os.path.join('uploads', dummy_file_name_on_disk)
            )
            file_instance.save()
            return file_instance

        cls.file1 = create_test_file(
            "report_final.pdf", b"PDF content version 1", "application/pdf",
            datetime(2023, 1, 15, 10, 0, 0, tzinfo=settings.TIME_ZONE_OBJ if settings.USE_TZ else None)
        )
        cls.file2 = create_test_file(
            "image_profile.jpg", b"JPEG image content", "image/jpeg",
            datetime(2023, 3, 20, 14, 30, 0, tzinfo=settings.TIME_ZONE_OBJ if settings.USE_TZ else None)
        )
        cls.file3 = create_test_file(
            "archive_data.zip", b"ZIP content, quite large" * 1000, "application/zip", # Larger file
            datetime(2023, 5, 10, 18, 45, 0, tzinfo=settings.TIME_ZONE_OBJ if settings.USE_TZ else None)
        )
        cls.file4 = create_test_file(
            "report_draft.pdf", b"PDF content draft version", "application/pdf", # Another PDF
            datetime(2023, 1, 10, 9, 0, 0, tzinfo=settings.TIME_ZONE_OBJ if settings.USE_TZ else None)
        )
        cls.file5_text_report = create_test_file(
            "text_report_final.txt", b"Plain text final report", "text/plain",
            datetime(2023, 1, 15, 11, 0, 0, tzinfo=settings.TIME_ZONE_OBJ if settings.USE_TZ else None) # Same day as file1
        )
    
    @classmethod
    def tearDownClass(cls):
        # Clean up the test media directory after all tests in this class are done
        if os.path.exists(TEST_MEDIA_ROOT):
            shutil.rmtree(TEST_MEDIA_ROOT)
        super().tearDownClass()


    def test_search_no_filters(self):
        response = self.client.get(self.search_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)

    def test_search_by_filename_exact(self):
        response = self.client.get(self.search_url, {'filename': 'report_final.pdf'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.file1.id))

    def test_search_by_filename_partial_case_insensitive(self):
        response = self.client.get(self.search_url, {'filename': 'Report'}) # Partial, case-insensitive
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Expects 'report_final.pdf', 'report_draft.pdf', 'text_report_final.txt'
        self.assertEqual(len(response.data), 3)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file4.id), ids_in_response)
        self.assertIn(str(self.file5_text_report.id), ids_in_response)

    def test_filter_by_file_type(self):
        response = self.client.get(self.search_url, {'file_type': 'application/pdf'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file4.id), ids_in_response)

    def test_filter_by_size_min(self):
        response = self.client.get(self.search_url, {'size_min': self.file3.size -1 }) # Slightly less than file3 size
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.file3.id))

    def test_filter_by_size_max(self):
        response = self.client.get(self.search_url, {'size_max': self.file2.size + 1}) # Slightly more than file2 size
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Expect file1, file2, file4, file5 (all except file3 which is very large)
        expected_ids = {str(self.file1.id), str(self.file2.id), str(self.file4.id), str(self.file5_text_report.id)}
        ids_in_response = {item['id'] for item in response.data}
        # Check if all expected IDs are in the response
        # This depends on the exact sizes. Let's be more precise.
        # file1: 21, file2: 18, file3: 23000, file4: 25, file5_text_report: 23
        # size_max = 18 + 1 = 19. Should only include file2.
        response = self.client.get(self.search_url, {'size_max': self.file2.size })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file2.id), ids_in_response)
        # To be more robust, explicitly list expected files based on their sizes
        # file1=21, file2=18, file3=23000, file4=25, file5=23
        # size_max=100 should include file1, file2, file4, file5
        response = self.client.get(self.search_url, {'size_max': 100})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids_in_response = {item['id'] for item in response.data}
        self.assertEqual(len(ids_in_response), 4)
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file2.id), ids_in_response)
        self.assertIn(str(self.file4.id), ids_in_response)
        self.assertIn(str(self.file5_text_report.id), ids_in_response)


    def test_filter_by_size_min_max(self):
        # file1=21, file2=18, file3=23000, file4=25, file5=23
        # min=20, max=24 --> file1 (21), file5 (23)
        response = self.client.get(self.search_url, {'size_min': 20, 'size_max': 24})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file5_text_report.id), ids_in_response)


    def test_filter_by_date_from(self):
        response = self.client.get(self.search_url, {'date_from': '2023-03-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) # file2 (Mar 20), file3 (May 10)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file2.id), ids_in_response)
        self.assertIn(str(self.file3.id), ids_in_response)

    def test_filter_by_date_to(self):
        response = self.client.get(self.search_url, {'date_to': '2023-01-15'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # file1 (Jan 15), file4 (Jan 10), file5 (Jan 15)
        self.assertEqual(len(response.data), 3)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file4.id), ids_in_response)
        self.assertIn(str(self.file5_text_report.id), ids_in_response)

    def test_filter_by_date_from_to(self):
        # From Jan 12 to Apr 1
        # file1 (Jan 15), file2 (Mar 20), file5 (Jan 15)
        response = self.client.get(self.search_url, {'date_from': '2023-01-12', 'date_to': '2023-04-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        ids_in_response = {item['id'] for item in response.data}
        self.assertIn(str(self.file1.id), ids_in_response)
        self.assertIn(str(self.file2.id), ids_in_response)
        self.assertIn(str(self.file5_text_report.id), ids_in_response)

    def test_combined_filters(self):
        # PDF, size > 20 bytes, uploaded on or after 2023-01-15
        # file1 (PDF, 21 bytes, Jan 15)
        # file4 (PDF, 25 bytes, Jan 10) -> excluded by date
        response = self.client.get(self.search_url, {
            'file_type': 'application/pdf',
            'size_min': 20, 
            'date_from': '2023-01-15'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.file1.id))

    def test_invalid_size_parameter(self):
        response = self.client.get(self.search_url, {'size_min': 'abc'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data) # Check for your specific error message key

    def test_invalid_date_parameter_format(self):
        response = self.client.get(self.search_url, {'date_from': '15/01/2023'}) # Wrong format
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

```

I've created the `backend/files/tests.py` file with two test classes: `FileDeduplicationTests` and `FileSearchApiTests`.

**Key aspects of the generated tests:**

*   **`FileDeduplicationTests`:**
    *   Uses `@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)` to redirect file uploads to a temporary directory.
    *   `setUp` and `tearDown` (or rather, relying on `APITestCase`'s handling of `MEDIA_ROOT` when overridden) manage the test media directory.
    *   `_upload_file` is a helper for posting files.
    *   Tests new uploads, duplicate uploads (checking `is_duplicate`, `original_file`, `sha256`, and that physical file paths match the original), and multiple duplicates.
    *   Verifies the number of physical files saved in the `uploads` subdirectory of `TEST_MEDIA_ROOT`.

*   **`FileSearchApiTests`:**
    *   Also uses `@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)`.
    *   `setUpTestData` creates a diverse set of `File` objects.
        *   **Important:** I've added a helper `create_test_file` within `setUpTestData` to actually create dummy physical files in the `TEST_MEDIA_ROOT`. This is crucial because if the search API or serializer tries to access `file.path` or `file.url`, these need to be valid. The `file` field in the `File` model is populated with a path relative to `MEDIA_ROOT`.
        *   Uses `datetime` objects with timezone information if `USE_TZ` is true (important for date filtering).
    *   Tests various filter combinations: by filename (exact, partial, case-insensitive), file type, size (min, max, range), date (from, to, range), and combined filters.
    *   Tests for no filters (all files returned).
    *   Tests for invalid input parameters (e.g., non-integer size, incorrect date format), expecting a 400 Bad Request.
    *   `tearDownClass` is added to explicitly clean up `TEST_MEDIA_ROOT` after all search tests.

**Next Steps:**

1.  Run these tests using `python manage.py test files.tests` (after attempting migrations).
2.  Analyze the output and submit the report.

I've tried to make the `setUpTestData` for search tests more robust by actually creating placeholder files on disk. This makes the test environment closer to reality.

Let's try running the migrations and then the tests.
