import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import type { Event } from '../lib/types';

export function useEvent(id: string) {
  const [event, setEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetch() {
      try {
        setLoading(true);
        const { data, error: err } = await supabase
          .from('events')
          .select('*')
          .eq('id', id)
          .single();

        if (err) throw new Error(err.message);
        setEvent(data);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Ukjent feil');
      } finally {
        setLoading(false);
      }
    }

    if (id) fetch();
  }, [id]);

  return { event, loading, error };
}
