# DRISHTI Phase 2 — Working Intelligence Prototype

## Goal
Turn the approved Phase 1 interface into a deterministic, synchronized intelligence prototype without changing its visual identity.

## Implementation
- Establish one typed demo-data engine for watches, snapshots, posts, accounts, relationships, demographics, events, and trend scores.
- Add a shared analysis provider holding the active watch, selected timestamp, selected narrative, selected account, selected evidence item, and playback state.
- Drive sentiment, narratives, network, evidence, demographics, and the current-moment summary from selectors over the same watch and timestamp.
- Upgrade the Time-Machine controls for click, drag, previous, next, play, pause, reset, and event-marker jumps.
- Add account and post detail panels, with KOL-to-evidence and trend-to-evidence filtering.
- Make watch creation and switching work locally in Demo Mode, then route Dashboard, Alerts, History, and watch rows into precise analysis states.
- Preserve the existing typography, colors, navigation, spacing, routes, and institutional composition.

## Verification
- Exercise every acceptance item end-to-end, including the required Sep 08 story, at laptop and desktop sizes.
- Confirm that changing one timeline position updates every analytical view with no console errors or overflow.
