import React, { useState } from 'react';
import { Image, View, Text, StyleSheet } from 'react-native';
import { SOURCE_COLORS, COLORS } from '../lib/constants';

interface Props {
  imageUrl: string | null;
  title: string;
  source: string;
  size?: number;
  fullWidth?: boolean;
  height?: number;
}

export function EventImage({ imageUrl, title, source, size = 80, fullWidth = false, height }: Props) {
  const [failed, setFailed] = useState(false);
  const bgColor = SOURCE_COLORS[source] ?? COLORS.primary;
  const letter = title.charAt(0).toUpperCase();

  if (!imageUrl || failed) {
    return (
      <View
        style={[
          styles.placeholder,
          fullWidth
            ? { width: '100%', height: height ?? 250 }
            : { width: size, height: size, borderRadius: 8 },
          { backgroundColor: bgColor },
        ]}
      >
        <Text style={[styles.letter, fullWidth ? { fontSize: 48 } : { fontSize: size * 0.4 }]}>
          {letter}
        </Text>
      </View>
    );
  }

  return (
    <Image
      source={{ uri: imageUrl }}
      style={
        fullWidth
          ? { width: '100%', height: height ?? 250 }
          : { width: size, height: size, borderRadius: 8 }
      }
      resizeMode="cover"
      onError={() => setFailed(true)}
    />
  );
}

const styles = StyleSheet.create({
  placeholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  letter: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
});
