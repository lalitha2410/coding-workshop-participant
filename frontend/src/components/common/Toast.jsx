/** Lightweight snackbar feedback for CRUD actions. useToast().success/error(msg). */

import { createContext, useCallback, useContext, useState } from 'react';
import { Snackbar, Alert } from '@mui/material';

const ToastContext = createContext({ success: () => {}, error: () => {}, info: () => {} });

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null); // { severity, message }

  const show = useCallback((severity, message) => setToast({ severity, message, key: Date.now() }), []);
  const value = {
    success: (m) => show('success', m),
    error: (m) => show('error', m),
    info: (m) => show('info', m),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Snackbar
        key={toast?.key}
        open={Boolean(toast)}
        autoHideDuration={4000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        {toast ? (
          <Alert severity={toast.severity} variant="standard" onClose={() => setToast(null)} sx={{ boxShadow: 3 }}>
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
