# Review Workspace v0.8

GeoScaleX v0.8 reorganizes Dataset Lab around the work researchers actually perform: choose a
dataset, inspect or compare features, review contextual scenes, and manage the data that feeds those
tasks. The milestone also makes geometry comparison behave like a spatial tool rather than a static
illustration.

## Why this milestone exists

The v0.7 interface exposed each capability as it was added. That kept implementation incremental,
but produced five peer navigation items for actions at different levels: comparison, scene review,
generation, import, and versioning. It also made the swipe divider look draggable while requiring a
separate slider below the canvas, and relied on small `A` and `B` labels more than visual identity.

The v0.8 design gives those capabilities an explicit hierarchy:

- **Datasets** is the entry point and exposes every workspace, rather than only the first workspace.
- **Workbench** is the feature-level comparison surface.
- **Review queue** contains contextual scenes and opens a selected scene in the workbench.
- **Data** groups import, synthetic generation, and immutable dataset versions behind local tabs.

Feature selection remains in the left rail because it is useful across the workbench. Bounded flows
use tabs; the application does not introduce a stepper for ordinary navigation.

## Comparison interaction

The comparison canvas has one direct-manipulation model:

- In swipe mode, the divider itself is draggable and keyboard accessible. There is no second slider.
- Candidate A is consistently orange and candidate B consistently blue. Their color swatches,
  method names, and achieved vertex counts live together outside the drawing area.
- The original geometry remains a neutral dashed reference, described in the legend.
- Wheel or buttons zoom the viewport, dragging the canvas pans it, and reset restores the fitted
  extent. View transforms never modify source or candidate coordinates.
- Overlay mode uses the same identity and viewport controls without displaying a divider.

The divider clips in screen space while all geometry layers share one viewport transform. This makes
the before/after boundary stable while a reviewer zooms or pans.

## Inspector hierarchy

The right inspector is divided into three local tabs:

- **Setup** selects methods, defines the matched budget, and builds candidates.
- **Metrics** compares source and achieved geometry measurements.
- **History** manages immutable revisions and feature actions.

This keeps the primary workbench focused while preserving all v0.7 functionality.

## Storage and deployment boundary

v0.8 remains local-first. The sidebar displays local SQLite as status, not as a dead navigation
control. Nothing in this UI contract prevents a hosted storage adapter later, but storage selection
will only become interactive when the backend actually offers more than one implementation.

## Acceptance criteria

1. Every workspace and dataset returned by the API can be discovered and selected.
2. Workbench, review queue, and data management have distinct, understandable destinations.
3. The swipe divider responds to pointer drag, arrow keys, Home, and End.
4. Geometry can be zoomed, panned, and reset in both comparison modes.
5. Candidate identity remains clear without labels drawn over the geometry.
6. Import, generation, versioning, editing, duplication, archiving, and review remain reachable.
7. Type checks, unit tests, production build, and browser smoke tests pass.

## Deferred work

- Persisting view state in URL routes.
- Resizable application sidebars and saved per-user layout preferences.
- A dedicated experiment registry and model promotion UI.
- Cloud storage configuration.
- Linked zoom across multiple independent canvases.
