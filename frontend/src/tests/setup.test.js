import { describe, it, expect } from 'vitest'

describe('Testing Infrastructure', () => {
  it('should run basic tests', () => {
    expect(true).toBe(true)
  })
  
  it('should have access to jsdom', () => {
    expect(typeof window).toBe('object')
    expect(typeof document).toBe('object')
  })
  
  it('should have matchMedia mock', () => {
    const result = window.matchMedia('(min-width: 768px)')
    expect(result).toBeDefined()
    expect(result.matches).toBe(false)
  })
  
  it('should have IntersectionObserver mock', () => {
    expect(typeof IntersectionObserver).toBe('function')
    const observer = new IntersectionObserver(() => {})
    expect(observer).toBeDefined()
  })
})
