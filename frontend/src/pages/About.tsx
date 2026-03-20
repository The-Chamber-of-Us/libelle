import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import abouthero from '../assets/abouthero.svg'
import dragonfly from '../assets/dragonfly.svg'

export default function About() {
  return (
    <div className="min-h-screen bg-[#F8FAFF]">
      <section className="relative overflow-hidden bg-gradient-to-b from-libelle-bg to-[#F8FAFF]">
        <Navbar />

        <div className="max-w-6xl mx-auto px-6 pt-20 pb-24 flex flex-col lg:flex-row items-center justify-center gap-[70px]">
          <div className="w-full max-w-[580px]">
            <div className="px-[30px] py-10 rounded-[10px] flex flex-col gap-12">
              <div className="flex flex-col gap-9">
                <h1 className="text-black text-[61px] leading-[69.8px] font-sans font-extrabold">
                  A Tool for Purpose-Driven Collaboration
                </h1>
                <p className="text-[#72727B] text-[25px] leading-[33.3px] font-sans font-medium">
                  Libelle is an open-source tool that makes it easy for volunteers to be matched to the work that needs them most.
                </p>
              </div>

              <Link
                to="/get-involved"
                className="px-7 py-[14px] rounded-full bg-gradient-to-r from-libelle-indigo to-[#8B5CF6] text-libelle-bg shadow-libelle flex items-center gap-3 w-fit"
              >
                <span className="font-sans font-bold text-[24px]">Get Involved</span>
                <ArrowLeft className="w-7 h-7 rotate-180 text-white" />
              </Link>
            </div>
          </div>

          <div className="w-[385px] h-[483px] rounded-[10px] overflow-hidden shadow-libelle bg-gray-200">
            <img
              src={abouthero}
              alt="Illustration of volunteers collaborating on a project"
              className="w-full h-full object-cover"
            />
          </div>
        </div>
      </section>

      {/* ABOUT BODY */}
      <section className="max-w-6xl mx-auto px-6 py-16 flex flex-col lg:flex-row items-center justify-center gap-24">
        <div className="w-full max-w-[487px] flex flex-col gap-6">
          <h2 className="text-black text-[49px] leading-[58.8px] font-sans font-bold">
            About Libelle
          </h2>

          <div className="flex flex-col gap-9">
            <p className="text-libelle-text text-[20px] leading-[29.2px] font-sans">
              Libelle is a new experiment built by volunteers from The Chamber of Us. The idea is simple: help people offer their unique skills — from code and design to leadership and art — to projects that matter.
            </p>

            <p className="text-libelle-text text-[20px] leading-[29.2px] font-sans">
              “Libelle” means dragonfly — a symbol of agility and balance across cultures. Dragonflies are among the most agile creatures on earth — a fitting metaphor for what this tool enables: fast, flexible connection between people and purpose.
            </p>
          </div>
        </div>

        <div className="w-[300px] h-[300px] bg-white rounded-full shadow-libelle relative">
          <img
            src={dragonfly}
            alt="Dragonfly icon"
            className="w-[233px] h-[148px] object-contain absolute top-[90px] left-1/2 -translate-x-1/2"
          />
        </div>
      </section>

      {/* WHAT TO EXPECT */}
      <section className="max-w-6xl mx-auto px-6 py-20 flex flex-col lg:flex-row items-center justify-center gap-24">
        <div className="w-full max-w-[880px] flex flex-col gap-6">
          <h2 className="text-black text-[49px] leading-[58.8px] font-sans font-bold mb-6">
            What to Expect
          </h2>
          <p className="text-libelle-text text-[20px] leading-[29.2px] font-sans max-w-3xl">
            This is a live beta, powered entirely by volunteers. Things may feel a little rough around the edges, but the spirit is real: connecting skills to impact. If you're energized by collaboration and purpose, you'll fit right in.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="px-[60px] py-[100px] bg-gradient-to-b from-[#8B5CF6] to-libelle-indigo">
        <div className="max-w-6xl mx-auto flex flex-col items-center gap-12">
          <div className="w-full flex flex-col gap-1">
            <h2 className="text-center text-white text-[49px] leading-[58.8px] font-sans font-bold">
              You’ve Got Experience. The World Needs It.
            </h2>
            <p className="text-center text-white text-[25px] leading-[33.3px] font-sans font-medium">
              Join thousands of skilled volunteers making a real difference
            </p>
          </div>

          <Link
            to="/get-involved"
            className="px-7 py-[14px] bg-white rounded-full shadow-libelle flex items-center gap-3"
          >
            <span className="text-black font-sans font-bold text-[24px]">Get Involved</span>
            <ArrowLeft className="w-7 h-7 rotate-180 text-black" />
          </Link>
        </div>
      </section>

      <Footer />
    </div>
  )
}