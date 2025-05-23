export interface File {
  id: string;
  original_filename: string;
  file_type: string;
  size: number;
  uploaded_at: string;
  file: string; // This is typically the URL to the file
  sha256?: string; // Optional as older entries might not have it
  is_duplicate?: boolean;
  original_file?: string | null; // ID of the original file, if it's a duplicate
}