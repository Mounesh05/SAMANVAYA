import { http, HttpResponse } from 'msw'

const API_BASE = 'http://localhost:8001/api'

export const handlers = [
  // Auth endpoints
  http.post(`${API_BASE}/auth/login`, async ({ request }) => {
    const { email, password } = await request.json()
    
    if (email === 'test@example.com' && password === 'password') {
      return HttpResponse.json({
        access_token: 'mock-jwt-token',
        token_type: 'bearer',
        user: {
          id: '1',
          email: 'test@example.com',
          full_name: 'Test User',
          role: 'DEVELOPER'
        }
      })
    }
    
    return new HttpResponse(null, { status: 401 })
  }),
  
  http.get(`${API_BASE}/auth/me`, () => {
    return HttpResponse.json({
      id: '1',
      email: 'test@example.com',
      full_name: 'Test User',
      role: 'DEVELOPER'
    })
  }),
  
  // Projects endpoints
  http.get(`${API_BASE}/projects`, () => {
    return HttpResponse.json([
      {
        id: '1',
        name: 'Test Project',
        description: 'A test project',
        status: 'active',
        created_at: '2024-01-01T00:00:00Z'
      }
    ])
  }),
  
  http.post(`${API_BASE}/projects`, async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({
      id: '2',
      ...body,
      created_at: new Date().toISOString()
    }, { status: 201 })
  }),
  
  // Tasks endpoints
  http.get(`${API_BASE}/tasks`, ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    
    const allTasks = [
      { id: '1', title: 'Task 1', status: 'todo' },
      { id: '2', title: 'Task 2', status: 'in_progress' },
      { id: '3', title: 'Task 3', status: 'done' }
    ]
    
    return HttpResponse.json(
      status ? allTasks.filter(t => t.status === status) : allTasks
    )
  }),
  
  // Sprints endpoints
  http.get(`${API_BASE}/sprints`, () => {
    return HttpResponse.json([
      {
        id: '1',
        name: 'Sprint 1',
        start_date: '2024-01-01',
        end_date: '2024-01-14',
        status: 'active'
      }
    ])
  }),
  
  // Stories endpoints
  http.get(`${API_BASE}/stories`, () => {
    return HttpResponse.json([
      {
        id: '1',
        title: 'User Story 1',
        description: 'As a user, I want...',
        status: 'in_progress'
      }
    ])
  }),
  
  // Teams endpoints
  http.get(`${API_BASE}/teams`, () => {
    return HttpResponse.json([
      {
        id: '1',
        name: 'Development Team',
        members: []
      }
    ])
  }),
  
  // Employees endpoints
  http.get(`${API_BASE}/employees`, () => {
    return HttpResponse.json([
      {
        id: '1',
        full_name: 'Test User',
        email: 'test@example.com',
        role: 'DEVELOPER'
      }
    ])
  }),
  
  // Error simulation handlers (can be activated in tests)
  http.get(`${API_BASE}/error/500`, () => {
    return new HttpResponse(null, { status: 500 })
  }),
  
  http.get(`${API_BASE}/error/network`, () => {
    return HttpResponse.error()
  })
]
