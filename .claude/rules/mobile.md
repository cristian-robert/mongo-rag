---
description: Mobile development rules — auto-loads when editing mobile/native files
globs: ["**/mobile/**", "**/native/**", "**/*.native.*", "**/expo/**"]
---

# Mobile Rules

## Expo Skills (use the right one for the task)

| Task | Skill |
|------|-------|
| Building screens, components, navigation | `/expo-app-design:building-native-ui` |
| API calls, caching, offline support | `/expo-app-design:native-data-fetching` |
| Tailwind/NativeWind setup | `/expo-app-design:expo-tailwind-setup` |
| Dev client builds, TestFlight | `/expo-app-design:expo-dev-client` |
| API routes with EAS Hosting | `/expo-app-design:expo-api-routes` |
| Web code in native webview | `/expo-app-design:use-dom` |
| SwiftUI components | `/expo-app-design:expo-ui-swift-ui` |
| Jetpack Compose components | `/expo-app-design:expo-ui-jetpack-compose` |

## Skill Chain

1. **KB search** (if KB configured) — search for relevant screen/navigation/feature articles
2. **architect-agent RETRIEVE** — understand screen/navigation structure
3. **Expo skill** — appropriate skill from table above
4. **context7 MCP** — verify Expo/React Native API
5. **mobile-tester-agent VERIFY/FLOW** — verify on simulator after implementation
6. **KB update** (if KB configured) — update wiki articles for new/changed screens, navigation, hooks

## Conventions

- Follow Expo Router file-based routing
- Platform-specific extensions (`.ios.tsx`, `.android.tsx`) only when necessary
- Animations via `react-native-reanimated`
- Navigation state managed by Expo Router, not manually

## Checklist

- [ ] mobile-tester-agent VERIFY/FLOW run on simulator after UI changes
- [ ] Platform-specific files justified (no needless `.ios/.android` splits)
- [ ] Navigation state flows through Expo Router
- [ ] KB wiki articles updated for new/changed screens or hooks

## References

Load only when the rule triggers:

- `.claude/references/code-patterns.md` — load for project-specific mobile patterns
- `<kb-path>/wiki/_index.md` — search for existing screen/navigation articles before building
