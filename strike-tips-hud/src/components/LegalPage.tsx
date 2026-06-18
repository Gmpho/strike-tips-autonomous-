import React from 'react';
import useSWR from 'swr';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import { ArrowLeft, FileText } from 'lucide-react';

const fetcher = (url: string) => fetch(url).then(res => res.text());

interface LegalPageProps {
  docId: 'privacy' | 'terms' | 'disclaimer' | 'how-to-bet' | 'faq' | 'betting-rules' | 'responsible';
  title: string;
}

export const LegalPage: React.FC<LegalPageProps> = ({ docId, title }) => {
  const { data, error, isLoading } = useSWR(`/api/legal/${docId}`, fetcher);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-12 h-12 border-4 border-purple-500/20 border-t-purple-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 text-center">
        <FileText className="w-12 h-12 text-theme-secondary mx-auto mb-4 opacity-50" />
        <p className="text-theme-secondary font-medium">Failed to load {title}</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="px-4 md:px-8 lg:px-12 py-4 md:py-8 flex-1 overflow-y-auto"
      >
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center gap-3 mb-6">
            <button
              onClick={() => window.history.back()}
              className="p-2 rounded-lg bg-theme-secondary hover:bg-purple-500/10 text-theme-secondary hover:text-purple-500 transition-all border border-theme"
            >
              <ArrowLeft size={20} />
            </button>
            <h1 className="text-xl md:text-2xl font-black text-theme-primary tracking-tight">{title}</h1>
          </div>

          <div className="prose prose-invert max-w-none text-theme-secondary leading-relaxed">
            <ReactMarkdown>{data}</ReactMarkdown>
          </div>
        </div>
      </motion.div>
    </div>
  );
};