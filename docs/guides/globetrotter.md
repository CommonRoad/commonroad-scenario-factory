# Globetrotter: Extract Intersections from a Map as Individual CommonRoad Scenarios

!!! abstract
    The basis for the Scenario Generation process is `globetrotter`, which processes openstreetmaps and extracts intersections as individual CommonRoad scenarios. A simple CLI is provided to use globetrotter.

# Usage

```sh
$ poetry run globetrotter -o /tmp/intersections --radius 0.1 --coords 48.264682/11.671399
```

This will download the map at the provided coordinates, convert it to CommonRoad, identify all intersections and create a new CommonRoad scenario for each intersection.

The same limitations as for the [scenario generation](./generate_scenarios) apply also for globetrotter.

More information about the usage, can be found in the [CLI reference](../../reference/cli/#globetrotter).
