import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import axios from 'axios'
import App from './App'
import { ThemeProvider } from './components/ThemeContext'
import { AuthProvider } from './components/AuthContext'
import './index.css'

// Base URL setup from environment
axios.defaults.baseURL = import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_BASE_URL || ''

// Request interceptor: attach Bearer token to all outgoing requests
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('janaawaz_token') || localStorage.getItem('civicline_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: on 401 Unauthorized, dispatch global logout event
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('janaawaz_token')
      localStorage.removeItem('janaawaz_user')
      localStorage.removeItem('civicline_user')
      window.dispatchEvent(new CustomEvent('janaawaz_auth_logout'))
    }
    return Promise.reject(error)
  }
)

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
)
