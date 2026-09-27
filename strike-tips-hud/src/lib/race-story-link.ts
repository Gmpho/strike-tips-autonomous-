/**
 * Race ⨯ story linking for the Live Ops panel.
 *
 * The backend already links news to racecards (`swarm_researcher.
 * _link_news_to_insights` → ChromaDB) but only emits a count in the
 * telemetry stream. This does the same matching client-side so the HUD can
 * show WHICH story belongs to WHICH live race, with a link to the article.
 *
 * Pure module — no React, no store, no network — so it is unit-testable
 * with the Node test runner (see tests/race-story-link.test.ts).
 */

export interface StorySource {
  id?: string;
  title: string;
  url?: string;
  source?: string;
  published?: string;
  summary?: string;
}

export interface RaceLike {
  id: string;
  course?: string;
  raceNumber?: string | number;
  t?: string;
  runners?: { name?: string }[];
}

export interface LinkedStory extends StorySource {
  /** Which term tied this story to the race (course name / horse). */
  matchedOn: string;
}

export interface RaceWithStories {
  id: string;
  course: string;
  raceNumber: string;
  offTime: string;
  runnerCount: number;
  stories: LinkedStory[];
}

export interface LinkOptions {
  /** Max races rendered (most-linked first). Default 12. */
  maxRaces?: number;
  /** Max stories per race. Default 3. */
  maxStoriesPerRace?: number;
  /** Shortest horse/course name that may match. Default 4 (kills "Ash"/"El"). */
  minTermLength?: number;
}

/** Lowercase, strip accents/punctuation, collapse spaces. */
function norm(value: string): string {
  return (value || "")
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Whole-word containment so "Turffontein" never matches "Turffontein2". */
function containsTerm(haystack: string, term: string): boolean {
  if (!term || term.length < 3) return false;
  return (` ${haystack} `).includes(` ${term} `);
}

export function linkStoriesToRaces(
  races: RaceLike[],
  stories: StorySource[],
  options: LinkOptions = {},
): RaceWithStories[] {
  const maxRaces = options.maxRaces ?? 12;
  const maxStories = options.maxStoriesPerRace ?? 3;
  const minLen = options.minTermLength ?? 4;

  const news = (stories || []).filter((s) => s && s.title);
  if (!Array.isArray(races) || races.length === 0 || news.length === 0) return [];

  // Pre-normalise every story once.
  const prepared = news.map((s) => ({ story: s, text: norm(s.title) }));

  const linked: RaceWithStories[] = [];
  for (const race of races) {
    if (!race) continue;
    const course = (race.course || '').trim();
    const courseTerm = norm(course);
    const runnerTerms = (race.runners || [])
      .map((r) => norm(r?.name || ''))
      .filter((n) => n.length >= minLen);

    const hits: LinkedStory[] = [];
    const seen = new Set<string>();
    for (const { story, text } of prepared) {
      let matchedOn = '';
      if (courseTerm && containsTerm(text, courseTerm)) {
        matchedOn = course;
      } else {
        const horse = runnerTerms.find((term) => containsTerm(text, term));
        if (horse) {
          matchedOn = race.runners?.find((r) => norm(r?.name || '') === horse)?.name || horse;
        }
      }
      if (!matchedOn) continue;
      const key = story.id || story.url || story.title;
      if (seen.has(key)) continue;
      seen.add(key);
      hits.push({ ...story, matchedOn });
      if (hits.length >= maxStories) break;
    }

    if (hits.length === 0) continue;
    linked.push({
      id: race.id,
      course: course || 'Unknown track',
      raceNumber: String(race.raceNumber ?? ''),
      offTime: race.t || '',
      runnerCount: race.runners?.length || 0,
      stories: hits,
    });
  }

  // Most-linked first (that's the newsworthy card), then by off time.
  linked.sort((a, b) => {
    if (b.stories.length !== a.stories.length) return b.stories.length - a.stories.length;
    return (a.offTime || '').localeCompare(b.offTime || '');
  });
  return linked.slice(0, maxRaces);
}
