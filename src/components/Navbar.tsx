import { NavLink, Link } from 'react-router-dom'

export default function Navbar() {
  const linkBase =
    'text-[18px] font-medium leading-[28.8px] tracking-[0.18px]'
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `${linkBase} ${isActive ? 'text-libelle-indigo' : 'text-black'} hover:text-libelle-indigo transition`

  return (
    <div className="w-full flex justify-center pt-5">
      <div className="w-[941px] px-2 py-[6px] bg-white shadow-libelle rounded-full flex items-center justify-between">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2 pl-2">
          <div className="w-[38.88px] h-[38.88px] bg-libelle-bg rounded-full" />
          <div className="w-[30.2px] h-[19.18px] relative bg-libelle-bg overflow-hidden rounded-sm">
            <div className="absolute inset-0 bg-gradient-to-b from-[#9747FF] to-libelle-indigo" />
          </div>

          <div className="flex items-center gap-2">
            <div className="text-black text-[20px] leading-[29.2px] font-normal font-sans">
              Libelle
            </div>
            <div className="text-[#72727B] text-[13px] leading-[15.6px] font-normal font-sans">
              by The Chamber of Us
            </div>
          </div>
        </Link>

        {/* Links */}
        <div className="flex items-center gap-12 pr-2">
          <NavLink to="/" className={navLinkClass}>
            Home
          </NavLink>

          <NavLink to="/about" className={navLinkClass}>
            About
          </NavLink>

          <Link
            to="/get-involved"
            className="px-6 py-2 bg-libelle-indigo text-white rounded-full flex items-center justify-center"
          >
            <span className={linkBase + ' text-white'}>Get Involved</span>
          </Link>
        </div>
      </div>
    </div>
  )
}