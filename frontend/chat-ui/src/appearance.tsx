import {
  createContext,
  Dispatch,
  ReactNode,
  SetStateAction,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type AppearancePreferences = {
  theme: "system" | "dark" | "light";
  contrast: "default" | "high";
  font: "system" | "dm-sans" | "mono";
  fontSize: 12 | 14 | 16 | 18;
  density: "comfortable" | "compact";
  reduceMotion: boolean;
};

export const DEFAULT_APPEARANCE: AppearancePreferences = {
  theme: "dark",
  contrast: "default",
  font: "dm-sans",
  fontSize: 14,
  density: "comfortable",
  reduceMotion: false,
};

export const APPEARANCE_STORAGE_KEY = "coding-appearance";

function readAppearancePreferences(): AppearancePreferences {
  const saved = localStorage.getItem(APPEARANCE_STORAGE_KEY);
  if (!saved) return DEFAULT_APPEARANCE;

  try {
    const parsed: unknown = JSON.parse(saved);
    if (!parsed || typeof parsed !== "object") return DEFAULT_APPEARANCE;
    const value = parsed as Record<string, unknown>;
    return {
      theme: value.theme === "system" || value.theme === "light"
        ? value.theme
        : DEFAULT_APPEARANCE.theme,
      contrast: value.contrast === "high" ? "high" : DEFAULT_APPEARANCE.contrast,
      font: value.font === "system" || value.font === "mono"
        ? value.font
        : DEFAULT_APPEARANCE.font,
      fontSize: value.fontSize === 12 || value.fontSize === 16 || value.fontSize === 18
        ? value.fontSize
        : DEFAULT_APPEARANCE.fontSize,
      density: value.density === "compact" ? "compact" : DEFAULT_APPEARANCE.density,
      reduceMotion: value.reduceMotion === true,
    };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

type AppearanceContextValue = {
  appearance: AppearancePreferences;
  setAppearance: Dispatch<SetStateAction<AppearancePreferences>>;
  effectiveTheme: "dark" | "light";
};

const AppearanceContext = createContext<AppearanceContextValue | null>(null);

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearance] = useState(readAppearancePreferences);
  const [systemTheme, setSystemTheme] = useState<"dark" | "light">(
    () => window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
  );
  const effectiveTheme = appearance.theme === "system"
    ? systemTheme
    : appearance.theme;

  useEffect(() => {
    localStorage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(appearance));
  }, [appearance]);

  useEffect(() => {
    const preference = window.matchMedia("(prefers-color-scheme: dark)");
    const updateSystemTheme = (event: MediaQueryListEvent) => {
      setSystemTheme(event.matches ? "dark" : "light");
    };
    const updateStoredAppearance = () => {
      setAppearance(readAppearancePreferences());
    };
    preference.addEventListener("change", updateSystemTheme);
    window.addEventListener("storage", updateStoredAppearance);
    setSystemTheme(preference.matches ? "dark" : "light");
    return () => {
      preference.removeEventListener("change", updateSystemTheme);
      window.removeEventListener("storage", updateStoredAppearance);
    };
  }, []);

  const value = useMemo(
    () => ({ appearance, setAppearance, effectiveTheme }),
    [appearance, effectiveTheme],
  );
  return (
    <AppearanceContext.Provider value={value}>
      {children}
    </AppearanceContext.Provider>
  );
}

export function useAppearance() {
  const context = useContext(AppearanceContext);
  if (!context) {
    throw new Error("useAppearance must be used within AppearanceProvider.");
  }
  return context;
}
