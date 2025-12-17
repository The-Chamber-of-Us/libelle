import React from 'react';
import { AlertCircle } from 'lucide-react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const Input: React.FC<InputProps> = ({ label, error, id, className = '', ...props }) => {
  const inputId = id || props.name;
  
  return (
    <div className="w-full">
      <label htmlFor={inputId} className="block text-sm font-medium text-gray-700 mb-1 font-sans">
        {label} {props.required && <span className="text-libelle-rose">*</span>}
      </label>
      <div className="relative">
        <input
          id={inputId}
          className={`
            block w-full rounded-md border-gray-300 shadow-sm px-4 py-2.5 bg-white text-gray-900 ring-1 ring-inset ring-gray-300
            focus:ring-2 focus:ring-inset focus:ring-libelle-indigo focus:border-libelle-indigo sm:text-sm sm:leading-6 transition-all
            ${error ? 'ring-libelle-rose focus:ring-libelle-rose border-libelle-rose pr-10' : ''}
            ${className}
          `}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : undefined}
          {...props}
        />
        {error && (
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
            <AlertCircle className="h-5 w-5 text-libelle-rose" aria-hidden="true" />
          </div>
        )}
      </div>
      {error && (
        <p className="mt-1 text-sm text-libelle-rose" id={`${inputId}-error`}>
          {error}
        </p>
      )}
    </div>
  );
};