import { createRoot } from 'react-dom/client';
import '@xterm/xterm/css/xterm.css';
import './styles.css';
import { Root } from './App.jsx';
import { SessionProvider } from './session.jsx';

createRoot(document.getElementById('root')).render(
  <SessionProvider>
    <Root />
  </SessionProvider>,
);
