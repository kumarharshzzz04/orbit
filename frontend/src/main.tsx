import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'sonner';
import { App } from './App';
import './styles/globals.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          className: 'bg-orbit-bg-card border border-orbit-border-primary text-orbit-text-primary',
          style: { boxShadow: '0 0 20px rgba(6, 182, 212, 0.1)' },
        }}
      />
    </BrowserRouter>
  </React.StrictMode>
);