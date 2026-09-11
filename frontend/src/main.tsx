import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider } from 'antd';
import ruRU from 'antd/locale/ru_RU';
import App from './App';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider locale={ruRU} theme={{ token: {
      colorPrimary: '#176c69', colorText: '#20313b', borderRadius: 8,
      fontFamily: 'Arial, sans-serif', fontSize: 16, controlHeight: 44,
    } }}>
      <App />
    </ConfigProvider>
  </StrictMode>,
);
