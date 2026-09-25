import bankByTheme from "./data/questions.json";
import type { FeatureFlags, Question, ThemeInfo } from "./types";

type ThemeBlock = { theme: string; level: string; usage: string; tags: string[]; sensitive: boolean; questions: string[] };

/**
 * Banque de 400 questions embarquée dans l'application (annexe A du cahier des
 * charges bêta). Les identifiants sont ceux du serveur (q001…q400) : le parcours
 * guidé fonctionne donc hors connexion, et la liste du serveur (questions
 * désactivées par l'administrateur, thèmes sensibles) la remplace dès qu'elle
 * est disponible.
 */
export const BUNDLED_QUESTIONS: Question[] = (() => {
  let number = 0;
  return (bankByTheme as ThemeBlock[]).flatMap((block) => block.questions.map((text) => {
    number += 1;
    return { id: `q${String(number).padStart(3, "0")}`, number, theme: block.theme, text, level: block.level, usage: block.usage, tags: block.tags, sensitive: block.sensitive, active: true };
  }));
})();

export const THEME_ORDER = (bankByTheme as ThemeBlock[]).map((block) => block.theme);
const SENSITIVE_THEMES = new Set((bankByTheme as ThemeBlock[]).filter((block) => block.sensitive).map((block) => block.theme));

/** Questions proposables : actives, et sans thème sensible tant qu'il n'est pas activé. */
export function availableQuestions(questions: Question[], features: FeatureFlags): Question[] {
  return questions.filter((question) => question.active !== false && (features.sensitive_themes || !question.sensitive));
}

export function themeCards(questions: Question[], features: FeatureFlags): ThemeInfo[] {
  const available = availableQuestions(questions, features);
  return THEME_ORDER.map((theme) => {
    const count = available.filter((question) => question.theme === theme).length;
    const sensitive = SENSITIVE_THEMES.has(theme);
    return { theme, sensitive, active_count: count, total: 20, enabled: count > 0 };
  });
}

/**
 * Choisit une question : d'abord celles jamais posées à la personne, sans
 * reproposer la question affichée. `theme` absent = « Question surprise ».
 */
export function pickQuestion(questions: Question[], answered: string[], theme: string | null, currentId: string | null): Question | null {
  const pool = questions.filter((question) => (!theme || question.theme === theme) && question.id !== currentId);
  if (!pool.length) return questions.find((question) => question.id === currentId) ?? null;
  const fresh = pool.filter((question) => !answered.includes(question.id));
  const candidates = fresh.length ? fresh : pool;
  return candidates[Math.floor(Math.random() * candidates.length)];
}
