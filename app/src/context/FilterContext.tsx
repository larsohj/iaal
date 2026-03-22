import React, { createContext, useContext, useState, useCallback } from 'react';

interface FilterState {
  selectedTags: string[];
  isFreeOnly: boolean;
  selectedSources: string[];
}

interface FilterContextType extends FilterState {
  toggleTag: (tag: string) => void;
  toggleSource: (source: string) => void;
  toggleFreeOnly: () => void;
  clearFilters: () => void;
  activeFilterCount: number;
}

const defaultState: FilterState = {
  selectedTags: [],
  isFreeOnly: false,
  selectedSources: [],
};

const FilterContext = createContext<FilterContextType | null>(null);

export function FilterProvider({ children }: { children: React.ReactNode }) {
  const [filters, setFilters] = useState<FilterState>(defaultState);

  const toggleTag = useCallback((tag: string) => {
    setFilters(prev => ({
      ...prev,
      selectedTags: prev.selectedTags.includes(tag)
        ? prev.selectedTags.filter(t => t !== tag)
        : [...prev.selectedTags, tag],
    }));
  }, []);

  const toggleSource = useCallback((source: string) => {
    setFilters(prev => ({
      ...prev,
      selectedSources: prev.selectedSources.includes(source)
        ? prev.selectedSources.filter(s => s !== source)
        : [...prev.selectedSources, source],
    }));
  }, []);

  const toggleFreeOnly = useCallback(() => {
    setFilters(prev => ({ ...prev, isFreeOnly: !prev.isFreeOnly }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters(defaultState);
  }, []);

  const activeFilterCount =
    filters.selectedTags.length +
    filters.selectedSources.length +
    (filters.isFreeOnly ? 1 : 0);

  return (
    <FilterContext.Provider
      value={{ ...filters, toggleTag, toggleSource, toggleFreeOnly, clearFilters, activeFilterCount }}
    >
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters(): FilterContextType {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error('useFilters must be used within FilterProvider');
  return ctx;
}
