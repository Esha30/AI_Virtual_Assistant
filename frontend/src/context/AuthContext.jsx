import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [token, setToken] = useState(localStorage.getItem('token'));

    useEffect(() => {
        if (token) {
            fetchUser();
        } else {
            setLoading(false);
        }
    }, [token]);

    const fetchUser = async () => {
        try {
            const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/me`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (res.ok) {
                const data = await res.json();
                setUser(data);
            } else {
                logout();
            }
        } catch (error) {
            console.error('Failed to fetch user', error);
            logout();
        } finally {
            setLoading(false);
        }
    };

    const login = async (email, password) => {
        const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (res.ok) {
            localStorage.setItem('token', data.access_token);
            setToken(data.access_token);
            return { success: true };
        }
        return { success: false, message: data.detail || 'Login failed' };
    };

    const signup = async (email, password) => {
        const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (res.ok) {
            return { success: true };
        }
        return { success: false, message: data.detail || 'Signup failed' };
    };

    const logout = () => {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
    };

    const authenticatedFetch = async (url, options = {}) => {
        const headers = {
            ...options.headers,
            'Authorization': `Bearer ${token}`
        };
        return fetch(url, { ...options, headers });
    };

    return (
        <AuthContext.Provider value={{ user, token, loading, login, signup, logout, authenticatedFetch }}>
            {children}
        </AuthContext.Provider>
    );
};
