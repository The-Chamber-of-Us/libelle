import React from 'react';
import { AlertCircle } from 'lucide-react';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
  helperText?: string;
}

export const Textarea: React.FC<TextareaProps> = ({ label, error, helperText, id, className = '', ...props }) => {
  const inputId = id || props.name;

  return (
    <div className="w-full">
      <label htmlFor={inputId} className="block text-sm font-medium text-gray-700 mb-1 font-sans">
        {label} {props.required && <span className="text-libelle-rose">*</span>}
      </label>
      <div className="relative">
        <textarea
          id={inputId}
          className={`
            block w-full rounded-md border-gray-300 shadow-sm px-4 py-3 bg-white text-gray-900 ring-1 ring-inset ring-gray-300
            focus:ring-2 focus:ring-inset focus:ring-libelle-indigo focus:border-libelle-indigo sm:text-sm sm:leading-6 transition-all
            min-h-[120px]
            ${error ? 'ring-libelle-rose focus:ring-libelle-rose border-libelle-rose' : ''}
            ${className}
          `}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : helperText ? `${inputId}-desc` : undefined}
          {...props}
        />
        {error && (
          <div className="absolute top-3 right-3 pointer-events-none">
            <AlertCircle className="h-5 w-5 text-libelle-rose" aria-hidden="true" />
          </div>
        )}
      </div>
      {error ? (
        <p className="mt-1 text-sm text-libelle-rose" id={`${inputId}-error`}>
          {error}
        </p>
      ) : helperText ? (
        <p className="mt-1 text-sm text-gray-500" id={`${inputId}-desc`}>
          {helperText}
        </p>
      ) : null}
    </div>
  );
};