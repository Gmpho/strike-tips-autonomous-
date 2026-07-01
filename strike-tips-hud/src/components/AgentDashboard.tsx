import React from 'react';
import { AIChat } from './AIChat';
import { motion } from 'framer-motion';

export const AgentDashboard: React.FC = () => {
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col space-y-4 h-[calc(100vh-120px)] md:h-[calc(100vh-150px)] min-h-[550px]"
    >
      <div className="flex-1 h-full min-h-0">
        <AIChat />
      </div>
    </motion.div>
  );
};
