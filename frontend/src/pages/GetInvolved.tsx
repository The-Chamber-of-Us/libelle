import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { IntakeForm } from '../components/IntakeForm'

export default function GetInvolved() {
  return (
    <div className="min-h-screen bg-libelle-bg">
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 py-12">
        <IntakeForm />
      </div>
      <Footer />
    </div>
  )
}