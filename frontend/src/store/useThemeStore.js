import { create } from 'zustand';

const initialTheme = localStorage.getItem('samanvaya_theme') || 'dark';
document.documentElement.setAttribute('data-theme', initialTheme);

export const useThemeStore = create((set) => ({
  theme: initialTheme,
  sidebarCollapsed: false,

  toggleTheme: () => {
    set((state) => {
      const nextTheme = state.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('samanvaya_theme', nextTheme);
      document.documentElement.setAttribute('data-theme', nextTheme);
      return { theme: nextTheme };
    });
  },

  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
}));
