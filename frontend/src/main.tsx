import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { queryClient } from './lib/query'
import { UnitsProvider } from './lib/units'
import './index.css'
import 'leaflet/dist/leaflet.css'

const base = import.meta.env.BASE_URL.replace(/\/$/, '')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <UnitsProvider>
        <BrowserRouter basename={base || undefined}>
          <App />
        </BrowserRouter>
      </UnitsProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
