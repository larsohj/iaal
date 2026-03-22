const DAYS_SHORT = ['søn', 'man', 'tir', 'ons', 'tor', 'fre', 'lør'];
const DAYS_LONG = ['Søndag', 'Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag', 'Lørdag'];
const MONTHS_SHORT = ['jan', 'feb', 'mar', 'apr', 'mai', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'des'];
const MONTHS_LONG = [
  'januar', 'februar', 'mars', 'april', 'mai', 'juni',
  'juli', 'august', 'september', 'oktober', 'november', 'desember',
];

function pad(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}

export function formatCardDate(isoDate: string): string {
  const d = new Date(isoDate);
  const day = DAYS_SHORT[d.getDay()];
  const date = d.getDate();
  const month = MONTHS_SHORT[d.getMonth()];
  const hours = pad(d.getHours());
  const minutes = pad(d.getMinutes());
  return `${day}. ${date}. ${month}, kl. ${hours}:${minutes}`;
}

export function formatDetailDate(startAt: string, endAt?: string | null): string {
  const d = new Date(startAt);
  const dayName = DAYS_LONG[d.getDay()];
  const date = d.getDate();
  const month = MONTHS_LONG[d.getMonth()];
  const year = d.getFullYear();
  const startTime = `${pad(d.getHours())}:${pad(d.getMinutes())}`;

  let result = `${dayName} ${date}. ${month} ${year}, kl. ${startTime}`;

  if (endAt) {
    const e = new Date(endAt);
    const endTime = `${pad(e.getHours())}:${pad(e.getMinutes())}`;
    result += ` – ${endTime}`;
  }

  return result;
}

export function isToday(isoDate: string): boolean {
  const d = new Date(isoDate);
  const now = new Date();
  return d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear();
}

export function isTomorrow(isoDate: string): boolean {
  const d = new Date(isoDate);
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return d.getDate() === tomorrow.getDate() &&
    d.getMonth() === tomorrow.getMonth() &&
    d.getFullYear() === tomorrow.getFullYear();
}

export function formatRelativeDate(isoDate: string): string | null {
  if (isToday(isoDate)) return 'I dag';
  if (isTomorrow(isoDate)) return 'I morgen';
  return null;
}
