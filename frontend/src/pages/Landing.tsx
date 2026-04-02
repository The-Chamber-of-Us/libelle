import Navbar from '../components/layout/Navbar'
import Footer from '../components/layout/Footer'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import TCUSlogo from '../assets/TCUSlogo.png'
import shareYourSkillsImg from '../assets/shareyourskills.svg'
import weReviewImg from '../assets/wereview.svg'
import weConnectYouImg from '../assets/weconnectyou.svg'
import whyLibelleImg from '../assets/whylibelle.svg'
import courtneyM from '../assets/courtneyM.jpg'

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
    <div className="min-h-screen overflow-x-hidden bg-libelle-bg">
      <section className="relative overflow-hidden bg-libelle-bg">
        <div className="pointer-events-none absolute left-1/2 top-[-18rem] h-[70rem] w-[70rem] -translate-x-1/2 rounded-full bg-gradient-to-b from-libelle-indigo via-[#9747FF] to-transparent opacity-20 blur-3xl" />

        <div className="relative">
          <Navbar />

          <div className="mx-auto flex w-full max-w-6xl flex-col items-center px-4 pb-12 pt-8 sm:px-6 sm:pb-14 sm:pt-10 lg:px-8 lg:pb-16">
            <div className="w-full max-w-5xl rounded-[10px] bg-white/80 px-6 py-10 shadow-libelle backdrop-blur-sm sm:px-8 sm:py-10 lg:px-[30px]">
              <div className="flex flex-col items-center gap-9">
                <div className="flex w-full flex-col gap-6">
                  <h1 className="text-center font-sans text-[32px] font-black leading-[38.4px] sm:text-[49px] sm:font-bold sm:leading-[58.8px] lg:text-[61px] lg:font-extrabold lg:leading-[69.8px]">
                    <span className="text-black">Use your skills to create </span>
                    <br className="hidden sm:block" />
                    <span className="text-libelle-indigo">real impact.</span>
                  </h1>

                  <p className="text-center font-sans text-[18px] leading-[23.8px] text-black sm:text-[20px] sm:leading-[29.2px] lg:text-[25px] lg:font-medium lg:leading-[33.3px]">
                    Libelle offers a smarter way for skilled people like you
                    <br className="hidden sm:block" /> to contribute to what matters.
                  </p>
                </div>

                <div className="flex w-full flex-col items-center gap-6">
                  <Link
                    to="/get-involved"
                    className="inline-flex items-center gap-3 rounded-full bg-gradient-to-r from-libelle-indigo to-[#8B5CF6] px-6 py-3 text-libelle-bg shadow-libelle transition hover:opacity-90 sm:px-7 sm:py-[14px]"
                  >
                    <span className="font-sans text-[18px] font-bold sm:text-[24px]">
                      Get Involved
                    </span>
                    <ArrowRight className="h-[17px] w-[17px] text-white sm:h-7 sm:w-7" />
                  </Link>

                  <div className="flex max-w-md items-center gap-2 text-center sm:max-w-none sm:text-left">
                    <img
                      src={TCUSlogo}
                      alt="The Chamber of Us logo"
                      className="h-10 w-10 rounded-full bg-white object-contain shadow sm:h-12 sm:w-12"
                    />
                    <div className="font-sans text-[14px] leading-[16.8px] text-[#72727B] sm:text-[16px] sm:leading-6">
                      Powered by <span className="underline">The Chamber of Us (TCUS)</span>.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="w-full bg-white/30 py-5">
            <div className="mx-auto flex w-full max-w-6xl flex-wrap justify-center gap-3 px-4 sm:gap-4 sm:px-6 lg:gap-5 lg:px-8">
              {roles.map((role) => (
                <div
                  key={role}
                  className="rounded-full bg-white px-4 py-2 shadow-[0px_14px_24px_rgba(79,70,229,0.05)] sm:px-5 sm:py-2.5 lg:px-[30px] lg:py-[10px]"
                >
                  <span className="font-sans text-[13px] font-medium leading-6 text-black sm:text-[14px] lg:text-[16px]">
                    {role}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="bg-gradient-to-b from-libelle-bg to-[#F8FAFF] px-4 py-[70px] sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-12">
          <div className="flex w-full flex-col gap-3">
            <h2 className="text-center font-sans text-[29px] font-bold leading-[34.8px] text-black sm:text-[39px] sm:leading-[46.8px] lg:text-[49px] lg:leading-[58.8px]">
              How It Works
            </h2>
            <p className="text-center font-sans text-[16px] leading-[22.4px] text-[#72727B] sm:text-[20px] sm:leading-[29.2px] lg:text-[25px] lg:font-medium lg:leading-[33.3px]">
              Getting started with Libelle is simple and straightforward
            </p>
          </div>

          <div className="grid w-full grid-cols-1 gap-5 md:grid-cols-3 md:items-stretch">
            <HowCard
              title="Share your skills"
              text="Tell us about your experience, skills, interests, and motivations."
              variant="purple"
              image={shareYourSkillsImg}
            />
            <HowCard
              title="We Review"
              text="Our team thoughtfully reviews your profile to find where you'll thrive."
              variant="violet"
              image={weReviewImg}
            />
            <HowCard
              title="We Connect You"
              text="When the right opportunity opens up, we'll reach out with a perfect match."
              variant="green"
              image={weConnectYouImg}
            />
          </div>

          <Link
            to="/about"
            className="font-sans text-[16px] leading-[22.4px] text-libelle-indigo underline sm:text-[20px] sm:leading-[29.2px]"
          >
            Learn more about Libelle
          </Link>
        </div>
      </section>

      <section className="bg-[#F8FAFF] px-4 py-[70px] sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex max-w-2xl flex-col gap-8 lg:gap-10">
            <h2 className="font-sans text-[29px] font-bold leading-[34.8px] text-black sm:text-[39px] sm:leading-[46.8px] lg:text-[49px] lg:leading-[58.8px]">
              Why Libelle?
            </h2>

            <div className="flex flex-col gap-4 sm:gap-5 lg:gap-6">
              <Bullet text="Skilled volunteers are underused." />
              <Bullet text="Nonprofits lack coordination infrastructure." />
              <Bullet text="Libelle helps match people to real needs, ethically." />
            </div>

            <Link
              to="/about"
              className="font-sans text-[16px] leading-[22.4px] text-libelle-indigo underline sm:text-[20px] sm:leading-[29.2px]"
            >
              Learn more about Libelle
            </Link>
          </div>

          <div className="w-full max-w-[528px] rounded-[10px] bg-white p-6 shadow-libelle sm:p-[30px]">
            <p className="font-sans text-[16px] italic leading-6 text-black sm:text-[18px]">
              “Libelle connected me with a nonprofit that perfectly matched my skills. I'm finally
              making the impact I always wanted to make.”
            </p>

            <div className="mt-9 flex items-center gap-4">
              <img
                src={courtneyM}
                alt="profile picture of Courtney M."
                className="h-[50px] w-[50px] shrink-0 rounded-full object-cover"
              />

              <div className="flex flex-col">
                <div className="font-sans text-[16px] leading-6 text-libelle-text">
                  Courtney M.
                </div>
                <div className="font-sans text-[16px] leading-6 text-[#72727B]">
                  UX Designer
                </div>
              </div>
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

function HowCard({
  title,
  text,
  variant,
  image
}: {
  title: string
  text: string
  variant: 'purple' | 'violet' | 'green'
  image: string
}) {
  const bg =
    variant === 'green'
      ? 'from-[#16E4A0] to-libelle-emerald'
      : variant === 'violet'
        ? 'from-[#A855F7] to-[#8B5CF6]'
        : 'from-[#8B5CF6] to-libelle-indigo'

  return (
    <div className="flex h-full w-full flex-col items-center gap-6 rounded-[10px] bg-white px-5 py-8 shadow-libelle sm:px-6 sm:py-10">
      <div
        className={`flex h-[60px] w-[60px] items-center justify-center rounded-full bg-gradient-to-b ${bg}`}
      >
        <img src={image} alt="" className="h-7 w-7 object-contain" />
      </div>

      <div className="flex w-full max-w-[300px] flex-col items-center gap-3 px-2 sm:px-5">
        <div className="text-center font-sans text-[20px] font-medium leading-6 text-black sm:text-[25px] sm:leading-[33.3px]">
          {title}
        </div>
        <div className="text-center font-sans text-[16px] leading-[22.4px] text-[#72727B] sm:leading-6">
          {text}
        </div>
      </div>
    </div>
  )
}

function Bullet({ text }: { text: string }) {
  return (
    <div className="flex max-w-[470px] items-center gap-3 sm:gap-4">
      <div className="flex h-6 w-6 shrink-0 items-center justify-center sm:h-9 sm:w-9">
        <img src={whyLibelleImg} alt="bullet icon" className="h-5 w-5 object-contain" />
      </div>
      <div className="font-sans text-[16px] leading-[22.4px] text-black sm:text-[20px] sm:leading-[29.2px]">
        {text}
      </div>
    </div>
  )
}