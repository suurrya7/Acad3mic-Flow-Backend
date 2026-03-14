import { AuthProvider } from 'react-admin';
import { supabase } from './supabase';

export const authProvider: AuthProvider = {
    login: async ({ username, password }) => {
        const { data, error } = await supabase.auth.signInWithPassword({
            email: username,
            password: password,
        });

        if (error) {
            throw new Error(error.message);
        }

        // Check if user is admin
        const { data: profile } = await supabase
            .from('user_profiles')
            .select('is_admin')
            .eq('id', data.user.id)
            .single();

        if (!profile?.is_admin) {
            await supabase.auth.signOut();
            throw new Error('Admin access required');
        }

        localStorage.setItem('auth', JSON.stringify(data.session));
        return Promise.resolve();
    },

    logout: async () => {
        await supabase.auth.signOut();
        localStorage.removeItem('auth');
        return Promise.resolve();
    },

    checkError: (error) => {
        const status = error.status || error.response?.status;
        console.log('[AuthProvider] checkError:', { status, error });
        if (status === 401 || status === 403) {
            localStorage.removeItem('auth');
            return Promise.reject();
        }
        return Promise.resolve();
    },

    checkAuth: async () => {
        try {
            const { data, error: sessionError } = await supabase.auth.getSession();
            console.log('[AuthProvider] checkAuth session:', { hasSession: !!data.session, sessionError });

            if (!data.session) {
                return Promise.reject();
            }

            // Verify admin status
            const { data: profile, error: profileError } = await supabase
                .from('user_profiles')
                .select('is_admin')
                .eq('id', data.session.user.id)
                .single();

            console.log('[AuthProvider] checkAuth profile:', { profile, profileError });

            if (!profile?.is_admin) {
                console.warn('[AuthProvider] Access denied: User is not an admin');
                return Promise.reject({ message: 'Admin access required' });
            }

            return Promise.resolve();
        } catch (err) {
            console.error('[AuthProvider] checkAuth unexpected error:', err);
            return Promise.reject(err);
        }
    },

    getPermissions: () => Promise.resolve(),

    getIdentity: async () => {
        const { data } = await supabase.auth.getUser();
        if (!data.user) {
            throw new Error('Not authenticated');
        }

        return {
            id: data.user.id,
            fullName: data.user.email,
            avatar: undefined,
        };
    },
};
