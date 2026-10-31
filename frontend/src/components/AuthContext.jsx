import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem('janaawaz_token') || localStorage.getItem('civicline_token') || null
    } catch {
      return null
    }
  })

  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('janaawaz_user') || localStorage.getItem('civicline_user')
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  })

  const login = (userData, tokenString) => {
    setUser(userData)
    setToken(tokenString || null)
    try {
      localStorage.setItem('janaawaz_user', JSON.stringify(userData))
      if (tokenString) {
        localStorage.setItem('janaawaz_token', tokenString)
      }
    } catch (e) {
      console.error('Failed to persist user session', e)
    }
  }

  const logout = () => {
    setUser(null)
    setToken(null)
    try {
      localStorage.removeItem('janaawaz_user')
      localStorage.removeItem('janaawaz_token')
      localStorage.removeItem('civicline_user')
    } catch (e) {
      console.error('Failed to remove user session', e)
    }
  }

  useEffect(() => {
    const handleUnauthorized = () => {
      logout()
    }
    window.addEventListener('janaawaz_auth_logout', handleUnauthorized)
    return () => window.removeEventListener('janaawaz_auth_logout', handleUnauthorized)
  }, [])

  const role = user?.role || 'citizen'
  const isAuthority = role === 'authority'
  const isVerified = Boolean(user && user.email && (user.verified || token))

  return (
    <AuthContext.Provider value={{ user, token, role, isAuthority, isVerified, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
