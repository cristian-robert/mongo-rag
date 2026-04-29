---
name: playwright-cli
description: Browser automation command reference for playwright-cli. Navigation, interaction, screenshots, forms, state management, debugging.
---

# Playwright CLI Reference

## Core Commands

### Navigation
```bash
npx playwright-cli open <url>              # Open URL
npx playwright-cli navigate <url>          # Navigate to URL
npx playwright-cli snapshot                # Get DOM snapshot with element refs
```

### Interaction
```bash
npx playwright-cli click <ref>             # Click element by ref from snapshot
npx playwright-cli fill <ref> <value>      # Fill input field
npx playwright-cli select <ref> <value>    # Select dropdown option
npx playwright-cli check <ref>             # Check checkbox
npx playwright-cli uncheck <ref>           # Uncheck checkbox
npx playwright-cli hover <ref>             # Hover over element
npx playwright-cli press <key>             # Press keyboard key
npx playwright-cli type <text>             # Type text (character by character)
```

### Screenshots and Recording
```bash
npx playwright-cli screenshot <path>       # Take screenshot
npx playwright-cli screenshot --full <path> # Full page screenshot
npx playwright-cli video start <path>      # Start recording
npx playwright-cli video stop              # Stop recording
```

### Waiting
```bash
npx playwright-cli wait <ref>              # Wait for element visible
npx playwright-cli wait-hidden <ref>       # Wait for element hidden
npx playwright-cli wait-navigation         # Wait for page navigation
```

### Dialog Handling
```bash
npx playwright-cli dialog accept           # Accept alert/confirm/prompt
npx playwright-cli dialog dismiss          # Dismiss dialog
npx playwright-cli dialog accept <text>    # Accept prompt with text
```

### Session and State
```bash
npx playwright-cli storage save <path>     # Save browser state (cookies, localStorage)
npx playwright-cli storage load <path>     # Load saved state
npx playwright-cli cookies get             # Get all cookies
npx playwright-cli cookies clear           # Clear cookies
```

### Network
```bash
npx playwright-cli network intercept <pattern> <response-file>  # Mock network request
npx playwright-cli network log             # Show network requests
```

### Viewport
```bash
npx playwright-cli viewport <width> <height>  # Set viewport size
```

## Common Patterns

### Login Flow
```bash
npx playwright-cli open http://localhost:3000/login
npx playwright-cli snapshot
npx playwright-cli fill ref:email "test@example.com"
npx playwright-cli fill ref:password "testpassword123"
npx playwright-cli click ref:submit
npx playwright-cli wait-navigation
npx playwright-cli snapshot  # Verify dashboard loaded
npx playwright-cli storage save auth-state.json  # Save for reuse
```

### Responsive Testing
```bash
# Desktop
npx playwright-cli viewport 1440 900
npx playwright-cli screenshot desktop.png

# Tablet
npx playwright-cli viewport 768 1024
npx playwright-cli screenshot tablet.png

# Mobile
npx playwright-cli viewport 375 812
npx playwright-cli screenshot mobile.png
```
