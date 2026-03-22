import React, { memo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { COLORS } from '../lib/constants';
import { formatCardDate, formatRelativeDate } from '../lib/date';
import { EventImage } from './EventImage';
import { TagChip } from './TagChip';
import type { Event } from '../lib/types';

interface Props {
  event: Event;
}

export const EventCard = memo(function EventCard({ event }: Props) {
  const router = useRouter();

  const dateText = event.start_at ? formatCardDate(event.start_at) : '';
  const relativeDate = event.start_at ? formatRelativeDate(event.start_at) : null;

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => router.push(`/event/${event.id}`)}
      activeOpacity={0.7}
    >
      <EventImage
        imageUrl={event.image_url}
        title={event.title}
        source={event.source}
        size={80}
      />
      <View style={styles.content}>
        <View style={styles.dateRow}>
          {relativeDate && <Text style={styles.relativeDate}>{relativeDate}</Text>}
          <Text style={styles.date}>{dateText}</Text>
        </View>
        <Text style={styles.title} numberOfLines={2}>
          {event.title}
        </Text>
        {event.location_name && (
          <Text style={styles.venue} numberOfLines={1}>
            📍 {event.location_name}
          </Text>
        )}
        <View style={styles.footer}>
          {event.is_free && (
            <View style={styles.freeBadge}>
              <Text style={styles.freeText}>Gratis</Text>
            </View>
          )}
          {event.tags?.slice(0, 2).map(tag => (
            <TagChip key={tag} label={tag} small />
          ))}
        </View>
      </View>
    </TouchableOpacity>
  );
});

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    padding: 12,
    marginHorizontal: 16,
    marginVertical: 4,
    backgroundColor: COLORS.white,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  content: {
    flex: 1,
    marginLeft: 12,
    justifyContent: 'center',
  },
  dateRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  relativeDate: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.primary,
  },
  date: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  title: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.text,
    marginTop: 2,
  },
  venue: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    gap: 4,
  },
  freeBadge: {
    backgroundColor: COLORS.freeLight,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    marginRight: 4,
  },
  freeText: {
    fontSize: 11,
    fontWeight: '600',
    color: COLORS.free,
  },
});
