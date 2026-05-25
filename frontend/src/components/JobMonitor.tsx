import React from 'react';
import { Bell, CheckCircle2, XCircle, Clock } from 'lucide-react';

export interface JobStatus {
  job_id: string;
  status: string;
  success: boolean | null;
  file?: string;
}

interface JobMonitorProps {
  jobs: JobStatus[];
}

export const JobMonitor: React.FC<JobMonitorProps> = ({ jobs }) => {
  return (
    <div className="bg-white p-6 rounded-xl border shadow-sm">
      <h3 className="text-[10px] font-black mb-4 text-blue-600 uppercase flex items-center gap-2">
        <Bell size={14} /> LIVE MONITOR
      </h3>
      <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
        {jobs.length === 0 && <p className="text-xs text-slate-400 italic text-center py-4">Nenhuma atividade recente.</p>}
        {jobs.map((job, i) => (
          <div key={i} className="flex flex-col gap-1 p-2 bg-slate-50 rounded border border-slate-100">
            <div className="flex justify-between items-center">
              <span className="text-slate-600 font-mono text-[10px]">{job.file || job.job_id.slice(0, 8)}</span>
              {job.status === 'completed' ? (
                <CheckCircle2 size={14} className="text-green-500" />
              ) : job.status === 'failed' ? (
                <XCircle size={14} className="text-red-500" />
              ) : (
                <Clock size={14} className="text-amber-500 animate-pulse" />
              )}
            </div>
            <p className={`text-[10px] font-bold ${job.status === 'completed' ? 'text-green-600' : 'text-slate-500'}`}>
              {job.status === 'completed' ? 'Processado' : job.status === 'failed' ? 'Falhou' : 'Ingerindo...'}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};
