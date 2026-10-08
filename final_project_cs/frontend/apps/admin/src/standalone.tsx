import { createRoot } from 'react-dom/client';
import AdminApp from './components/AdminApp';
import './app/globals.css';
createRoot(document.getElementById('root')!).render(<AdminApp mode="demo" standalone initialPath={location.hash.slice(1) || '/login'} />);
