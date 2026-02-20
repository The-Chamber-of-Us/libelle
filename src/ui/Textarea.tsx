import React from 'react'

type Props = {
  label: string
  name: string
  rows?: number
  maxLength?: number
  placeholder?: string
  value: string
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
  error?: string
  helperText?: string
  disabled?: boolean
}

export function Textarea({
  label,
  name,
  rows = 4,
  maxLength,
  placeholder,
  value,
  onChange,
  error,
  helperText,
  disabled
}: Props) {
  const hasError = Boolean(error)

  return (
    <div className="w-full">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700 mb-1 font-sans">
        {label}
      </label>
      <textarea
        id={name}
        name={name}
        rows={rows}
        maxLength={maxLength}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        disabled={disabled}
        className={[
          'block w-full rounded-md px-4 py-2.5 bg-white text-gray-900',
          'ring-1 ring-inset ring-gray-300 shadow-sm',
          'focus:ring-2 focus:ring-inset focus:ring-libelle-indigo focus:border-libelle-indigo',
          'transition disabled:bg-gray-50 disabled:text-gray-500',
          hasError ? 'ring-libelle-rose focus:ring-libelle-rose' : ''
        ].join(' ')}
        aria-invalid={hasError}
        aria-describedby={hasError ? `${name}-error` : undefined}
      />
      <div className="mt-1 flex items-center justify-between">
        {hasError ? (
          <p className="text-sm text-libelle-rose" id={`${name}-error`}>
            {error}
          </p>
        ) : (
          <span />
        )}
        {helperText ? <p className="text-xs text-gray-400">{helperText}</p> : null}
      </div>
    </div>
  )
}