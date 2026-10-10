import { useAuthStore } from '@/store/useAuthStore'

/**
 * Set authenticated user in test environment
 * 
 * @param {Object} user - User object (optional, uses default if not provided)
 */
export function setAuthUser(user = null) {
  const defaultUser = {
    id: '1',
    email: 'test@example.com',
    full_name: 'Test User',
    role: 'DEVELOPER'
  }
  
  useAuthStore.setState({
    user: user || defaultUser,
    token: 'mock-jwt-token',
    isAuthenticated: true
  })
}

/**
 * Clear authentication in test environment
 */
export function clearAuth() {
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false
  })
}

/**
 * Set authenticated user with specific role
 * 
 * @param {string} role - User role (DEVELOPER, LEAD, PM, QA, DEVOPS, HR, CEO)
 */
export function setAuthUserWithRole(role) {
  setAuthUser({
    id: '1',
    email: `${role.toLowerCase()}@example.com`,
    full_name: `Test ${role}`,
    role: role
  })
}
