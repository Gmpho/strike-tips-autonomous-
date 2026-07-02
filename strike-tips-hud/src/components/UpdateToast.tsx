import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw, Download } from 'lucide-react';

interface Props {
  visible: boolean;
  onUpdate: () => void;
}

export const UpdateToast: React.FC<Props> = ({ visible, onUpdate }) => {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: -20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          className="fixed top-4 right-4 z-[60] max-w-sm"
        >
          <div className="bg-zinc-900/95 backdrop-blur-xl border border-purple-500/30 rounded-2xl p-4 shadow-2xl shadow-purple-500/10">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-xl bg-purple-500/15 border border-purple-500/20 flex items-center justify-center shrink-0 mt-0.5">
                <Download className="w-4 h-4 text-purple-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-black text-purple-200 uppercase tracking-wider">
                  Update Available
                </p>
                <p className="text-[11px] text-slate-400 font-medium mt-0.5">
                  A new version has been downloaded. Tap to refresh and apply.
                </p>
              </div>
              <button
                onClick={onUpdate}
                className="shrink-0 flex items-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white px-3.5 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all active:scale-95 mt-0.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Refresh
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
