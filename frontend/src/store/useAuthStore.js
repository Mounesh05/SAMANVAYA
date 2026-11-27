import { create } from 'zustand';

// SEC-05: the session token is an HttpOnly cookie the page cannot read. Only
// the non-secret profile is kept here so the UI can render after a reload;
// the server still checks the cookie on every request.
localStorage.removeItem('samanvaya_token');
let initialUser = null;
try {
  const savedUser = localStorage.getItem('samanvaya_user');
  if (savedUser) initialUser = JSON.parse(savedUser);
} catch {
  initialUser = null;
}

export const useAuthStore = create((set) => ({
  token: null,
  user: initialUser,
  isAuthenticated: !!initialUser,

  // The first argument is ignored (kept so existing callers keep working).
  setAuth: (_token, user) => {
    localStorage.setItem('samanvaya_user', JSON.stringify(user));
    set({ token: null, user, isAuthenticated: true });
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
