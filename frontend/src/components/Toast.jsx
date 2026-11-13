import { Terminal } from 'lucide-react';

export function Toast({ toast }) {
  return toast ? (
    <div className={'toast ' + toast.kind}>
      <Terminal size={15} />
      {toast.text}
    </div>
  ) : null;
}
