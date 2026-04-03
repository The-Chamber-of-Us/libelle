import Navbar from '../components/layout/Navbar'
import Footer from '../components/layout/Footer'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import abouthero from '../assets/abouthero.svg'
import dragonfly from '../assets/dragonfly.svg'
import whyjoin from '../assets/whyjoin.svg'

export default function About() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-[#F8FAFF]">
      <section className="relative overflow-hidden bg-gradient-to-b from-libelle-bg to-[#F8FAFF]">
        <Navbar />

        <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-10 px-4 pb-16 pt-8 sm:px-6 sm:pb-20 sm:pt-10 lg:flex-row lg:justify-between lg:gap-[70px] lg:px-8 lg:pb-24">
          <div className="w-full max-w-[580px]">
            <div className="flex flex-col gap-9 rounded-[10px] py-2 sm:py-4 lg:px-[30px] lg:py-10">
              <div className="flex flex-col gap-6 sm:gap-9">
                <h1 className="font-sans text-[32px] font-black leading-[38.4px] text-black sm:text-[49px] sm:font-bold sm:leading-[58.8px] lg:text-[61px] lg:font-extrabold lg:leading-[69.8px]">
                  A Tool for Purpose-Driven Collaboration
                </h1>

                <p className="font-sans text-[18px] leading-[23.8px] text-[#72727B] sm:text-[20px] sm:leading-[29.2px] lg:text-[25px] lg:font-medium lg:leading-[33.3px]">
                  Libelle is an open-source tool that makes it easy for volunteers to be matched to
                  the work that needs them most.
                </p>
              </div>

              <Link
                to="/get-involved"
                className="inline-flex w-fit items-center gap-3 rounded-full bg-gradient-to-r from-libelle-indigo to-[#8B5CF6] px-6 py-3 text-libelle-bg shadow-libelle transition hover:opacity-90 sm:px-7 sm:py-[14px]"
              >
                <span className="font-sans text-[18px] font-bold sm:text-[24px]">Get Involved</span>
                <ArrowRight className="h-[17px] w-[17px] text-white sm:h-7 sm:w-7" />
              </Link>
            </div>
          </div>

          <div className="h-auto w-full max-w-[385px] overflow-hidden rounded-[10px] bg-gray-200 shadow-libelle">
            <img
              src={abouthero}
              alt="Illustration of volunteers collaborating on a project"
              className="h-auto w-full object-cover"
            />
          </div>
        </div>
      </section>

      <section className="bg-[#F8FAFF] px-4 py-[70px] sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-12 lg:flex-row lg:justify-between lg:gap-24">
          <div className="w-full max-w-[487px]">
            <div className="flex flex-col gap-6">
              <h2 className="font-sans text-[29px] font-bold leading-[34.8px] text-black sm:text-[39px] sm:leading-[46.8px] lg:text-[49px] lg:leading-[58.8px]">
                About Libelle
              </h2>

              <div className="flex flex-col gap-6 sm:gap-9">
                <p className="font-sans text-[16px] leading-[22.4px] text-libelle-text sm:text-[20px] sm:leading-[29.2px]">
                  Libelle is a new experiment built by volunteers from The Chamber of Us. The idea
                  is simple: help people offer their unique skills — from code and design to
                  leadership and art — to projects that matter.
                </p>

                <p className="font-sans text-[16px] leading-[22.4px] text-libelle-text sm:text-[20px] sm:leading-[29.2px]">
                  “Libelle” means dragonfly — a symbol of agility and balance across cultures.
                  Dragonflies are among the most agile creatures on earth — a fitting metaphor for
                  what this tool enables: fast, flexible connection between people and purpose.
                </p>
              </div>
            </div>
          </div>

          <div className="flex h-[210px] w-[210px] items-center justify-center rounded-full bg-white shadow-libelle sm:h-[252px] sm:w-[252px] lg:h-[300px] lg:w-[300px]">
            <img
              src={dragonfly}
              alt="Dragonfly icon"
              className="w-[163px] object-contain sm:w-[196px] lg:w-[233px]"
            />
          </div>
        </div>
      </section>

      <section className="bg-[#F8FAFF] px-4 py-[70px] sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 lg:flex-row lg:items-center lg:justify-between lg:gap-[70px]">
          <div className="order-2 w-full max-w-[417px] lg:order-2">
            <div className="flex flex-col gap-6">
              <h2 className="font-sans text-[29px] font-bold leading-[34.8px] text-black sm:text-[39px] sm:leading-[46.8px] lg:text-[49px] lg:leading-[58.8px]">
                Why Join Now?
              </h2>

              <p className="font-sans text-[16px] leading-[22.4px] text-libelle-text sm:text-[20px] sm:leading-[29.2px]">
                Libelle is new, and that's the exciting part. By joining early, you're not just
                signing up to help with projects — you're helping shape how this platform itself
                grows. Every contribution makes a difference, whether that's building the tool,
                testing it, or using it to support causes you care about.
              </p>
            </div>
          </div>

          <div className="order-1 w-full max-w-[496px] lg:order-1">
            <img
              src={whyjoin}
              alt="Volunteers collaborating"
              className="h-auto w-full rounded-[999px] shadow-libelle"
            />
          </div>
        </div>
      </section>

      <section className="bg-[#F8FAFF] px-4 py-[70px] sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-6xl">
          <div className="max-w-4xl">
            <div className="flex flex-col gap-6">
              <h2 className="font-sans text-[29px] font-bold leading-[34.8px] text-black sm:text-[39px] sm:leading-[46.8px] lg:text-[49px] lg:leading-[58.8px]">
                What to Expect
              </h2>

              <p className="font-sans text-[16px] leading-[22.4px] text-libelle-text sm:text-[20px] sm:leading-[29.2px]">
                This is a live beta, powered entirely by volunteers. Things may feel a little rough
                around the edges, but the spirit is real: connecting skills to impact. If you're
                energized by collaboration and purpose, you'll fit right in.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-gradient-to-b from-[#8B5CF6] to-libelle-indigo px-4 py-[70px] sm:px-6 sm:py-[100px] lg:px-8">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-9 sm:gap-12">
          <div className="flex w-full flex-col gap-3 sm:gap-1">
            <h2 className="text-center font-sans text-[29px] font-bold leading-[34.8px] text-white sm:text-[39px] sm:leading-[46.8px] lg:text-[49px] lg:leading-[58.8px]">
              You’ve Got Experience. The World Needs It.
            </h2>
            <p className="text-center font-sans text-[18px] leading-[23.8px] text-white sm:text-[20px] sm:leading-[29.2px] lg:text-[25px] lg:font-medium lg:leading-[33.3px]">
              Join thousands of skilled volunteers making a real difference
            </p>
          </div>

          <Link
            to="/get-involved"
            className="inline-flex items-center gap-3 rounded-full bg-white px-6 py-3 shadow-libelle transition hover:opacity-90 sm:px-7 sm:py-[14px]"
          >
            <span className="font-sans text-[18px] font-bold text-black sm:text-[24px]">
              Get Involved
            </span>
            <ArrowRight className="h-[17px] w-[17px] text-black sm:h-7 sm:w-7" />
          </Link>
        </div>
      </section>

      <Footer />
    </div>
  )
}