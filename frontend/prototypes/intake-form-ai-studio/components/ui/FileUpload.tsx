import React, { useRef, useState } from 'react';
import { Upload, FileText, X, AlertCircle } from 'lucide-react';

interface FileUploadProps {
  label: string;
  name: string;
  accept?: string;
  required?: boolean;
  error?: string;
  onChange: (file: File | null) => void;
  value: File | null;
  description?: string;
}

export const FileUpload: React.FC<FileUploadProps> = ({ 
  label, 
  name, 
  accept, 
  required, 
  error, 
  onChange,
  value,
  description = "PDF up to 5MB"
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    onChange(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0] || null;
    onChange(file);
  };

  const clearFile = () => {
    onChange(null);
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  return (
    <div className="w-full">
      <label className="block text-sm font-medium text-gray-700 mb-1 font-sans">
        {label} {required && <span className="text-libelle-rose">*</span>}
      </label>
      
      {!value ? (
        <div
          className={`
            relative block w-full rounded-lg border-2 border-dashed p-8 text-center hover:bg-indigo-50 transition-colors
            ${isDragOver ? 'border-libelle-indigo bg-indigo-50 ring-2 ring-libelle-indigo ring-opacity-50' : 'border-gray-300'}
            ${error ? 'border-libelle-rose bg-red-50' : ''}
          `}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <input
            type="file"
            name={name}
            id={name}
            ref={inputRef}
            accept={accept}
            onChange={handleFileChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            aria-label={label}
            aria-invalid={!!error}
            aria-describedby={error ? `${name}-error` : undefined}
          />
          <Upload className={`mx-auto h-10 w-10 ${error ? 'text-libelle-rose' : 'text-gray-400'}`} />
          <div className="mt-4 flex text-sm leading-6 text-gray-600 justify-center">
            <span className="font-semibold text-libelle-indigo hover:text-indigo-500">
              Upload a file
            </span>
            <span className="pl-1">or drag and drop</span>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {description}
          </p>
        </div>
      ) : (
        <div className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg shadow-sm ring-1 ring-gray-200">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="flex-shrink-0 w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-libelle-indigo" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-gray-900 truncate">
                {value.name}
              </p>
              <p className="text-xs text-gray-500">
                {(value.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={clearFile}
            className="flex-shrink-0 p-1 ml-4 text-gray-400 hover:text-gray-500 hover:bg-gray-100 rounded-full transition-colors"
            aria-label="Remove file"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {error && (
        <p className="mt-1 text-sm text-libelle-rose flex items-center gap-1" id={`${name}-error`}>
          <AlertCircle className="w-4 h-4" />
          {error}
        </p>
      )}
    </div>
  );
};