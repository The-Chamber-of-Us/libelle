import React from 'react';
import { IntakeForm } from './components/IntakeForm';
import { ShieldCheck } from 'lucide-react';

const App: React.FC = () => {
  return (
    <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8 bg-libelle-bg">
      <div className="max-w-3xl mx-auto">
        <header className="mb-10 text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-12 h-12 bg-libelle-indigo rounded-lg flex items-center justify-center text-white shadow-lg shadow-libelle-indigo/20">
              <ShieldCheck size={28} />
            </div>
          </div>
          <h1 className="text-3xl font-sans font-bold text-gray-900 tracking-tight sm:text-4xl">
            Join Libelle
          </h1>
          <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto font-medium">
            Volunteer matching for The Chamber of Us (TCUS)
          </p>
        </header>

        <main>
          <IntakeForm />
        </main>

        <footer className="mt-12 text-center text-sm text-gray-500">
          <p>&copy; {new Date().getFullYear()} The Chamber of Us. All rights reserved.</p>
        </footer>
      </div>
    </div>
  );
};

export default App;