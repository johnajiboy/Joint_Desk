import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import Landing from './pages/Landing'
import Patient from './pages/Patient'
import Queue from './pages/Queue'
import Results from './pages/Results'
import Week from './pages/Week'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<AppShell />}>
          <Route path="/queue" element={<Queue />} />
          <Route path="/patient/:id" element={<Patient />} />
          <Route path="/week" element={<Week />} />
          <Route path="/results" element={<Results />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
