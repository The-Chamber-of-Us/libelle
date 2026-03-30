import React from 'react'

type Props = {
  label: string
  name: string
  type?: string
  required?: boolean
  placeholder?: string
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  error?: string
  autoComplete?: string
  disabled?: boolean
}

export function Input({
  label,
  name,
  type = 'text',
  required,
  placeholder,
  value,
  onChange,
  error,
  autoComplete,
  disabled
}: Props) {
  const hasError = Boolean(error)

  return (
    <div className="w-full">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700 mb-1 font-sans">
        {label} {required ? <span className="text-libelle-rose">*</span> : null}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        required={required}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
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
      {hasError ? (
        <p className="mt-1 text-sm text-libelle-rose" id={`${name}-error`}>
          {error}
        </p>
      ) : null}
    </div>
  )
}