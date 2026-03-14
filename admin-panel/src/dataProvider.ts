import axios from 'axios';
import { DataProvider, GetListParams, GetOneParams, CreateParams, UpdateParams, DeleteParams } from 'react-admin';

const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const httpClient = axios.create({
    baseURL: apiUrl,
});

// Add auth token to requests
httpClient.interceptors.request.use((config) => {
    try {
        const auth = localStorage.getItem('auth');
        if (auth) {
            const session = JSON.parse(auth);
            if (session?.access_token) {
                config.headers.Authorization = `Bearer ${session.access_token}`;
            }
        }
    } catch (e) {
        console.warn('Failed to parse auth from localStorage:', e);
    }
    return config;
}, (error) => {
    console.error('Request interceptor error:', error);
    return Promise.reject(error);
});

// Add response interceptor to handle token expiry (401)
httpClient.interceptors.response.use(
    (response) => response,
    (error) => {
        // We let the authProvider handle the 401/403 redirects via checkError
        return Promise.reject(error);
    }
);

export const dataProvider: DataProvider = {
    getList: async (resource, params: GetListParams) => {
        const { page, perPage } = params.pagination;
        const query = {
            ...params.filter,
            page,
            per_page: perPage,
        };

        const url = `/admin/${resource}`;
        try {
            const { data } = await httpClient.get(url, { params: query });
            console.log(`[DataProvider] getList for ${resource}:`, { data, total: data.total });

            return {
                data: data.data || data,
                total: data.total !== undefined ? data.total : (Array.isArray(data) ? data.length : 0),
            };
        } catch (error) {
            console.error(`[DataProvider] getList failed for ${resource}:`, error);
            throw error;
        }
    },

    getOne: async (resource, params: GetOneParams) => {
        const url = `/admin/${resource}/${params.id}`;
        const { data } = await httpClient.get(url);
        return { data };
    },

    getMany: async (resource, params) => {
        const promises = params.ids.map((id) =>
            httpClient.get(`/admin/${resource}/${id}`)
        );
        const responses = await Promise.all(promises);
        return { data: responses.map((r) => r.data) };
    },

    getManyReference: async (resource, params) => {
        const { page, perPage } = params.pagination;
        const query = {
            ...params.filter,
            [params.target]: params.id,
            page,
            per_page: perPage,
        };

        const url = `/admin/${resource}`;
        const { data } = await httpClient.get(url, { params: query });

        return {
            data: data.data || data,
            total: data.total || data.length,
        };
    },

    create: async (resource, params: CreateParams) => {
        const url = `/admin/${resource}`;
        const { data } = await httpClient.post(url, params.data);
        return { data };
    },

    update: async (resource, params: UpdateParams) => {
        const url = `/admin/${resource}/${params.id}`;
        const { data } = await httpClient.put(url, params.data);
        return { data };
    },

    updateMany: async (resource, params) => {
        const promises = params.ids.map((id) =>
            httpClient.put(`/admin/${resource}/${id}`, params.data)
        );
        const responses = await Promise.all(promises);
        return { data: responses.map((r) => r.data.id) };
    },

    delete: async (resource, params: DeleteParams) => {
        const url = `/admin/${resource}/${params.id}`;
        await httpClient.delete(url);
        return { data: params.previousData };
    },

    deleteMany: async (resource, params) => {
        const promises = params.ids.map((id) =>
            httpClient.delete(`/admin/${resource}/${id}`)
        );
        await Promise.all(promises);
        return { data: params.ids };
    },
};
