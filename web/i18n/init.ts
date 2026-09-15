import i18n from "i18next";
import { initReactI18next } from "react-i18next";

export type AppLanguage = "en" | "zh";

export function normalizeLanguage(lang: unknown): AppLanguage {
  if (!lang) return "en";
  const s = String(lang).toLowerCase();
  if (s === "zh" || s === "cn" || s === "chinese") return "zh";
  return "en";
}

let _initialized = false;
const loadedLanguages = new Set<AppLanguage>();
const pendingLanguageLoads = new Map<AppLanguage, Promise<void>>();

const languageLoaders: Record<AppLanguage, () => Promise<Record<string, string>>> = {
  en: async () => (await import("@/locales/en/app.json")).default,
  zh: async () => (await import("@/locales/zh/app.json")).default,
};

export function initI18n(language?: unknown) {
  if (_initialized) return i18n;

  i18n.use(initReactI18next).init({
    resources: {},
    lng: normalizeLanguage(language),
    fallbackLng: "en",
    // Use a single default namespace to keep lookups simple.
    // We intentionally keep keySeparator disabled so keys like "Generating..." remain valid.
    defaultNS: "app",
    ns: ["app"],
    keySeparator: false,
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: false,
    },
    returnEmptyString: false,
    returnNull: false,
  });

  _initialized = true;
  return i18n;
}

export async function ensureLanguage(language: AppLanguage) {
  const normalized = normalizeLanguage(language);
  if (loadedLanguages.has(normalized) && i18n.hasResourceBundle(normalized, "app")) {
    return;
  }

  const existingLoad = pendingLanguageLoads.get(normalized);
  if (existingLoad) {
    await existingLoad;
    return;
  }

  const load = languageLoaders[normalized]().then((appMessages) => {
    i18n.addResourceBundle(normalized, "app", appMessages, true, true);
    loadedLanguages.add(normalized);
  }).finally(() => {
    pendingLanguageLoads.delete(normalized);
  });
  pendingLanguageLoads.set(normalized, load);
  await load;
}
