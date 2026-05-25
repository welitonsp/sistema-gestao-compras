import React from 'react';

interface StatusMessageProps {
  message: string;
}

export const StatusMessage: React.FC<StatusMessageProps> = ({ message }) => {
  return (
    <div aria-live="polite" className="sr-only" role="status">
      {message}
    </div>
  );
};
