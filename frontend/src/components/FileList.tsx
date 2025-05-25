import React, { useState } from 'react';
import { fileService, SearchParams } from '../services/fileService';
import { File as FileType } from '../types/file';
import { DocumentIcon, TrashIcon, ArrowDownTrayIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileSearchFilter } from './FileSearchFilter';

export const FileList: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useState<SearchParams | null>(null);

  const { data: files, isLoading, error, isFetching } = useQuery<FileType[], Error>({
    queryKey: ['files', searchParams],
    queryFn: () => (searchParams ? fileService.searchFiles(searchParams) : fileService.getFiles()),
    refetchOnWindowFocus: false,
  });

  const deleteMutation = useMutation({
    mutationFn: fileService.deleteFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });

  const downloadMutation = useMutation({
    mutationFn: ({ fileUrl, filename }: { fileUrl: string; filename: string }) =>
      fileService.downloadFile(fileUrl, filename),
  });

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  const handleDownload = async (fileUrl: string, filename: string) => {
    try {
      await downloadMutation.mutateAsync({ fileUrl, filename });
    } catch (err) {
      console.error('Download error:', err);
    }
  };

  const handleSearch = (params: SearchParams) => {
    setSearchParams(params);
  };

  const handleClearSearch = () => {
    setSearchParams(null);
  };

  const isCurrentlySearching = isLoading || isFetching;

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="animate-pulse space-y-4 mt-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-200 rounded"></div>
          ))}
        </div>
      );
    }

    if (error) {
      return (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 mt-4">
          <div className="flex">
            <div className="flex-shrink-0">{/* Error Icon */}</div>
            <div className="ml-3">
              <p className="text-sm text-red-700">
                Failed to load files: {error.message || 'Please try again.'}
              </p>
            </div>
          </div>
        </div>
      );
    }

    if (!files || files.length === 0) {
      return (
        <div className="text-center py-12">
          {searchParams ? (
            <>
              <MagnifyingGlassIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No files found</h3>
              <p className="mt-1 text-sm text-gray-500">Try adjusting your search or filter criteria.</p>
            </>
          ) : (
            <>
              <DocumentIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No files uploaded yet</h3>
              <p className="mt-1 text-sm text-gray-500">Get started by uploading a file.</p>
            </>
          )}
        </div>
      );
    }

    return (
      <div className="mt-6 flow-root">
        <ul className="-my-5 divide-y divide-gray-200">
          {files.map((file) => (
            <li key={file.id} className="py-4">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <DocumentIcon className="h-8 w-8 text-gray-400 mt-1" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {file.original_filename}
                  </p>
                  <div className="text-xs text-gray-500 space-y-0.5">
                    <p>{file.file_type} • {(file.size / 1024).toFixed(2)} KB</p>
                    <p>Uploaded: {new Date(file.uploaded_at).toLocaleString()}</p>
                    {file.sha256 && <p className="truncate">SHA256: {file.sha256}</p>}
                    {file.is_duplicate && (
                      <p className="text-yellow-600">
                        Duplicate of: <span className="font-medium">{file.original_file || 'N/A'}</span>
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex-shrink-0 flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
                  <button
                    onClick={() => handleDownload(file.file, file.original_filename)}
                    disabled={downloadMutation.isPending}
                    className="inline-flex items-center justify-center px-3 py-1.5 border border-transparent shadow-sm text-xs leading-4 font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50"
                  >
                    <ArrowDownTrayIcon className="h-4 w-4 mr-1 sm:mr-0.5" />
                    <span className="hidden sm:inline">Download</span>
                  </button>
                  <button
                    onClick={() => handleDelete(file.id)}
                    disabled={deleteMutation.isPending}
                    className="inline-flex items-center justify-center px-3 py-1.5 border border-transparent shadow-sm text-xs leading-4 font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                  >
                    <TrashIcon className="h-4 w-4 mr-1 sm:mr-0.5" />
                    <span className="hidden sm:inline">Delete</span>
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className="p-6">
      <FileSearchFilter
        onSearch={handleSearch}
        onClear={handleClearSearch}
        isSearching={isCurrentlySearching}
      />
      <h2 className="text-xl font-semibold text-gray-900 mb-4 mt-6">
        {searchParams ? 'Search Results' : 'All Uploaded Files'}
      </h2>
      {renderContent()}
    </div>
  );
};
