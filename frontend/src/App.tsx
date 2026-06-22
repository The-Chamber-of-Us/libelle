import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import About from './pages/About'
import GetInvolved from './pages/GetInvolved'
import Inbox from './pages/Inbox'
import Ops from './pages/Ops'
import ParserResults from './pages/ParserResults'
import Errors from './pages/Errors'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/about" element={<About />} />
        <Route path="/get-involved" element={<GetInvolved />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/ops" element={<Ops />} />
        <Route path="/parser-results" element={<ParserResults />} />
        <Route path="/errors" element={<Errors />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
