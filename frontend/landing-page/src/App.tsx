import libelleMark from "./assets/libelle-mark.svg";

type RoleChipProps = { label: string };

function RoleChip({ label }: RoleChipProps) {
  return (
    <span className="inline-flex items-center justify-center rounded-full bg-white px-7 py-2.5 text-[16px] font-medium leading-6 text-black shadow-soft">
      {label}
    </span>
  );
}

type StepCardProps = {
  title: string;
  description: string;
  iconBg: string; // tailwind gradient class string
  iconShape: "share" | "review" | "connect";
};

function StepIcon({ iconShape }: { iconShape: StepCardProps["iconShape"] }) {
  // Minimal inline SVGs (clean, no external icon deps)
  if (iconShape === "share") {
    return (
      <svg viewBox="0 0 48 48" className="h-12 w-12">
        <path
          d="M30 12l-18 12 18 12"
          fill="none"
          stroke="white"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M30 12v10c0 1-1 2-2 2H12"
          fill="none"
          stroke="white"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  if (iconShape === "review") {
    return (
      <svg viewBox="0 0 48 48" className="h-12 w-12">
        <path
          d="M14 14h20v14H19l-5 6V14z"
          fill="none"
          stroke="white"
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <path
          d="M18 21h12"
          stroke="white"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 48 48" className="h-12 w-12">
      <path
        d="M18 25l4 4 10-10"
        fill="none"
        stroke="white"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M24 44c11 0 20-9 20-20S35 4 24 4 4 13 4 24s9 20 20 20z"
        fill="none"
        stroke="white"
        strokeWidth="3"
      />
    </svg>
  );
}

function StepCard({ title, description, iconBg, iconShape }: StepCardProps) {
  return (
    <div className="w-full max-w-[300px] rounded-[10px] bg-white px-5 py-10 shadow-hero">
      <div className="mx-auto mb-6 grid h-15 w-15 place-items-center rounded-full">
        <div className={`grid h-15 w-15 place-items-center rounded-full ${iconBg}`}>
          <StepIcon iconShape={iconShape} />
        </div>
      </div>

      <div className="mx-auto flex max-w-[300px] flex-col items-center gap-3 px-5">
        <h3 className="text-center text-[25px] font-medium leading-[33.3px] text-black">
          {title}
        </h3>
        <p className="text-center text-[16px] font-normal leading-6 text-libelle-slate">
          {description}
        </p>
      </div>
    </div>
  );
}

function ArrowDivider() {
  return (
    <div className="hidden h-12 w-12 items-center justify-center md:flex">
      <svg viewBox="0 0 48 48" className="h-12 w-12">
        <path
          d="M14 24h20"
          stroke="#6B6B6B"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <path
          d="M28 16l8 8-8 8"
          fill="none"
          stroke="#6B6B6B"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function PrimaryButton({ children }: { children: React.ReactNode }) {
  return (
    <button className="inline-flex items-center gap-3 rounded-full bg-gradient-to-r from-libelle-indigo to-libelle-violet px-7 py-3.5 text-[24px] font-bold text-libelle-hero shadow-hero transition-transform hover:scale-[1.01] active:scale-[0.99]">
      <span className="leading-none">{children}</span>
      <span className="grid h-7 w-7 place-items-center">
        <svg viewBox="0 0 28 28" className="h-7 w-7">
          <path
            d="M8 14h12"
            stroke="white"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <path
            d="M14 8l6 6-6 6"
            fill="none"
            stroke="white"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    </button>
  );
}

function SecondaryButton({ children }: { children: React.ReactNode }) {
  return (
    <button className="inline-flex items-center gap-3 rounded-full bg-white px-7 py-3.5 text-[24px] font-bold text-black shadow-hero transition-transform hover:scale-[1.01] active:scale-[0.99]">
      <span className="leading-none">{children}</span>
      <span className="grid h-7 w-7 place-items-center">
        <svg viewBox="0 0 28 28" className="h-7 w-7">
          <path
            d="M8 14h12"
            stroke="black"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <path
            d="M14 8l6 6-6 6"
            fill="none"
            stroke="black"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    </button>
  );
}

function TextLink({ children }: { children: React.ReactNode }) {
  return (
    <a
      href="#"
      className="text-center text-[20px] font-normal leading-[29.2px] text-libelle-indigo underline underline-offset-4"
    >
      {children}
    </a>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-white font-inter">
      {/* HERO */}
      <section className="relative overflow-hidden bg-libelle-hero">
        {/* big background circle/shape */}
        <div className="pointer-events-none absolute left-[-120px] top-[-331px] h-[1440px] w-[1440px] rounded-full bg-gradient-to-b from-libelle-violet/20 to-libelle-indigo/20" />

        <div className="mx-auto flex min-h-[800px] max-w-[1200px] flex-col items-center gap-12 px-6 pt-5">
          {/* NAVBAR */}
          <header className="mt-4 w-full">
            <div className="mx-auto flex w-full max-w-[941px] items-center justify-between rounded-full bg-white px-4 py-1.5 shadow-hero">
              <div className="flex items-center gap-2">
                <div className="h-10 w-10 rounded-full bg-libelle-hero" />
                <img
                  src={libelleMark}
                  alt="Libelle mark"
                  className="h-6 w-auto"
                />
                <div className="ml-1 flex items-center gap-2">
                  <span className="text-center text-[20px] font-normal leading-[29.2px] text-black">
                    Libelle
                  </span>
                  <span className="text-center text-[13px] font-normal leading-[15.6px] text-libelle-slate">
                    by The Chamber of Us
                  </span>
                </div>
              </div>

              <nav className="hidden items-center gap-12 md:flex">
                <a
                  href="#"
                  className="text-center text-[18px] font-medium leading-[28.8px] tracking-[0.18px] text-libelle-indigo"
                >
                  Home
                </a>
                <a
                  href="#"
                  className="text-center text-[18px] font-medium leading-[28.8px] tracking-[0.18px] text-black"
                >
                  About
                </a>
                <button className="rounded-full bg-libelle-indigo px-6 py-2 text-center text-[18px] font-medium leading-[28.8px] tracking-[0.18px] text-white">
                  Get Involved
                </button>
              </nav>

              {/* mobile CTA */}
              <button className="rounded-full bg-libelle-indigo px-4 py-2 text-[14px] font-semibold text-white md:hidden">
                Get Involved
              </button>
            </div>
          </header>

          {/* HERO CARD */}
          <div className="w-full max-w-[941px] rounded-[10px] bg-white/80 px-8 py-10 shadow-hero backdrop-blur">
            <div className="flex flex-col items-center gap-9">
              <div className="flex w-full flex-col gap-6">
                <h1 className="text-center text-[44px] font-extrabold leading-tight text-black md:text-[61px] md:leading-[69.8px]">
                  Use your skills to create <br />
                  <span className="text-libelle-indigo">real impact.</span>
                </h1>
                <p className="text-center text-[18px] font-medium leading-snug text-black md:text-[25px] md:leading-[33.3px]">
                  Libelle offers a smarter way for skilled people like you <br />
                  to contribute to what matters.
                </p>
              </div>

              <div className="flex flex-col items-center gap-6">
                <PrimaryButton>Get Involved</PrimaryButton>

                <div className="flex items-center gap-2">
                  <div className="h-9 w-8 rounded bg-white" />
                  <div className="grid h-14 w-14 place-items-center rounded-full bg-white shadow-soft">
                    <span className="text-sm font-semibold text-libelle-indigo">
                      TCUS
                    </span>
                  </div>
                  <div className="text-center text-[16px] leading-6 text-libelle-slate">
                    Powered by{" "}
                    <span className="underline underline-offset-4">
                      The Chamber of Us (TCUS)
                    </span>
                    .
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ROLE CHIPS ROW */}
          <div className="w-full bg-white/30 py-5">
            <div className="mx-auto flex max-w-[1200px] flex-wrap justify-center gap-4 px-6">
              {[
                "UX Designer",
                "Content Strategist",
                "Back-End Developer",
                "User Researcher",
                "Project Manager",
                "Front-End Developer",
                "Product Manager",
                "Graphic Designer"
              ].map((r) => (
                <RoleChip key={r} label={r} />
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="bg-gradient-to-b from-libelle-hero via-libelle-hero to-libelle-page px-6 py-[70px]">
        <div className="mx-auto flex max-w-[1200px] flex-col items-center gap-12">
          <div className="flex w-full flex-col gap-2">
            <h2 className="text-center text-[36px] font-bold leading-tight text-black md:text-[49px] md:leading-[58.8px]">
              How It Works
            </h2>
            <p className="text-center text-[18px] font-medium leading-snug text-libelle-slate md:text-[25px] md:leading-[33.3px]">
              Getting started with Libelle is simple and straightforward
            </p>
          </div>

          <div className="flex w-full flex-col items-center justify-center gap-6 md:flex-row md:gap-5">
            <StepCard
              title="Share your skills"
              description="Tell us about your experience, skills, interests, and motivations."
              iconBg="bg-gradient-to-b from-libelle-violet to-libelle-indigo"
              iconShape="share"
            />
            <ArrowDivider />
            <StepCard
              title="We Review"
              description="Our team thoughtfully reviews your profile to find where you'll thrive."
              iconBg="bg-gradient-to-b from-[#A855F7] to-libelle-violet"
              iconShape="review"
            />
            <ArrowDivider />
            <StepCard
              title="We Connect You"
              description="When the right opportunity opens up, we'll reach out with a perfect match."
              iconBg="bg-gradient-to-b from-[#16E4A0] to-[#10B981]"
              iconShape="connect"
            />
          </div>

          <TextLink>Learn more about Libelle</TextLink>
        </div>
      </section>

      {/* WHY LIBELLE */}
      <section className="bg-libelle-page px-6 py-[70px]">
        <div className="mx-auto grid max-w-[1200px] grid-cols-1 items-center gap-10 md:grid-cols-2">
          <div className="flex flex-col gap-10">
            <h2 className="text-[36px] font-bold leading-tight text-black md:text-[49px] md:leading-[58.8px]">
              Why Libelle?
            </h2>

            <div className="flex flex-col gap-6">
              {[
                "Skilled volunteers are underused.",
                "Nonprofits lack coordination infrastructure.",
                "Libelle helps match people to real needs, ethically."
              ].map((t) => (
                <div key={t} className="flex items-center gap-4">
                  <span className="grid h-9 w-9 place-items-center rounded bg-[#10B981]">
                    <svg viewBox="0 0 24 24" className="h-5 w-5">
                      <path
                        d="M20 6L9 17l-5-5"
                        fill="none"
                        stroke="white"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                  <p className="text-[20px] font-normal leading-[29.2px] text-black">
                    {t}
                  </p>
                </div>
              ))}
            </div>

            <TextLink>Learn more about Libelle</TextLink>
          </div>

          <div className="rounded-[10px] bg-white p-8 shadow-hero">
            <p className="text-[18px] italic leading-6 text-black">
              “Libelle connected me with a nonprofit that perfectly matched my
              skills. I'm finally making the impact I always wanted to make.”
            </p>

            <div className="mt-8 flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-libelle-hero" />
              <div>
                <div className="text-[16px] leading-6 text-[#1F2937]">
                  Courtney M.
                </div>
                <div className="text-[16px] leading-6 text-libelle-slate">
                  UX Designer
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="bg-gradient-to-b from-libelle-violet to-libelle-indigo px-6 py-[100px]">
        <div className="mx-auto flex max-w-[1200px] flex-col items-center gap-12">
          <div className="flex w-full flex-col gap-1">
            <h2 className="text-center text-[34px] font-bold leading-tight text-white md:text-[49px] md:leading-[58.8px]">
              You’ve Got Experience. The World Needs It.
            </h2>
            <p className="text-center text-[18px] font-medium leading-snug text-white md:text-[25px] md:leading-[33.3px]">
              Join thousands of skilled volunteers making a real difference
            </p>
          </div>

          <SecondaryButton>Get Involved</SecondaryButton>
        </div>
      </section>
    </div>
  );
}
