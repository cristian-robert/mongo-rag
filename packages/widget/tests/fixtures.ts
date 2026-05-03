import type { WidgetConfig } from "../src/types.js";

/**
 * Build a WidgetConfig with sensible defaults for tests. Test cases
 * only need to spread overrides for the fields they care about.
 *
 * Mirrors the defaults in `src/config.ts::buildConfig` — keep them in
 * sync (a future test could codify equality, but simple is fine for now).
 */
export function baseWidgetConfig(overrides: Partial<WidgetConfig> = {}): WidgetConfig {
  return {
    apiKey: "mrag_test_key_____________________________________",
    apiUrl: "https://api.example.test",
    botName: "Assistant",
    welcomeMessage: "Hi",
    showBranding: true,
    primaryColor: "#0f172a",
    position: "bottom-right",
    avatarUrl: null,
    colorMode: "light",
    background: null,
    surface: null,
    foreground: null,
    muted: null,
    border: null,
    primaryForeground: null,
    darkOverrides: null,
    fontFamily: "system",
    displayFont: null,
    baseFontSize: "md",
    radius: "md",
    density: "comfortable",
    launcherShape: "circle",
    launcherSize: "md",
    panelSize: "md",
    launcherIcon: "chat",
    launcherIconUrl: null,
    showAvatarInMessages: true,
    brandingText: null,
    ...overrides,
  };
}
