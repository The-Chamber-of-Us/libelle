import React, { useRef } from 'react'

type Props = {
  label: string
  name: string
  accept?: string
  required?: boolean
  value: File | null
  onChange: (file: File | null) => void
  error?: string
  description?: string
}

export function FileUpload({
  label,
  name,
  accept,
  required,
  value,
  onChange,
  error,
  description
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const hasError = Boolean(error)

  return (
    <div className="w-full">
      <label className="block text-sm font-medium text-gray-700 mb-1 font-sans">
        {label} {required ? <span className="text-libelle-rose">*</span> : null}
      </label>

      <div
        className={[
          'flex items-center justify-between gap-4 rounded-md border px-4 py-3 bg-white',
          hasError ? 'border-libelle-rose' : 'border-gray-200'
        ].join(' ')}
      >
        <div className="min-w-0">
          <div className="text-sm text-gray-900 truncate">
            {value ? value.name : 'No file selected'}
          </div>
          {description ? <div className="text-xs text-gray-400">{description}</div> : null}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="px-3 py-2 rounded-md bg-libelle-indigo text-white text-sm font-medium hover:opacity-90 transition"
          >
            Choose file
          </button>
          {value ? (
            <button
              type="button"
              onClick={() => {
                if (inputRef.current) inputRef.current.value = ''
                onChange(null)
              }}
              className="px-3 py-2 rounded-md border border-gray-300 bg-white text-sm font-medium hover:bg-gray-50 transition"
            >
              Remove
            </button>
          ) : null}
        </div>
      </div>

      <input
        ref={inputRef}
        id={name}
        name={name}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        aria-invalid={hasError}
      />

      {hasError ? <p className="mt-1 text-sm text-libelle-rose">{error}</p> : null}
    </div>
  )
}