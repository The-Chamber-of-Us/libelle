import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import About from './pages/About'
import GetInvolved from './pages/GetInvolved'
import Inbox from './pages/Inbox'
import ParserResults from './pages/ParserResults'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/about" element={<About />} />
        <Route path="/get-involved" element={<GetInvolved />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/parser-results" element={<ParserResults />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
