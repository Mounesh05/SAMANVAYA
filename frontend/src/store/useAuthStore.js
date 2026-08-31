import { create } from 'zustand';

const initialToken = localStorage.getItem('samanvaya_token') || null;
let initialUser = null;
try {
  const savedUser = localStorage.getItem('samanvaya_user');
  if (savedUser) initialUser = JSON.parse(savedUser);
} catch {
  initialUser = null;
}

export const useAuthStore = create((set) => ({
  token: initialToken,
  user: initialUser,
  isAuthenticated: !!initialToken,

  setAuth: (token, user) => {
    localStorage.setItem('samanvaya_token', token);
    localStorage.setItem('samanvaya_user', JSON.stringify(user));
    set({ token, user, isAuthenticated: true });
  },

  setUser: (user) => {
    localStorage.setItem('samanvaya_user', JSON.stringify(user));
    set({ user });
  },

  logout: () => {
    localStorage.removeItem('samanvaya_token');
    localStorage.removeItem('samanvaya_user');
    set({ token: null, user: null, isAuthenticated: false });
  },
}));
