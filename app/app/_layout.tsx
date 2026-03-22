import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { FilterProvider } from '../src/context/FilterContext';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <FilterProvider>
        <StatusBar style="dark" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: '#FFFFFF' },
            headerTintColor: '#111827',
            headerShadowVisible: false,
          }}
        >
          <Stack.Screen
            name="index"
            options={{ title: 'Kultur i Ålesund' }}
          />
          <Stack.Screen
            name="event/[id]"
            options={{ title: '', headerBackTitle: 'Tilbake' }}
          />
        </Stack>
      </FilterProvider>
    </GestureHandlerRootView>
  );
}
