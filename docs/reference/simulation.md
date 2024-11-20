# Simulation

The Scenario Factory currently supports two simulators: SUMO and OpenTrafficSim (OTS). Each of the simulators has different

## Simulation Mode Overview

In the table below, you can see which [`SimulationMode`](../api/simulation/#scenario_factory.simulation.SimulationMode) is supported by which simulator.

| Mode        | SUMO | OTS | Description |
| ----------- | ---- | --- | ------- |
| `SimulationMode.RANDOM_TRAFFIC_GENERATION` | :material-check: | :material-check: | Vehicles are generated randomly on the street network of the scenario. |
| `SimulationMode.DEMAND_TRAFFIC_GENERATION` | :material-check: | :material-check: | Vehicles are generated randomly according to demand information that was extracted from the original scenario. |
| `SimulationMode.INFRASTRUCTURE_TRAFFIC_GENERATION` | :material-check: | :material-check: | Vehicles are generated randomly according to demand information that was extracted from the original scenario. The demand information is adjusted to account for the infrastructure capacities. |
| `SimulationMode.RESIMULATION` | :material-check: | :material-check: | Vehicle trajectories are injected into the simulation as close as possible. Insertion is forced, although it might not be safe. |
| `SimulationMode.DELAY` | :material-check: | :material-check: | Vehicles trajectories are injected into the simulation as close as possible, but insertion checks are enabled. |

All simulation modes except `SimulationMode.RANDOM_TRAFFIC_GENERATION` require the input scenarios to contain dynamic obstacles.
