// Course -> racing region mapping for the dashboard region filter.
// Explicit course map first, then runner-region majority, then "other"
// (unknown courses are never hidden, only grouped). Ambiguous names
// (Belmont, Sandown) resolve via runner region when present.

export interface RegionInfo {
  code: string;
  label: string;
  flag: string;
}

export const REGIONS: Record<string, RegionInfo> = {
  SA: { code: 'SA', label: 'South Africa', flag: '🇿🇦' },
  UK_IE: { code: 'UK_IE', label: 'UK & Ireland', flag: '🇬🇧' },
  JP: { code: 'JP', label: 'Japan', flag: '🇯🇵' },
  HK: { code: 'HK', label: 'Hong Kong', flag: '🇭🇰' },
  AUS: { code: 'AUS', label: 'Australia', flag: '🇦🇺' },
  USA: { code: 'USA', label: 'USA', flag: '🇺🇸' },
  CAN: { code: 'CAN', label: 'Canada', flag: '🇨🇦' },
  FRA: { code: 'FRA', label: 'France', flag: '🇫🇷' },
  NZ: { code: 'NZ', label: 'New Zealand', flag: '🇳🇿' },
  UAE: { code: 'UAE', label: 'UAE', flag: '🇦🇪' },
  ARG: { code: 'ARG', label: 'Argentina', flag: '🇦🇷' },
  GER: { code: 'GER', label: 'Germany', flag: '🇩🇪' },
  OTHER: { code: 'OTHER', label: 'Other', flag: '🌍' },
};

function norm(s: string): string {
  return s.toLowerCase().replace(/[^a-z ]/g, ' ').replace(/\s+/g, ' ').trim();
}

// Explicit course -> region. Ambiguous dual-hemisphere names (Belmont,
// Sandown) are resolved by runner region first — see regionOf().
const COURSE_MAP: Record<string, string> = {
  // South Africa
  turffontein: 'SA', vaal: 'SA', fairview: 'SA', scottsville: 'SA',
  kenilworth: 'SA', durbanville: 'SA', greyville: 'SA', clairwood: 'SA',
  // UK
  redcar: 'UK_IE', uttoxeter: 'UK_IE', wolverhampton: 'UK_IE', yarmouth: 'UK_IE',
  bath: 'UK_IE', doncaster: 'UK_IE', musselburgh: 'UK_IE', kelso: 'UK_IE',
  beverley: 'UK_IE', lingfield: 'UK_IE', sandown: 'UK_IE',
  ascot: 'UK_IE', epsom: 'UK_IE', goodwood: 'UK_IE', newmarket: 'UK_IE',
  york: 'UK_IE', chester: 'UK_IE', haydock: 'UK_IE', aintree: 'UK_IE',
  cheltenham: 'UK_IE', kempton: 'UK_IE', newcastle: 'UK_IE', southwell: 'UK_IE',
  // Ireland
  punchestown: 'UK_IE', leopardstown: 'UK_IE', curragh: 'UK_IE', clonmel: 'UK_IE',
  fairyhouse: 'UK_IE', galway: 'UK_IE', naas: 'UK_IE', tipperary: 'UK_IE',
  // Japan (NAR + JRA)
  kanazawa: 'JP', mombetsu: 'JP', monbetsu: 'JP', nagoya: 'JP', ohi: 'JP',
  kochi: 'JP', mizusawa: 'JP', urawa: 'JP', funabashi: 'JP', kawasaki: 'JP',
  sonoda: 'JP', saga: 'JP', morioka: 'JP', himeji: 'JP', oi: 'JP',
  tokyo: 'JP', kyoto: 'JP', hanshin: 'JP', nakayama: 'JP', chukyo: 'JP',
  // Hong Kong
  'sha tin': 'HK', 'happy valley': 'HK', shatin: 'HK',
  // Australia
  balaklava: 'AUS', canterbury: 'AUS', caulfield: 'AUS', doomben: 'AUS',
  launceston: 'AUS', shepparton: 'AUS', young: 'AUS', 'globe derby': 'AUS',
  'gloucester park': 'AUS', flemington: 'AUS', randwick: 'AUS', rosehill: 'AUS',
  eaglefarm: 'AUS', 'moonee valley': 'AUS',
  // USA
  'fairmount park': 'USA', 'finger lakes': 'USA', 'horseshoe indianapolis': 'USA',
  'laurel park': 'USA', 'delaware park': 'USA', 'gulfstream park': 'USA',
  'churchill downs': 'USA', 'remington park': 'USA', 'los alamitos': 'USA',
  'louisiana downs': 'USA', 'mountaineer park': 'USA', philadelphia: 'USA',
  parx: 'USA', 'presque isle downs': 'USA', thistledown: 'USA',
  'monmouth park': 'USA', belmont: 'USA', keeneland: 'USA', saratoga: 'USA',
  aqueduct: 'USA', pimlico: 'USA', 'santa anita': 'USA', 'del mar': 'USA',
  // Canada
  woodbine: 'CAN', 'fort erie': 'CAN',
  // France
  auteuil: 'FRA', 'bordeaux le bouscat': 'FRA', compiegne: 'FRA',
  'lyon parilly': 'FRA', longchamp: 'FRA', chantilly: 'FRA', deauville: 'FRA',
  // New Zealand
  matamata: 'NZ', ellerslie: 'NZ', trentham: 'NZ', riccarton: 'NZ',
  wellington: 'NZ', 'te rapa': 'NZ',
  // UAE / Germany / Argentina
  meydan: 'UAE', 'jebel ali': 'UAE',
  'baden baden': 'GER', cologne: 'GER', munich: 'GER',
  palermo: 'ARG', 'san isidro': 'ARG',
};

// Ascot defaults to UK here; Ascot AUS resolves via runner-region vote
// (see AMBIGUOUS below).
COURSE_MAP['ascot'] = 'UK_IE';

const RUNNER_REGION_MAP: [RegExp, string][] = [
  [/south\s*africa|rsa\b/, 'SA'],
  [/united\s*kingdom|great\s*britain|\buk\b|england|scotland|wales/, 'UK_IE'],
  [/\bireland|irish/, 'UK_IE'],
  [/japan|japanese/, 'JP'],
  [/hong\s*kong/, 'HK'],
  [/australia|australian/, 'AUS'],
  [/united\s*states|\busa?\b|america/, 'USA'],
  [/canada|canadian/, 'CAN'],
  [/france|french/, 'FRA'],
  [/new\s*zealand/, 'NZ'],
  [/\buae\b|dubai|emirates/, 'UAE'],
  [/germany|german/, 'GER'],
  [/argentina/, 'ARG'],
];

function runnerRegion(regions: (string | undefined)[]): string | null {
  const votes = new Map<string, number>();
  for (const r of regions) {
    if (!r) continue;
    const low = r.toLowerCase();
    for (const [re, code] of RUNNER_REGION_MAP) {
      if (re.test(low)) {
        votes.set(code, (votes.get(code) || 0) + 1);
        break;
      }
    }
  }
  let best: string | null = null;
  let bestN = 0;
  for (const [code, n] of votes) {
    if (n > bestN) {
      bestN = n;
      best = code;
    }
  }
  return best;
}

// Dual-hemisphere names: explicit map is unreliable, runner vote decides.
const AMBIGUOUS = new Set(['belmont', 'sandown', 'ascot']);

/** Resolve an event's region. Never throws; unknown -> OTHER (never hidden). */
export function regionOf(course: string, runnerRegions: (string | undefined)[] = []): string {
  const c = norm(course);
  if (c && !AMBIGUOUS.has(c) && COURSE_MAP[c]) return COURSE_MAP[c];
  // Runner-region vote: disambiguates dual-hemisphere names and covers
  // courses missing from the map.
  const vote = runnerRegion(runnerRegions);
  if (vote) return vote;
  if (c && COURSE_MAP[c]) return COURSE_MAP[c];
  // Suffix hints surviving cleaning ("... (AUS)").
  const raw = course.toLowerCase();
  if (/\(aus\)/.test(raw)) return 'AUS';
  if (/\(rsa\)|\(saf\)/.test(raw)) return 'SA';
  if (/\(usa\)/.test(raw)) return 'USA';
  if (/\(gb\)|\(uk\)/.test(raw)) return 'UK_IE';
  if (/\(ire\)/.test(raw)) return 'UK_IE';
  if (/\(fr\)/.test(raw)) return 'FRA';
  if (/\(jpn\)/.test(raw)) return 'JP';
  return 'OTHER';
}
