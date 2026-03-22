import React, { forwardRef, useCallback, useMemo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import BottomSheet, { BottomSheetScrollView } from '@gorhom/bottom-sheet';
import { COLORS, TAGS, SOURCES } from '../lib/constants';
import { useFilters } from '../context/FilterContext';
import { TagChip } from './TagChip';

export const FilterSheet = forwardRef<BottomSheet>(function FilterSheet(_, ref) {
  const {
    selectedTags, isFreeOnly, selectedSources,
    toggleTag, toggleSource, toggleFreeOnly, clearFilters, activeFilterCount,
  } = useFilters();

  const snapPoints = useMemo(() => ['55%', '85%'], []);

  return (
    <BottomSheet
      ref={ref}
      index={-1}
      snapPoints={snapPoints}
      enablePanDownToClose
      backgroundStyle={styles.background}
      handleIndicatorStyle={styles.indicator}
    >
      <BottomSheetScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Filter</Text>
          {activeFilterCount > 0 && (
            <TouchableOpacity onPress={clearFilters}>
              <Text style={styles.resetText}>Nullstill</Text>
            </TouchableOpacity>
          )}
        </View>

        <Text style={styles.sectionTitle}>Kategori</Text>
        <View style={styles.chipGrid}>
          {TAGS.map(tag => (
            <TagChip
              key={tag.key}
              label={tag.label}
              active={selectedTags.includes(tag.key)}
              onPress={() => toggleTag(tag.key)}
            />
          ))}
        </View>

        <Text style={styles.sectionTitle}>Pris</Text>
        <View style={styles.chipGrid}>
          <TagChip
            label="Kun gratis"
            active={isFreeOnly}
            onPress={toggleFreeOnly}
          />
        </View>

        <Text style={styles.sectionTitle}>Kilde</Text>
        <View style={styles.chipGrid}>
          {SOURCES.map(source => (
            <TagChip
              key={source.key}
              label={source.label}
              active={selectedSources.includes(source.key)}
              onPress={() => toggleSource(source.key)}
            />
          ))}
        </View>
      </BottomSheetScrollView>
    </BottomSheet>
  );
});

const styles = StyleSheet.create({
  background: {
    backgroundColor: COLORS.white,
    borderRadius: 20,
  },
  indicator: {
    backgroundColor: COLORS.textTertiary,
    width: 40,
  },
  content: {
    padding: 20,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.text,
  },
  resetText: {
    fontSize: 14,
    color: COLORS.primary,
    fontWeight: '500',
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.text,
    marginTop: 16,
    marginBottom: 10,
  },
  chipGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
});
