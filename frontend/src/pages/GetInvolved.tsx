import Navbar from '../components/layout/Navbar'
import Footer from '../components/layout/Footer'
import { IntakeForm } from '../components/intake/IntakeForm'

export default function GetInvolved() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-libelle-bg">
      <Navbar />

      <main className="px-4 py-8 sm:px-6 sm:py-10 lg:px-8 lg:py-12">
        <div className="mx-auto w-full max-w-5xl">
          <IntakeForm />
        </div>
      </main>

      <Footer />
    </div>
  )
}