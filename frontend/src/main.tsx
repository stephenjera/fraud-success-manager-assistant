import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
// import { ReactQueryDevtools } from '@tanstack/react-query-devtools'; // Optional DevTools
import { AppRouterProvider } from './router';
import './index.css';

// 1. Create a client instance outside the component
const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* 2. Wrap your App component in the Provider */}
    <QueryClientProvider client={queryClient}>
      <AppRouterProvider />
      
      {/* 3. Optional: This renders the visual DevTools panel in development */}
      {/* <ReactQueryDevtools initialIsOpen={false} /> */}
    </QueryClientProvider>
  </StrictMode>
);