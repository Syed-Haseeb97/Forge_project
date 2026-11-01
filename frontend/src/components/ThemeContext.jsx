import { createContext, useContext, useEffect, useState } from 'react'
import toast from 'react-hot-toast'

const ThemeContext = createContext({
  isDark: false,
  toggleTheme: () => {},
  setDark: () => {},
})

export function ThemeProvider({ children }) {
  const [isDark, setIsDark] = useState(() => {
    try {
      const saved = localStorage.getItem('janaawaz_theme') || localStorage.getItem('fordge_theme')
      if (saved) return saved === 'dark'
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
    } catch {
      return false
    }
  })

  // Apply theme to all possible root elements
  const applyThemeToDOM = (dark) => {
    try {
      const targets = [
        document.documentElement,
        document.body,
        document.getElementById('root'),
      ].filter(Boolean)

      targets.forEach(el => {
        if (dark) {
          el.classList.add('dark')
          el.setAttribute('data-theme', 'dark')
        } else {
          el.classList.remove('dark')
          el.setAttribute('data-theme', 'light')
        }
      })

      localStorage.setItem('janaawaz_theme', dark ? 'dark' : 'light')
    } catch (e) {
      console.error('Failed to sync theme classes', e)
    }
  }

  // Synchronize on mount and on isDark state change
  useEffect(() => {
    applyThemeToDOM(isDark)
  }, [isDark])

  const setDark = (dark) => {
    setIsDark(prev => {
      if (prev === dark) return prev
      applyThemeToDOM(dark)
      toast.success(dark ? 'Dark Mode Activated' : 'Light Mode Activated', {
        id: 'theme-toggle-toast',
        duration: 1500,
      })
      return dark
    })
  }

  const toggleTheme = () => {
    setIsDark(prev => {
      const next = !prev
      applyThemeToDOM(next)
      toast.success(next ? 'Dark Mode Activated' : 'Light Mode Activated', {
        id: 'theme-toggle-toast',
        duration: 1500,
      })
      return next
    })
  }

  return (
    <ThemeContext.Provider value={{ isDark, toggleTheme, setDark }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
