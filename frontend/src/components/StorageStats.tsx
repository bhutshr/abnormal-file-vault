import React, { useState, useEffect } from 'react';
import { fileService, StorageStatsData } from '../services/fileService';

const formatBytes = (bytes: number, decimals = 2): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

const StorageStats: React.FC = () => {
  const [stats, setStats] = useState<StorageStatsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const data = await fileService.getStorageStats();
        setStats(data);
        setError(null);
      } catch (err) {
        setError('Failed to load storage statistics.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (loading) {
    return <p>Loading storage statistics...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  if (!stats) {
    return <p>No storage statistics available.</p>;
  }

  return (
    <div style={{ padding: '20px', border: '1px solid #ccc', borderRadius: '8px', marginBottom: '20px' }}>
      <h3>Storage Statistics</h3>
      <p>Total files stored: {stats.total_files_count} ({stats.original_files_count} unique, {stats.deduplicated_files_count} duplicates)</p>
      <p>Actual storage used (Physical): {formatBytes(stats.total_physical_size)}</p>
      <p>Storage saved by deduplication: {formatBytes(stats.saved_space)}</p>
      <p>Total logical size (if no deduplication): {formatBytes(stats.total_logical_size)}</p>
    </div>
  );
};

export default StorageStats;
