import React, { useRef, useCallback } from 'react';
import { View, FlatList, ActivityIndicator, RefreshControl, StyleSheet } from 'react-native';
import BottomSheet from '@gorhom/bottom-sheet';
import { useEvents } from '../src/hooks/useEvents';
import { useFilters } from '../src/context/FilterContext';
import { EventCard } from '../src/components/EventCard';
import { FilterBar } from '../src/components/FilterBar';
import { FilterSheet } from '../src/components/FilterSheet';
import { EmptyState } from '../src/components/EmptyState';
import { COLORS } from '../src/lib/constants';
import type { Event } from '../src/lib/types';

export default function HomeScreen() {
  const filters = useFilters();
  const { events, loading, error, loadMore, hasMore, refresh } = useEvents({
    selectedTags: filters.selectedTags,
    isFreeOnly: filters.isFreeOnly,
    selectedSources: filters.selectedSources,
  });

  const bottomSheetRef = useRef<BottomSheet>(null);

  const openFilters = useCallback(() => {
    bottomSheetRef.current?.snapToIndex(0);
  }, []);

  const renderItem = useCallback(({ item }: { item: Event }) => (
    <EventCard event={item} />
  ), []);

  const keyExtractor = useCallback((item: Event) => item.id, []);

  const renderFooter = useCallback(() => {
    if (!hasMore || !loading) return null;
    return (
      <View style={styles.footer}>
        <ActivityIndicator size="small" color={COLORS.primary} />
      </View>
    );
  }, [hasMore, loading]);

  return (
    <View style={styles.container}>
      <FilterBar onOpenFilters={openFilters} />
      <FlatList
        data={events}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        contentContainerStyle={styles.list}
        onEndReached={loadMore}
        onEndReachedThreshold={0.5}
        ListFooterComponent={renderFooter}
        ListEmptyComponent={loading ? null : <EmptyState />}
        refreshControl={
          <RefreshControl refreshing={loading && events.length === 0} onRefresh={refresh} />
        }
      />
      <FilterSheet ref={bottomSheetRef} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.surface,
  },
  list: {
    paddingTop: 8,
    paddingBottom: 20,
  },
  footer: {
    paddingVertical: 20,
    alignItems: 'center',
  },
});
