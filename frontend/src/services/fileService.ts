import axios from 'axios';
import { File as FileType } from '../types/file';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export const fileService = {
  async uploadFile(file: File): Promise<FileType> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await axios.post(`${API_URL}/files/`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async getFiles(): Promise<FileType[]> {
    const response = await axios.get(`${API_URL}/files/`);
    return response.data;
  },

  async deleteFile(id: string): Promise<void> {
    await axios.delete(`${API_URL}/files/${id}/`);
  },

  async downloadFile(fileUrl: string, filename: string): Promise<void> {
    try {
      const response = await axios.get(fileUrl, {
        responseType: 'blob',
      });
      
      // Create a blob URL and trigger download
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download error:', error);
      throw new Error('Failed to download file');
    }
  },

  async searchFiles(params: SearchParams): Promise<FileType[]> {
    // Filter out undefined or empty string params to avoid sending them
    const filteredParams = Object.entries(params).reduce((acc, [key, value]) => {
      if (value !== undefined && value !== '') {
        acc[key] = value;
      }
      return acc;
    }, {} as Record<string, any>);

    const response = await axios.get(`${API_URL}/files/search/`, { params: filteredParams });
    return response.data;
  },
};

export interface SearchParams {
  filename?: string;
  file_type?: string;
  size_min?: number;
  size_max?: number;
  date_from?: string; // YYYY-MM-DD
  date_to?: string;   // YYYY-MM-DD
}