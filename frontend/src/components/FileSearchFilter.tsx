import React, { useState } from 'react';
import { SearchParams } from '../services/fileService';

interface FileSearchFilterProps {
  onSearch: (params: SearchParams) => void;
  onClear: () => void;
  isSearching: boolean;
}

export const FileSearchFilter: React.FC<FileSearchFilterProps> = ({ onSearch, onClear, isSearching }) => {
  const [filename, setFilename] = useState('');
  const [fileType, setFileType] = useState('');
  const [sizeMin, setSizeMin] = useState('');
  const [sizeMax, setSizeMax] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const params: SearchParams = {
      filename: filename || undefined,
      file_type: fileType || undefined,
      size_min: sizeMin ? parseInt(sizeMin, 10) : undefined,
      size_max: sizeMax ? parseInt(sizeMax, 10) : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };
    onSearch(params);
  };

  const handleClear = () => {
    setFilename('');
    setFileType('');
    setSizeMin('');
    setSizeMax('');
    setDateFrom('');
    setDateTo('');
    onClear();
  };

  return (
    <form onSubmit={handleSearch} className="p-6 bg-white shadow rounded-lg mb-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Filter Files</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div>
          <label htmlFor="filename" className="block text-sm font-medium text-gray-700">Filename</label>
          <input
            type="text"
            id="filename"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
          />
        </div>
        <div>
          <label htmlFor="fileType" className="block text-sm font-medium text-gray-700">File Type</label>
          <input
            type="text"
            id="fileType"
            value={fileType}
            onChange={(e) => setFileType(e.target.value)}
            placeholder="e.g., image/jpeg"
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
          />
        </div>
        <div>
          <label htmlFor="sizeMin" className="block text-sm font-medium text-gray-700">Min Size (bytes)</label>
          <input
            type="number"
            id="sizeMin"
            value={sizeMin}
            onChange={(e) => setSizeMin(e.target.value)}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
          />
        </div>
        <div>
          <label htmlFor="sizeMax" className="block text-sm font-medium text-gray-700">Max Size (bytes)</label>
          <input
            type="number"
            id="sizeMax"
            value={sizeMax}
            onChange={(e) => setSizeMax(e.target.value)}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
          />
        </div>
        <div>
          <label htmlFor="dateFrom" className="block text-sm font-medium text-gray-700">Date From</label>
          <input
            type="date"
            id="dateFrom"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
          />
        </div>
        <div>
          <label htmlFor="dateTo" className="block text-sm font-medium text-gray-700">Date To</label>
          <input
            type="date"
            id="dateTo"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
          />
        </div>
      </div>
      <div className="mt-6 flex space-x-3 justify-end">
        <button
          type="button"
          onClick={handleClear}
          disabled={isSearching}
          className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50"
        >
          Clear Filters
        </button>
        <button
          type="submit"
          disabled={isSearching}
          className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50"
        >
          {isSearching ? 'Searching...' : 'Search'}
        </button>
      </div>
    </form>
  );
};
