import { render } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

/**
 * Create a custom render function with all providers
 * 
 * @param {React.ReactElement} ui - Component to render
 * @param {Object} options - Render options
 * @param {string} options.route - Initial route (default: '/')
 * @param {QueryClient} options.queryClient - React Query client
 * @param {Object} options.renderOptions - Additional render options
 * @returns {Object} Render result with queryClient
 */
export function renderWithProviders(
  ui,
  {
    route = '/',
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    }),
    ...renderOptions
  } = {}
) {
  // Set initial route
  window.history.pushState({}, 'Test page', route)
  
  function Wrapper({ children }) {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          {children}
        </BrowserRouter>
      </QueryClientProvider>
    )
  }
  
  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient
  }
}

// Re-export everything from React Testing Library
export * from '@testing-library/react'
export { default as userEvent } from '@testing-library/user-event'
