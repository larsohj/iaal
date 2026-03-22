import React from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useEvent } from '../../src/hooks/useEvent';
import { EventImage } from '../../src/components/EventImage';
import { TagChip } from '../../src/components/TagChip';
import { COLORS, SOURCE_COLORS } from '../../src/lib/constants';
import { formatDetailDate } from '../../src/lib/date';

export default function EventDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { event, loading, error } = useEvent(id);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={COLORS.primary} />
      </View>
    );
  }

  if (error || !event) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Kunne ikke laste arrangementet</Text>
      </View>
    );
  }

  const dateText = event.start_at ? formatDetailDate(event.start_at, event.end_at) : null;
  const sourceColor = SOURCE_COLORS[event.source] ?? COLORS.primary;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <EventImage
        imageUrl={event.image_url}
        title={event.title}
        source={event.source}
        fullWidth
        height={250}
      />

      <View style={styles.sourceBadge} />

      <View style={styles.body}>
        <Text style={styles.title}>{event.title}</Text>

        {dateText && (
          <View style={styles.infoRow}>
            <Text style={styles.infoIcon}>📅</Text>
            <Text style={styles.infoText}>{dateText}</Text>
          </View>
        )}

        {event.location_name && (
          <View style={styles.infoRow}>
            <Text style={styles.infoIcon}>📍</Text>
            <View>
              <Text style={styles.infoText}>{event.location_name}</Text>
              {event.address && <Text style={styles.infoSubtext}>{event.address}</Text>}
            </View>
          </View>
        )}

        <View style={styles.infoRow}>
          <Text style={styles.infoIcon}>💰</Text>
          <Text style={styles.infoText}>
            {event.is_free ? 'Gratis' : event.price_text ?? 'Se arrangementside'}
          </Text>
        </View>

        {event.organizer && (
          <View style={styles.infoRow}>
            <Text style={styles.infoIcon}>🎭</Text>
            <Text style={styles.infoText}>{event.organizer}</Text>
          </View>
        )}

        {event.tags && event.tags.length > 0 && (
          <View style={styles.tags}>
            {event.tags.map(tag => (
              <TagChip key={tag} label={tag} small />
            ))}
          </View>
        )}

        {event.description && (
          <Text style={styles.description}>{event.description}</Text>
        )}

        <View style={styles.sourceRow}>
          <View style={[styles.sourceDot, { backgroundColor: sourceColor }]} />
          <Text style={styles.sourceText}>Kilde: {event.source}</Text>
        </View>

        {event.url && (
          <TouchableOpacity
            style={styles.button}
            onPress={() => WebBrowser.openBrowserAsync(event.url!)}
            activeOpacity={0.8}
          >
            <Text style={styles.buttonText}>
              {event.is_free ? 'Mer info' : 'Kjøp billetter'}
            </Text>
          </TouchableOpacity>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.white,
  },
  content: {
    paddingBottom: 40,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  errorText: {
    fontSize: 16,
    color: COLORS.textSecondary,
  },
  sourceBadge: {
    position: 'absolute',
    top: 16,
    right: 16,
  },
  body: {
    padding: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 16,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  infoIcon: {
    fontSize: 16,
    marginRight: 10,
    marginTop: 1,
  },
  infoText: {
    fontSize: 15,
    color: COLORS.text,
  },
  infoSubtext: {
    fontSize: 13,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  tags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 4,
    marginBottom: 16,
  },
  description: {
    fontSize: 15,
    lineHeight: 22,
    color: COLORS.text,
    marginTop: 8,
    marginBottom: 16,
  },
  sourceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 24,
  },
  sourceDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  sourceText: {
    fontSize: 13,
    color: COLORS.textTertiary,
  },
  button: {
    backgroundColor: COLORS.primary,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  buttonText: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: '600',
  },
});
