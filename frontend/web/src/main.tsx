import React from 'react';
import ReactDOM from 'react-dom/client';
import { init, retrieveLaunchParams } from '@telegram-apps/sdk';
import App from './App';
import './styles.css';
import './v2/styles.css';

// A regular browser uses real session login; never forge Telegram launch data.
try { retrieveLaunchParams(); init(); } catch { /* Web login. */ }
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
