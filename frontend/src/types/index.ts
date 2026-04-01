export interface IntakeFormData {
    firstName: string
    lastName: string
    email: string
    location: string
    interests: string
    availability: string
    experienceLevel: string
    linkedinUrl: string
    githubUrl: string
    motivation: string
    resume: File | null
    consentProfile: boolean
    consentGuidelines: boolean
    consentDataUse: boolean
  }
  
  export type FormErrors = Partial<Record<keyof IntakeFormData, string>>
  
  export type FormStatus =
    | { state: 'idle' }
    | { state: 'submitting' }
    | { state: 'success'; message?: string; submissionId?: string }
    | { state: 'error'; message?: string }