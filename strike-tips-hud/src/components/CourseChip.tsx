import React from 'react';
import { MapPin } from 'lucide-react';
import { getFullCourseName } from '../lib/course-names';

// One-line track intel distilled from the OKF track shelves
// (knowledge/racing/tracks/*.md + tracks-uk/*.md). Surface + the bias that matters.
export const TRACK_INTEL: Record<string, string> = {
  // SA
  Greyville: 'No straight · handy types · poly kickback watch on hot days',
  'Greyville Poly': 'No straight · handy types · poly kickback watch on hot days',
  Kenilworth: 'Straight: inside · wind flips it outside · winter specialists',
  'Kenilworth Winter': 'Straight: inside · wind flips it outside · winter specialists',
  Durbanville: 'Low draws · read the false rail · course specialists repeat',
  Fairview: 'Turf straight: HIGH draws (downhill) · poly: low · slow draining',
  'Fairview Poly': 'Low draws to 1600m · forward types · 400m run-in',
  'Fairview Turf': 'Straight: HIGH draws downhill · slow draining after rain',
  Turffontein: 'Most testing track · stamina · wet = high draws up the straight',
  'Turffontein Inside': 'All round the turn · draw barely matters',
  'Vaal Classic': 'Low draws 1200/1450m · angled stalls above 1400m',
  'Vaal Turf': 'Low draws slightly · winter splits into two groups',
  Vaal: '1600m straight stamina test · handy types dominate',
  Scottsville: 'Straight: inside (fading bias) · hot pace collapses late',
  'Scottsville Inside': 'Straight: inside (fading bias) · hot pace collapses late',
  // UK / Ireland (ATR feed)
  Newcastle: 'Straight sprints: HIGH draws · uphill mile tests stamina',
  Southwell: 'Straight 5f: low lean (8–10 runners) · stamina circuit',
  Nottingham: 'Sharp sprints: low + handy · fair beyond a mile',
  Salisbury: 'Undulating straight · balance over stall number',
  Bellewstown: '5f: HIGH (dogleg) · uphill finish · balance exam',
  Clonmel: 'Stamina + climb · wide draws suffer 9–11f',
};

const REGION_FLAG: Record<string, string> = {
  SA: '🇿🇦', UK: '🇬🇧', Ireland: '🇮🇪 ',
};

export function regionForCourse(course: string): string {
  const c = (course || '').toLowerCase();
  if (!c) return '';
  if (/(greyville|scottsville|turffontein|vaal|kenilworth|durbanville|fairview|flamingo|kimberley)/.test(c)) return 'SA';
  return '';
}

export const CourseChip: React.FC<{ course?: string; region?: string; time?: string; intel?: boolean }> = ({
  course, region, time, intel = true,
}) => {
  if (!course) return null;
  const flag = REGION_FLAG[region || ''] || (regionForCourse(course) === 'SA' ? '🇿🇦' : '');
  const tip = intel ? TRACK_INTEL[course] : undefined;
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5" title={tip}>
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-sky-500/10 border border-sky-500/25 text-sky-300 text-[10px] font-black uppercase tracking-wider">
        <MapPin className="w-2.5 h-2.5" />
        {flag && <span>{flag}</span>}
        {getFullCourseName(course)}
        {time ? <span className="text-sky-400/70">· {time}</span> : null}
      </span>
    </span>
  );
};
