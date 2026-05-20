export function SectionHeader({
  title,
  description,
  status,
  statusTone
}: {
  title: string
  description: string
  status: string
  statusTone: 'neutral' | 'success' | 'warning'
}) {
  return (
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-libelle-indigo">
          {title}
        </h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
      </div>
      <span
        className={[
          'inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em]',
          statusTone === 'success'
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
            : statusTone === 'warning'
              ? 'border-amber-200 bg-amber-50 text-amber-700'
              : 'border-slate-200 bg-slate-50 text-slate-600'
        ].join(' ')}
      >
        {status}
      </span>
    </div>
  )
}

export function StateCallout({
  tone,
  children
}: {
  tone: 'neutral' | 'warning'
  children: string
}) {
  return (
    <p
      className={[
        'rounded-md border px-3 py-2 text-sm leading-5',
        tone === 'warning'
          ? 'border-amber-200 bg-amber-50 text-amber-800'
          : 'border-slate-200 bg-slate-50 text-slate-600'
      ].join(' ')}
    >
      {children}
    </p>
  )
}

export function DetailField({
  label,
  value,
  multiline = false
}: {
  label: string
  value: string
  multiline?: boolean
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </dt>
      <dd
        className={[
          'mt-1 break-words text-slate-900',
          multiline ? 'whitespace-pre-wrap' : ''
        ].join(' ')}
      >
        {value.trim() || 'Not provided'}
      </dd>
    </div>
  )
}

export function ListDetailField({
  label,
  values,
  emptyLabel,
  tone = 'neutral'
}: {
  label: string
  values: string[]
  emptyLabel: string
  tone?: 'neutral' | 'warning'
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </dt>
      <dd className="mt-2">
        {values.length > 0 ? (
          <ul className="flex flex-wrap gap-2">
            {values.map((value, index) => (
              <li
                key={`${label}-${value}-${index}`}
                className={[
                  'max-w-full break-words rounded-md border px-2.5 py-1 text-sm',
                  tone === 'warning'
                    ? 'border-amber-200 bg-amber-50 text-amber-800'
                    : 'border-slate-200 bg-slate-50 text-slate-800'
                ].join(' ')}
              >
                {value}
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-sm text-slate-500">{emptyLabel}</span>
        )}
      </dd>
    </div>
  )
}

export function LinkDetailField({ label, value }: { label: string; value: string }) {
  const href = value.trim()

  if (!href) {
    return <DetailField label={label} value="" />
  }

  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 break-words">
        <a
          className="text-libelle-indigo underline decoration-libelle-indigo/30 underline-offset-2 hover:decoration-libelle-indigo"
          href={href}
          rel="noreferrer"
          target="_blank"
        >
          {href}
        </a>
      </dd>
    </div>
  )
}
