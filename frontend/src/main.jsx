import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

// Self-hosted variable fonts (no external CDN request).
import '@fontsource-variable/inter';
import '@fontsource-variable/jetbrains-mono';

import './index.css';
import App from './App.jsx';
import { ColorModeProvider } from './theme/ColorModeContext';
import { ToastProvider } from './components/common/Toast';
import { AuthProvider } from './auth/AuthContext';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ColorModeProvider>
      <ToastProvider>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </ToastProvider>
    </ColorModeProvider>
  </StrictMode>,
);
