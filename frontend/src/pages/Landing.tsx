import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

const roles = [
  'UX Designer',
  'Content Strategist',
  'Back-End Developer',
  'User Researcher',
  'Project Manager',
  'Front-End Developer',
  'Product Manager',
  'Graphic Designer'
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-libelle-bg">
      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="absolute -left-[120px] -top-[331px] w-[1440px] h-[1440px] opacity-20 pointer-events-none">
          <div className="w-full h-full bg-gradient-to-b from-libelle-indigo via-[#9747FF] to-transparent rounded-full blur-3xl" />
        </div>

        <div className="relative">
          <Navbar />

          <div className="w-full flex justify-center pt-12">
            <div className="w-[941px] px-[30px] py-10 bg-white/80 rounded-[10px] flex flex-col items-center gap-9 shadow-libelle">
              <div className="w-full flex flex-col gap-6">
                <h1 className="text-center font-sans font-extrabold text-[61px] leading-[69.8px]">
                  <span className="text-black">
                    Use your skills to create <br />
                  </span>
                  <span className="text-libelle-indigo">real impact.</span>
                </h1>

                <p className="text-center text-black font-sans font-medium text-[25px] leading-[33.3px]">
                  Libelle offers a smarter way for skilled people like you <br />
                  to contribute to what matters.
                </p>
              </div>

              <div className="flex flex-col items-center gap-6">
                <Link
                  to="/get-involved"
                  className="px-7 py-[14px] rounded-full bg-gradient-to-r from-libelle-indigo to-[#8B5CF6] text-libelle-bg shadow-libelle flex items-center gap-3"
                >
                  <span className="font-sans font-bold text-[24px]">Get Involved</span>
                  <ArrowLeft className="w-7 h-7 rotate-180 text-white" />
                </Link>

                <div className="flex items-center gap-2">
                  <div className="w-8 h-[37.82px] bg-white rounded" />
                  <div className="w-[55.5px] h-[55.5px] bg-white rounded-full shadow" />
                  <div className="text-[#72727B] text-[16px] leading-6 font-sans">
                    Powered by{' '}
                    <span className="underline">The Chamber of Us (TCUS)</span>.
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ROLE PILLS */}
          <div className="w-full flex justify-center pt-12">
            <div className="w-full bg-white/30 py-5">
              <div className="max-w-6xl mx-auto flex flex-wrap justify-center gap-[51px] px-6">
                {roles.map((r) => (
                  <div
                    key={r}
                    className="px-[30px] py-[10px] bg-white rounded-full shadow-[0px_14px_24px_rgba(79,70,229,0.05)]"
                  >
                    <span className="text-black text-[16px] leading-6 font-medium font-sans">
                      {r}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="py-[60px] pb-[70px] px-[60px] bg-gradient-to-b from-libelle-bg to-[#F8FAFF]">
        <div className="max-w-6xl mx-auto flex flex-col items-center gap-12">
          <div className="w-full flex flex-col gap-2">
            <h2 className="text-center text-black text-[49px] leading-[58.8px] font-sans font-bold">
              How It Works
            </h2>
            <p className="text-center text-[#72727B] text-[25px] leading-[33.3px] font-sans font-medium">
              Getting started with Libelle is simple and straightforward
            </p>
          </div>

          <div className="flex flex-col lg:flex-row items-center justify-center gap-5">
            <HowCard title="Share your skills" text="Tell us about your experience, skills, interests, and motivations." variant="purple" />
            <ArrowLeft className="w-12 h-12 rotate-180 text-[#6B6B6B] hidden lg:block" />
            <HowCard title="We Review" text="Our team thoughtfully reviews your profile to find where you'll thrive." variant="violet" />
            <ArrowLeft className="w-12 h-12 rotate-180 text-[#6B6B6B] hidden lg:block" />
            <HowCard title="We Connect You" text="When the right opportunity opens up, we'll reach out with a perfect match." variant="green" />
          </div>

          <Link to="/about" className="text-libelle-indigo underline text-[20px] leading-[29.2px] font-sans">
            Learn more about Libelle
          </Link>
        </div>
      </section>

      {/* WHY LIBELLE */}
      <section className="py-[70px] bg-[#F8FAFF]">
        <div className="max-w-6xl mx-auto px-6 flex flex-col lg:flex-row items-center justify-between gap-12">
          <div className="flex flex-col gap-10">
            <h2 className="text-black text-[49px] leading-[58.8px] font-sans font-bold">
              Why Libelle?
            </h2>

            <div className="flex flex-col gap-6">
              <Bullet text="Skilled volunteers are underused." />
              <Bullet text="Nonprofits lack coordination infrastructure." />
              <Bullet text="Libelle helps match people to real needs, ethically." />
            </div>

            <Link to="/about" className="text-libelle-indigo underline text-[20px] leading-[29.2px] font-sans">
              Learn more about Libelle
            </Link>
          </div>

          <div className="w-full max-w-[528px] p-[30px] bg-white rounded-[10px] shadow-libelle">
            <p className="text-black italic text-[18px] leading-6 font-sans">
              “Libelle connected me with a nonprofit that perfectly matched my skills. I'm finally making the impact I always wanted to make.”
            </p>

            <div className="flex items-center gap-4 mt-9">
              <div className="w-[50px] h-[50px] rounded-full bg-gray-200" />
              <div>
                <div className="text-libelle-text text-[16px] leading-6 font-sans">Courtney M.</div>
                <div className="text-[#72727B] text-[16px] leading-6 font-sans">UX Designer</div>
              </div>
            </div>
          </div>
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

function HowCard({
  title,
  text,
  variant
}: {
  title: string
  text: string
  variant: 'purple' | 'violet' | 'green'
}) {
  const bg =
    variant === 'green'
      ? 'from-[#16E4A0] to-libelle-emerald'
      : variant === 'violet'
      ? 'from-[#A855F7] to-[#8B5CF6]'
      : 'from-[#8B5CF6] to-libelle-indigo'

  return (
    <div className="max-w-[300px] px-5 py-10 bg-white rounded-[10px] shadow-libelle flex flex-col items-center gap-6">
      <div className={`w-[60px] h-[60px] rounded-full bg-gradient-to-b ${bg}`} />
      <div className="px-5 flex flex-col items-center gap-3">
        <div className="text-black text-[25px] leading-[33.3px] font-sans font-medium text-center">
          {title}
        </div>
        <div className="text-[#72727B] text-[16px] leading-6 font-sans text-center">
          {text}
        </div>
      </div>
    </div>
  )
}

function Bullet({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-4 max-w-[470px]">
      <div className="w-9 h-9 bg-libelle-emerald rounded" />
      <div className="text-black text-[20px] leading-[29.2px] font-sans">
        {text}
      </div>
    </div>
  )
}