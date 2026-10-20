import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell, Loading } from './components/AppShell'
import Landing from './pages/Landing'
import Patient from './pages/Patient'
import Queue from './pages/Queue'
import Week from './pages/Week'

// Results carries the chart library; load it only when the page is opened.
const Results = lazy(() => import('./pages/Results'))

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<AppShell />}>
          <Route path="/queue" element={<Queue />} />
          <Route path="/patient/:id" element={<Patient />} />
          <Route path="/week" element={<Week />} />
          <Route path="/results" element={<Suspense fallback={<Loading />}><Results /></Suspense>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
