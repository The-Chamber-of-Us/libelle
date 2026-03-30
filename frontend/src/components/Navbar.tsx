import { NavLink, Link } from 'react-router-dom'
import dragonfly from '../assets/dragonfly.svg'

export default function Navbar() {
  const linkBase =
    'text-[18px] font-medium leading-[28.8px] tracking-[0.18px]'
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `${linkBase} ${isActive ? 'text-libelle-indigo' : 'text-black'} hover:text-libelle-indigo transition`

  return (
    <div className="w-full flex justify-center pt-5">
    <div className="w-[941px] px-2 py-[6px] bg-white shadow-libelle rounded-full flex items-center justify-between overflow-hidden">
      {/* Brand */}
      <Link to="/" className="flex items-center gap-3 pl-3 pr-4 min-w-0">
        {/* Dragonfly icon with indigo background */}
        <div className="relative w-[44px] h-[44px] flex items-center justify-center shrink-0">
          <div className="absolute inset-0 rounded-full bg-indigo-300/30 blur-md" />
          <img
            src={dragonfly}
            alt="Libelle dragonfly icon"
            className="relative z-10 w-6 h-6 object-contain"
          />
        </div>

        {/* Single-line brand text */}
        <div className="flex items-center gap-2 whitespace-nowrap min-w-0">
          <span className="text-black text-[20px] leading-none font-normal font-sans">
            Libelle
          </span>
          <span className="text-[#72727B] text-[13px] leading-none font-normal font-sans">
            by The Chamber of Us
          </span>
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