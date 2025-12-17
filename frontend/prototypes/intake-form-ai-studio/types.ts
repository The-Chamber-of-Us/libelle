export interface IntakeFormData {
  firstName: string;
  lastName: string;
  email: string;
  location: string;
  interests: string;
  availability: string;
  experienceLevel: string;
  linkedinUrl: string;
  githubUrl: string;
  motivation: string;
  resume: File | null;
  consentProfile: boolean;
  consentGuidelines: boolean;
  consentDataUse: boolean;
}

export type FormErrors = Partial<Record<keyof IntakeFormData, string>>;

export interface FormStatus {
  state: 'idle' | 'submitting' | 'success' | 'error';
  message?: string;
  submissionId?: string;
}