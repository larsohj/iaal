import { useState, useEffect, useCallback } from 'react';
import { supabase } from '../lib/supabase';
import { PAGE_SIZE } from '../lib/constants';
import type { Event } from '../lib/types';

interface UseEventsOptions {
  selectedTags: string[];
  isFreeOnly: boolean;
  selectedSources: string[];
}

export function useEvents(options: UseEventsOptions) {
  const [allEvents, setAllEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const fetchEvents = useCallback(async (pageNum: number, replace: boolean) => {
    try {
      if (replace) setLoading(true);

      const from = pageNum * PAGE_SIZE;
      const to = from + PAGE_SIZE - 1;

      const { data, error: err } = await supabase
        .from('events')
        .select('*')
        .gte('start_at', new Date().toISOString())
        .order('start_at', { ascending: true })
        .range(from, to);

      if (err) throw new Error(err.message);

      const events = data ?? [];
      setHasMore(events.length === PAGE_SIZE);

      if (replace) {
        setAllEvents(events);
      } else {
        setAllEvents(prev => [...prev, ...events]);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ukjent feil');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setPage(0);
    fetchEvents(0, true);
  }, [fetchEvents]);

  const loadMore = useCallback(() => {
    if (!hasMore || loading) return;
    const nextPage = page + 1;
    setPage(nextPage);
    fetchEvents(nextPage, false);
  }, [page, hasMore, loading, fetchEvents]);

  const refresh = useCallback(() => {
    setPage(0);
    fetchEvents(0, true);
  }, [fetchEvents]);

  // Client-side filtrering
  const filteredEvents = allEvents.filter(event => {
    if (options.isFreeOnly && !event.is_free) return false;

    if (options.selectedSources.length > 0 && !options.selectedSources.includes(event.source)) {
      return false;
    }

    if (options.selectedTags.length > 0) {
      const eventTags = event.tags ?? [];
      if (!options.selectedTags.some(tag => eventTags.includes(tag))) return false;
    }

    return true;
  });

  return { events: filteredEvents, loading, error, loadMore, hasMore, refresh };
}
