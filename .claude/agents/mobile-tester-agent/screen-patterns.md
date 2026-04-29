# Screen Patterns

Screen inventory and navigation patterns for the mobile-tester-agent.
Populated by /create-rules and updated by /evolve.

## Configuration

- **App URL:** exp://localhost:8081
- **Dev command:** `npx expo start`
- **Platform:** iOS Simulator

## Navigation Structure

> Populated when /create-rules scans the mobile app's routing.

### Tab Bar
| Tab | Screen | Icon Position (approx) |
|-----|--------|----------------------|
| Home | HomeScreen | Bottom-left |
| Search | SearchScreen | Bottom-center-left |
| Profile | ProfileScreen | Bottom-right |

### Stack Screens
| Parent | Screen | Trigger |
|--------|--------|---------|
| Home | DetailScreen | Tap list item |

## Screen Inventory

> Populated when /create-rules scans the mobile app's screens.

| Screen | Auth Required | Key Elements |
|--------|--------------|-------------|
| HomeScreen | No | Header, list, tab bar |
| LoginScreen | No | Email field, password field, submit |
| ProfileScreen | Yes | Avatar, name, settings list |

## Common Patterns

- **Pull to refresh:** Swipe down from top of list
- **Infinite scroll:** Swipe up at bottom of list
- **Modal dismiss:** Swipe down from modal header or tap X
