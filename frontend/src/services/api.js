import axios from 'axios';

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8010/api';

// Create an axios instance with default config
const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const uploadVideo = async (file, targetLanguage) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target_language', targetLanguage);

    const response = await apiClient.post('/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const startDemoJob = async (targetLanguage) => {
    const formData = new FormData();
    formData.append('target_language', targetLanguage);

    const response = await apiClient.post('/demo', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const getJobStatus = async (jobId) => {
    const response = await apiClient.get(`/status/${jobId}`);
    return response.data;
};

export const getJobResult = async (jobId) => {
    const response = await apiClient.get(`/result/${jobId}`);
    return response.data;
};
