import { NavLink } from 'react-router-dom'

const tabs = [
  { to: '/inbox', label: 'Inbox' },
  { to: '/parser-results', label: 'Parser Results' }
]

export default function DashboardTabs() {
  return (
    <nav
      className="flex w-fit rounded-md border border-slate-200 bg-white p-1 shadow-sm"
      aria-label="Dashboard sections"
    >
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            [
              'rounded px-3 py-1.5 text-sm font-semibold transition',
              isActive
                ? 'bg-libelle-indigo text-white'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950'
            ].join(' ')
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
