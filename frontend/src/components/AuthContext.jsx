import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('civicline_user')
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  })

  const login = (userData) => {
    setUser(userData)
    try {
      localStorage.setItem('civicline_user', JSON.stringify(userData))
    } catch (e) {
      console.error('Failed to persist user session', e)
    }
  }

  const logout = () => {
    setUser(null)
    try {
      localStorage.removeItem('civicline_user')
    } catch (e) {
      console.error('Failed to remove user session', e)
    }
  }

  const isVerified = Boolean(user && user.email && user.verified)

  return (
    <AuthContext.Provider value={{ user, isVerified, login, logout }}>
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
