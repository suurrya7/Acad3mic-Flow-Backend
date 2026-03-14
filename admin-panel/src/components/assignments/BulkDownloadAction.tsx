import { useListContext, useNotify, useUnselectAll } from 'react-admin';
import { Button } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import axios from 'axios';
import { useState } from 'react';

export const BulkDownloadAction = () => {
    const { selectedIds } = useListContext();
    const notify = useNotify();
    const unselectAll = useUnselectAll('assignments');
    const [loading, setLoading] = useState(false);

    const handleDownload = async () => {
        if (!selectedIds || selectedIds.length === 0) return;

        setLoading(true);
        try {
            const auth = localStorage.getItem('auth');
            const session = JSON.parse(auth || '{}');

            // Convert to array of strings and create query params
            const queryParams = new URLSearchParams();
            selectedIds.forEach(id => queryParams.append('report_ids', id.toString()));

            const response = await axios.get(
                // @ts-ignore
                `${import.meta.env.VITE_API_URL}/admin/assignments/download?${queryParams.toString()}`,
                {
                    headers: { Authorization: `Bearer ${session.access_token}` },
                    responseType: 'blob' // Important for downloading files
                }
            );

            // Create a temporary link to trigger the browser download
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `grading_reports_${new Date().getTime()}.zip`);
            document.body.appendChild(link);
            link.click();
            link.remove();

            notify('Files downloaded successfully', { type: 'success' });
            unselectAll();
        } catch (error) {
            console.error(error);
            notify('Failed to bulk download files', { type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <Button
            onClick={handleDownload}
            disabled={loading || selectedIds.length === 0}
            startIcon={<DownloadIcon />}
            color="primary"
        >
            {loading ? 'ZIPPING...' : 'DOWNLOAD SELECTED'}
        </Button>
    );
};
