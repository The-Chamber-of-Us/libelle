import { useEffect, useState } from 'react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import dragonfly from '../../assets/dragonfly.svg'

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false)
  const location = useLocation()

  const linkBase =
    'text-[18px] font-medium leading-[28.8px] tracking-[0.18px] transition'

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `${linkBase} ${isActive ? 'text-libelle-indigo' : 'text-black hover:text-libelle-indigo'}`

  useEffect(() => {
    setIsOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!isOpen) return

    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = originalOverflow
    }
  }, [isOpen])

  return (
    <>
      <header className="w-full px-4 pt-5 sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-6xl">
          <div className="flex items-center justify-between rounded-full bg-white px-3 py-[6px] shadow-libelle sm:px-4">
            {/* Brand */}
            <Link to="/" className="flex min-w-0 items-center gap-3 pl-1 sm:pl-2">
              <div className="relative flex h-[44px] w-[44px] shrink-0 items-center justify-center">
                <div className="absolute inset-0 rounded-full bg-indigo-300/30 blur-md" />
                <img
                  src={dragonfly}
                  alt="Libelle dragonfly icon"
                  className="relative z-10 h-6 w-6 object-contain"
                />
              </div>

              <div className="flex min-w-0 items-center gap-2 whitespace-nowrap">
                <span className="font-sans text-[18px] font-normal leading-none text-black sm:text-[20px]">
                  Libelle
                </span>
                <span className="hidden font-sans text-[13px] font-normal leading-none text-[#72727B] md:inline">
                  by The Chamber of Us
                </span>
              </div>
            </Link>

            {/* Desktop nav */}
            <div className="hidden items-center gap-6 pr-1 lg:flex xl:gap-12">
              <NavLink to="/" className={navLinkClass}>
                Home
              </NavLink>

              <NavLink to="/about" className={navLinkClass}>
                About
              </NavLink>

              <Link
                to="/get-involved"
                className="flex items-center justify-center rounded-full bg-libelle-indigo px-6 py-2 text-white transition hover:opacity-90"
              >
                <span className={linkBase + ' text-white'}>Get Involved</span>
              </Link>
            </div>

            {/* Mobile / tablet menu button */}
            <button
              type="button"
              aria-label={isOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={isOpen}
              onClick={() => setIsOpen((prev) => !prev)}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full text-libelle-indigo transition hover:bg-libelle-bg lg:hidden"
            >
              {isOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile / tablet dropdown */}
      {isOpen && (
        <div className="fixed inset-0 z-40 bg-black/20 lg:hidden" onClick={() => setIsOpen(false)}>
          <div
            className="absolute inset-x-4 top-20 rounded-2xl bg-white p-4 shadow-2xl sm:inset-x-6"
            onClick={(e) => e.stopPropagation()}
          >
            <nav className="flex flex-col gap-2">
              <NavLink
                to="/"
                className={({ isActive }) =>
                  [
                    'rounded-xl px-4 py-3 font-sans text-base font-medium transition',
                    isActive
                      ? 'bg-libelle-bg text-libelle-indigo'
                      : 'text-black hover:bg-libelle-bg hover:text-libelle-indigo'
                  ].join(' ')
                }
              >
                Home
              </NavLink>

              <NavLink
                to="/about"
                className={({ isActive }) =>
                  [
                    'rounded-xl px-4 py-3 font-sans text-base font-medium transition',
                    isActive
                      ? 'bg-libelle-bg text-libelle-indigo'
                      : 'text-black hover:bg-libelle-bg hover:text-libelle-indigo'
                  ].join(' ')
                }
              >
                About
              </NavLink>

              <Link
                to="/get-involved"
                className="mt-2 rounded-xl bg-libelle-indigo px-4 py-3 text-center font-sans text-base font-medium text-white transition hover:opacity-90"
              >
                Get Involved
              </Link>
            </nav>
          </div>
        </div>
      )}
    </>
  )
}