import axios from 'axios';

// Create an axios instance with default config
const apiClient = axios.create({
    baseURL: 'http://localhost:8000/api', // Make sure backend is running on this port
    headers: {
        'Content-Type': 'application/json',
    },
});

export const uploadVideo = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/upload', formData, {
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
