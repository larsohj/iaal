import React from 'react';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { COLORS } from '../lib/constants';

interface Props {
  label: string;
  active?: boolean;
  onPress?: () => void;
  small?: boolean;
}

export function TagChip({ label, active = false, onPress, small = false }: Props) {
  return (
    <TouchableOpacity
      style={[
        styles.chip,
        small && styles.chipSmall,
        active ? styles.chipActive : styles.chipInactive,
      ]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <Text
        style={[
          styles.label,
          small && styles.labelSmall,
          active ? styles.labelActive : styles.labelInactive,
        ]}
      >
        {label}
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginRight: 8,
    marginBottom: 4,
  },
  chipSmall: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    marginRight: 4,
  },
  chipActive: {
    backgroundColor: COLORS.primary,
  },
  chipInactive: {
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  label: {
    fontSize: 13,
    fontWeight: '500',
  },
  labelSmall: {
    fontSize: 11,
  },
  labelActive: {
    color: COLORS.white,
  },
  labelInactive: {
    color: COLORS.textSecondary,
  },
});
