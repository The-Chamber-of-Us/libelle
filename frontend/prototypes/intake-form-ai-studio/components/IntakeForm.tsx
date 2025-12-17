import React, { useState } from 'react';
import { IntakeFormData, FormErrors, FormStatus } from '../types';
import { Input } from './ui/Input';
import { Textarea } from './ui/Textarea';
import { FileUpload } from './ui/FileUpload';
import { Check, ArrowRight, Loader2, AlertCircle, RotateCcw, ExternalLink } from 'lucide-react';

const INITIAL_FORM_DATA: IntakeFormData = {
  firstName: '',
  lastName: '',
  email: '',
  location: '',
  interests: '',
  availability: '',
  experienceLevel: '',
  linkedinUrl: '',
  githubUrl: '',
  motivation: '',
  resume: null,
  consentProfile: false,
  consentGuidelines: false,
  consentDataUse: false,
};

export const IntakeForm: React.FC = () => {
  const [formData, setFormData] = useState<IntakeFormData>(INITIAL_FORM_DATA);
  const [errors, setErrors] = useState<FormErrors>({});
  const [status, setStatus] = useState<FormStatus>({ state: 'idle' });

  // --- Validation Logic ---
  const validate = (): boolean => {
    const newErrors: FormErrors = {};
    let isValid = true;

    if (!formData.firstName.trim()) {
      newErrors.firstName = 'First name is required';
      isValid = false;
    }

    if (!formData.lastName.trim()) {
      newErrors.lastName = 'Last name is required';
      isValid = false;
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
      isValid = false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
      isValid = false;
    }

    if (!formData.location.trim()) {
      newErrors.location = 'Location is required';
      isValid = false;
    }

    if (!formData.interests.trim()) {
      newErrors.interests = 'Please list at least one interest';
      isValid = false;
    }

    if (!formData.availability.trim()) {
      newErrors.availability = 'Availability is required';
      isValid = false;
    }

    if (!formData.experienceLevel) {
      newErrors.experienceLevel = 'Please select an experience level';
      isValid = false;
    }

    // Optional URL validation
    if (formData.linkedinUrl && !/^https?:\/\/(www\.)?linkedin\.com\/.*$/.test(formData.linkedinUrl)) {
      newErrors.linkedinUrl = 'Invalid LinkedIn URL';
      isValid = false;
    }

    if (formData.githubUrl && !/^https?:\/\/(www\.)?github\.com\/.*$/.test(formData.githubUrl)) {
      newErrors.githubUrl = 'Invalid GitHub URL';
      isValid = false;
    }

    // Motivation Max Length (Strict 280 chars)
    if (formData.motivation.length > 280) {
      newErrors.motivation = 'Motivation must be 280 characters or less';
      isValid = false;
    }

    // Strict File Validation (PDF Only, 5MB)
    if (!formData.resume) {
      newErrors.resume = 'Please upload your resume (PDF only)';
      isValid = false;
    } else {
      if (formData.resume.type !== 'application/pdf') {
        newErrors.resume = 'Only PDF files are allowed';
        isValid = false;
      }
      if (formData.resume.size > 5 * 1024 * 1024) { // 5MB
        newErrors.resume = 'File size must be less than 5MB';
        isValid = false;
      }
    }

    // Consent Logic: Both must be checked to proceed
    if (!formData.consentProfile) {
      newErrors.consentProfile = 'This consent is required to proceed';
      isValid = false;
    }

    if (!formData.consentGuidelines) {
      newErrors.consentGuidelines = 'You must agree to the guidelines';
      isValid = false;
    }

    setErrors(newErrors);
    return isValid;
  };

  // --- Scroll Helper ---
  const scrollToError = () => {
    // Small timeout to allow DOM to update with error states
    setTimeout(() => {
      const firstError = document.querySelector('[aria-invalid="true"]');
      if (firstError) {
        firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }, 10);
  };

  // --- Submit Handler ---
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // 1. Client Validation
    if (!validate()) {
        scrollToError();
        return;
    }

    // 2. Set State: Submitting
    setStatus({ state: 'submitting' });
    setErrors({}); 

    // 3. Prepare Payload (Strict Mapping)
    const payload = new FormData();
    
    // Logic: Concatenate First + Last name for API 'full_name' key
    const fullName = `${formData.firstName} ${formData.lastName}`.trim();
    payload.append('full_name', fullName);

    payload.append('email', formData.email);
    payload.append('location', formData.location);
    payload.append('interests', formData.interests);
    payload.append('availability', formData.availability);
    payload.append('experience_level', formData.experienceLevel);
    
    // Logic: Consent is effectively true here because of client validation
    payload.append('consent', 'true');
    
    // File is guaranteed to exist and be valid here
    if (formData.resume) {
      payload.append('file', formData.resume);
    }
    
    // Optional fields
    if (formData.linkedinUrl) payload.append('linkedin_url', formData.linkedinUrl);
    if (formData.githubUrl) payload.append('github_url', formData.githubUrl);
    if (formData.motivation) payload.append('motivation', formData.motivation);

    try {
      const apiBase = (import.meta as any).env?.VITE_API_URL || '';
      const response = await fetch(`${apiBase}/api/upload`, {
        method: 'POST',
        body: payload,
      });

      // 4. Handle Response
      if (response.ok) {
        const data = await response.json();
        // Success State
        setStatus({ 
          state: 'success', 
          message: data.message || 'Application received',
          submissionId: data.submission_id 
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }

      // 5. Handle Errors
      const data = await response.json().catch(() => ({}));

      // 422 Validation Error
      if (response.status === 422 && data.fields) {
        const apiErrors: FormErrors = {};
        
        // Map snake_case API keys to camelCase state keys
        const fieldMap: Record<string, keyof IntakeFormData> = {
          full_name: 'firstName', // Map full_name error to firstName for visibility
          email: 'email',
          location: 'location',
          interests: 'interests',
          availability: 'availability',
          experience_level: 'experienceLevel',
          file: 'resume',
          linkedin_url: 'linkedinUrl',
          github_url: 'githubUrl',
          motivation: 'motivation',
          consent: 'consentProfile'
        };

        Object.keys(data.fields).forEach((apiKey) => {
          const stateKey = fieldMap[apiKey];
          if (stateKey) {
            apiErrors[stateKey] = data.fields[apiKey];
          }
        });

        setErrors(apiErrors);
        setStatus({ 
            state: 'error', 
            message: "Please fix the highlighted fields and try again." 
        });
        scrollToError();
        return;
      }

      // 400 File Missing (Specific API Error)
      if (response.status === 400 && data.code === 'FILE_REQUIRED') {
         setErrors({ resume: data.message || "A resume file is required." });
         setStatus({ state: 'error', message: "Please upload your resume to continue." });
         scrollToError();
         return;
      }

      // 500 or other errors
      throw new Error(data.message || 'We hit a snag while processing your submission. Please try again or reach out to support.');

    } catch (error: any) {
      // Network errors or generic 500s
      setStatus({ 
        state: 'error', 
        message: error.message || 'We hit a snag... please try again. If it keeps happening, email privacy@thechamberofus.org.' 
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleClear = () => {
    if (window.confirm("Are you sure you want to clear the form? All entered data will be lost.")) {
      setFormData(INITIAL_FORM_DATA);
      setErrors({});
      setStatus({ state: 'idle' });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleReset = () => {
    setFormData(INITIAL_FORM_DATA);
    setErrors({});
    setStatus({ state: 'idle' });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name as keyof IntakeFormData]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
  };

  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, checked } = e.target;
    setFormData(prev => ({ ...prev, [name]: checked }));
    if (errors[name as keyof IntakeFormData]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
  };

  const handleFileChange = (file: File | null) => {
    setFormData(prev => ({ ...prev, resume: file }));
    if (errors.resume) {
      setErrors(prev => ({ ...prev, resume: undefined }));
    }
  };

  const isSubmitting = status.state === 'submitting';

  // --- Success View ---
  if (status.state === 'success') {
    return (
      <div className="bg-white rounded-xl shadow-xl overflow-hidden animate-fade-in p-10 text-center border-t-4 border-libelle-emerald">
        <div className="w-20 h-20 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
          <Check className="w-10 h-10 text-libelle-emerald" />
        </div>
        <h2 className="text-3xl font-bold text-gray-900 font-sans mb-4">Application received</h2>
        <p className="text-gray-600 mb-8 max-w-lg mx-auto text-lg leading-relaxed">
          Thanks. We’ve received your profile and will review it for matching across TCUS projects.
        </p>
        
        {status.submissionId && (
            <p className="text-xs text-gray-400 mb-8 font-mono">ID: {status.submissionId}</p>
        )}

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
             <a
              href="https://libelle.io"
              className="inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-libelle-indigo hover:bg-indigo-700 transition-colors shadow-sm"
            >
              Back to Libelle
              <ExternalLink className="ml-2 w-4 h-4" />
            </a>
            <button
              onClick={handleReset}
              className="inline-flex items-center justify-center px-6 py-3 border border-gray-300 text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors"
            >
              Submit another
            </button>
        </div>
      </div>
    );
  }

  // --- Form View ---
  return (
    <div className="bg-white rounded-xl shadow-xl overflow-hidden border border-gray-100 relative">
      <div className="h-2 bg-libelle-indigo w-full"></div>
      
      {/* Form Card Header */}
      <div className="p-6 sm:p-10 border-b border-gray-100">
        <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 font-sans tracking-tight mb-3">
          We help you plug in fast.
        </h2>
        <p className="text-base sm:text-lg text-gray-600 mb-4 leading-relaxed">
          You found us for a reason. Create your volunteer profile, and we’ll match you to real needs across TCUS projects.
        </p>
        <p className="text-sm text-gray-500 italic">
          Most people finish in under 5 minutes.
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="p-6 sm:p-10 space-y-10" noValidate>
        
        {/* Global Error Banner */}
        {status.state === 'error' && status.message && (
             <div className="bg-red-50 border border-red-100 text-libelle-rose p-4 rounded-lg flex items-start animate-fade-in" role="alert">
                <AlertCircle className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5" />
                <p className="font-medium">{status.message}</p>
            </div>
        )}

        {/* Personal Information Section */}
        <section aria-labelledby="personal-info-heading">
          <h2 id="personal-info-heading" className="text-xl font-bold text-gray-900 font-sans mb-6 pb-2 border-b border-gray-100">
            Personal Information
          </h2>
          <div className="grid grid-cols-1 gap-y-6 gap-x-6 sm:grid-cols-2">
            <Input
              label="First Name"
              name="firstName"
              type="text"
              required
              placeholder="e.g. Jane"
              value={formData.firstName}
              onChange={handleInputChange}
              error={errors.firstName}
              autoComplete="given-name"
              disabled={isSubmitting}
            />
            <Input
              label="Last Name"
              name="lastName"
              type="text"
              required
              placeholder="e.g. Doe"
              value={formData.lastName}
              onChange={handleInputChange}
              error={errors.lastName}
              autoComplete="family-name"
              disabled={isSubmitting}
            />
            <div className="sm:col-span-2">
              <Input
                label="Email Address"
                name="email"
                type="email"
                required
                placeholder="jane@example.com"
                value={formData.email}
                onChange={handleInputChange}
                error={errors.email}
                autoComplete="email"
                disabled={isSubmitting}
              />
            </div>
            <div className="sm:col-span-2">
              <Input
                label="Current Location"
                name="location"
                type="text"
                required
                placeholder="City, State, or Country"
                value={formData.location}
                onChange={handleInputChange}
                error={errors.location}
                disabled={isSubmitting}
              />
            </div>
          </div>
        </section>

        {/* Experience & Motivation Section */}
        <section aria-labelledby="experience-heading">
           <h2 id="experience-heading" className="text-xl font-bold text-gray-900 font-sans mb-6 pb-2 border-b border-gray-100">
            Experience & Details
          </h2>
          <div className="grid grid-cols-1 gap-y-6 gap-x-6 sm:grid-cols-2 mb-6">
             <div className="sm:col-span-2">
              <Input
                label="Availability"
                name="availability"
                type="text"
                required
                placeholder="e.g. 5-10 hours/week, Weekends only"
                value={formData.availability}
                onChange={handleInputChange}
                error={errors.availability}
                disabled={isSubmitting}
              />
            </div>
            
            <div className="sm:col-span-2">
               <div className="w-full">
                <label htmlFor="experienceLevel" className="block text-sm font-medium text-gray-700 mb-1 font-sans">
                  Experience Level <span className="text-libelle-rose">*</span>
                </label>
                <div className="relative">
                  <select
                    id="experienceLevel"
                    name="experienceLevel"
                    required
                    value={formData.experienceLevel}
                    onChange={handleInputChange}
                    disabled={isSubmitting}
                    className={`
                      block w-full rounded-md border-gray-300 shadow-sm px-4 py-2.5 bg-white text-gray-900 ring-1 ring-inset ring-gray-300
                      focus:ring-2 focus:ring-inset focus:ring-libelle-indigo focus:border-libelle-indigo sm:text-sm sm:leading-6 transition-all
                      disabled:bg-gray-50 disabled:text-gray-500
                      ${errors.experienceLevel ? 'ring-libelle-rose focus:ring-libelle-rose border-libelle-rose' : ''}
                    `}
                    aria-invalid={!!errors.experienceLevel}
                    aria-describedby={errors.experienceLevel ? "experienceLevel-error" : undefined}
                  >
                    <option value="" disabled>Select your level</option>
                    <option value="Beginner">Beginner</option>
                    <option value="Mid">Mid</option>
                    <option value="Senior">Senior</option>
                  </select>
                   {errors.experienceLevel && (
                    <div className="pointer-events-none absolute inset-y-0 right-8 flex items-center">
                      <AlertCircle className="h-5 w-5 text-libelle-rose" aria-hidden="true" />
                    </div>
                  )}
                </div>
                {errors.experienceLevel && (
                  <p className="mt-1 text-sm text-libelle-rose" id="experienceLevel-error">
                    {errors.experienceLevel}
                  </p>
                )}
              </div>
            </div>

            <div className="sm:col-span-2">
              <Input
                label="Key Interests"
                name="interests"
                type="text"
                required
                placeholder="e.g. Coding, Design, Event Planning"
                value={formData.interests}
                onChange={handleInputChange}
                error={errors.interests}
                disabled={isSubmitting}
              />
            </div>

            <div className="sm:col-span-2">
              <Input
                label="LinkedIn URL (Optional)"
                name="linkedinUrl"
                type="url"
                placeholder="https://linkedin.com/in/..."
                value={formData.linkedinUrl}
                onChange={handleInputChange}
                error={errors.linkedinUrl}
                disabled={isSubmitting}
              />
            </div>

            <div className="sm:col-span-2">
              <Input
                label="GitHub URL (Optional)"
                name="githubUrl"
                type="url"
                placeholder="https://github.com/..."
                value={formData.githubUrl}
                onChange={handleInputChange}
                error={errors.githubUrl}
                disabled={isSubmitting}
              />
            </div>
          </div>

          <div className="space-y-6">
            <div className={isSubmitting ? "opacity-60 pointer-events-none" : ""}>
                <FileUpload
                label="Resume (PDF Only)"
                name="resume"
                accept=".pdf"
                required
                value={formData.resume}
                onChange={handleFileChange}
                error={errors.resume}
                description="PDF up to 5MB"
                />
            </div>

            <Textarea
              label="Why do you want to join TCUS? (Optional)"
              name="motivation"
              rows={4}
              maxLength={280}
              placeholder="Tell us about your interest in volunteering... (Max 280 chars)"
              value={formData.motivation}
              onChange={handleInputChange}
              error={errors.motivation}
              helperText={`${formData.motivation.length}/280 characters`}
              disabled={isSubmitting}
            />
          </div>
        </section>

        {/* Privacy & Consent Section */}
        <section aria-labelledby="privacy-heading" className="bg-gray-50 rounded-lg p-6 sm:p-8 border border-gray-200">
          <div className="flex flex-col space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h2 id="privacy-heading" className="text-lg font-bold text-gray-900 font-sans">
                Privacy and Consent
              </h2>
              <a href="#" className="text-sm font-medium text-libelle-indigo hover:text-indigo-800 underline">
                Privacy Policy
              </a>
            </div>

            <p className="text-sm text-gray-600 leading-relaxed">
              At The Chamber of Us (TCUS), we use the information you submit to create your volunteer profile and match you with opportunities aligned with your skills, interests, and availability. This can include processing details from your resume such as roles, education, and skills. We do not sell your information or use it for advertising.
            </p>

            <div className="space-y-4 pt-4">
              {/* Checkbox 1 */}
              <div className="flex items-start">
                <div className="flex items-center h-5">
                  <input
                    id="consentProfile"
                    name="consentProfile"
                    type="checkbox"
                    required
                    checked={formData.consentProfile}
                    onChange={handleCheckboxChange}
                    disabled={isSubmitting}
                    className="h-4 w-4 rounded border-gray-300 text-libelle-indigo focus:ring-libelle-indigo disabled:opacity-50"
                    aria-invalid={!!errors.consentProfile}
                    aria-describedby={errors.consentProfile ? "consentProfile-error" : undefined}
                  />
                </div>
                <div className="ml-3 text-sm">
                  <label htmlFor="consentProfile" className={`font-medium text-gray-700 ${isSubmitting ? 'opacity-60' : ''}`}>
                    I consent to TCUS using my information to create my volunteer profile and match me with opportunities. <span className="text-libelle-rose">*</span>
                  </label>
                  {errors.consentProfile && (
                    <p id="consentProfile-error" className="text-libelle-rose text-xs mt-1">{errors.consentProfile}</p>
                  )}
                </div>
              </div>

              {/* Checkbox 2 */}
              <div className="flex items-start">
                <div className="flex items-center h-5">
                  <input
                    id="consentGuidelines"
                    name="consentGuidelines"
                    type="checkbox"
                    required
                    checked={formData.consentGuidelines}
                    onChange={handleCheckboxChange}
                    disabled={isSubmitting}
                    className="h-4 w-4 rounded border-gray-300 text-libelle-indigo focus:ring-libelle-indigo disabled:opacity-50"
                    aria-invalid={!!errors.consentGuidelines}
                    aria-describedby={errors.consentGuidelines ? "consentGuidelines-error" : undefined}
                  />
                </div>
                <div className="ml-3 text-sm">
                  <label htmlFor="consentGuidelines" className={`font-medium text-gray-700 ${isSubmitting ? 'opacity-60' : ''}`}>
                    I agree to the <a href="#" className="text-libelle-indigo underline hover:text-indigo-800">Community Guidelines</a> and <a href="#" className="text-libelle-indigo underline hover:text-indigo-800">Code of Conduct</a>. <span className="text-libelle-rose">*</span>
                  </label>
                  {errors.consentGuidelines && (
                    <p id="consentGuidelines-error" className="text-libelle-rose text-xs mt-1">{errors.consentGuidelines}</p>
                  )}
                </div>
              </div>

              {/* Checkbox 3 */}
              <div className="flex items-start">
                <div className="flex items-center h-5">
                  <input
                    id="consentDataUse"
                    name="consentDataUse"
                    type="checkbox"
                    checked={formData.consentDataUse}
                    onChange={handleCheckboxChange}
                    disabled={isSubmitting}
                    className="h-4 w-4 rounded border-gray-300 text-libelle-indigo focus:ring-libelle-indigo disabled:opacity-50"
                  />
                </div>
                <div className="ml-3 text-sm">
                  <label htmlFor="consentDataUse" className={`text-gray-700 ${isSubmitting ? 'opacity-60' : ''}`}>
                    <span className="font-bold">Optional:</span> TCUS may use de-identified, aggregated data (with personal details removed) to improve Libelle’s matching and reporting.
                  </label>
                </div>
              </div>
            </div>

            <p className="text-xs text-gray-500 pt-2 border-t border-gray-200 mt-2">
              You can request deletion at any time at <a href="mailto:privacy@thechamberofus.org" className="text-gray-700 underline hover:text-gray-900">privacy@thechamberofus.org</a>.
            </p>
          </div>
        </section>

        {/* Submit Actions */}
        <div className="pt-4">
            <div className="flex flex-col gap-3">
                <div className="flex flex-col sm:flex-row gap-4">
                <button
                    type="submit"
                    disabled={isSubmitting}
                    className="flex-1 sm:flex-none flex justify-center items-center px-8 py-4 border border-transparent rounded-lg shadow-sm text-base font-semibold text-white bg-libelle-indigo hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-libelle-indigo disabled:opacity-70 disabled:cursor-not-allowed transition-all transform active:scale-[0.98]"
                >
                    {isSubmitting ? (
                    <>
                        <Loader2 className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" />
                        Submitting...
                    </>
                    ) : (
                    <>
                        Submit Application
                        <ArrowRight className="ml-2 -mr-1 h-5 w-5" />
                    </>
                    )}
                </button>

                <button
                    type="button"
                    onClick={handleClear}
                    disabled={isSubmitting}
                    className="flex-1 sm:flex-none flex justify-center items-center px-6 py-4 border border-transparent rounded-lg text-base font-medium text-gray-500 bg-transparent hover:bg-gray-50 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Clear Form
                </button>
                </div>
                
                {isSubmitting && (
                    <p className="text-sm text-gray-500 text-center sm:text-left animate-pulse">
                        Uploading resume and creating your volunteer profile...
                    </p>
                )}
            </div>
        </div>
      </form>
    </div>
  );
};