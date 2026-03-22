import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://vidabmirmqssepksaisc.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_QWd7-tHQ-TRx73eNFpsDLg_amnCnk5-';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
