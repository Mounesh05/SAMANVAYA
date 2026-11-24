import { useEffect, useState } from 'react';
import { useAuthStore } from '../../store/useAuthStore';

// Private notes stay in memory only. Account changes remove all unsaved drafts.
const drafts = new Map();
useAuthStore.subscribe((next, previous) => {
  if (!next.isAuthenticated || next.user?.employee_id !== previous.user?.employee_id ||
      next.user?.org_id !== previous.user?.org_id) drafts.clear();
});

export function useScoringDraft(key, initial) {
  const [value, setValue] = useState(() => drafts.get(key) || initial);
  const [dirty, setDirty] = useState(() => drafts.has(key));
  useEffect(() => {
    if (!dirty) return;
    const unload = (event) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', unload);
    return () => window.removeEventListener('beforeunload', unload);
  }, [dirty]);
  return { value, dirty, change(next) { drafts.set(key, next); setValue(next); setDirty(true); },
    clear(next = initial) { drafts.delete(key); setValue(next); setDirty(false); },
    clearIfUnchanged(version) {
      if (drafts.get(key) !== version) return false;
      drafts.delete(key); setValue(initial); setDirty(false); return true;
    } };
}
