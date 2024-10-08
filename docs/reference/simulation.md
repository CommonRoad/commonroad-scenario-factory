# Simulation

The Scenario Factory currently supports two simulators: SUMO and OpenTrafficSim (OTS).

## Supported Simulation Modes

In the table below, you can see which [`SimulationMode`](../api/simulation/#scenario_factory.simulation.SimulationMode) is supported by which simulator.

| Mode        | SUMO | OTS |
| ----------- | ------------------------------------ | ------ |
| `SimulationMode.RANDOM_TRAFFIC_GENERATION`          | :material-check: | :material-check: |
| `SimulationMode.DEMAND_TRAFFIC_GENERATION`       | :material-close: | :material-check: |
| `SimulationMode.INFRASTRUCTURE_TRAFFIC_GENERATION`    | :material-close: | :material-check: |
| `SimulationMode.DELAY_RESIMULATION`    | :material-close: | :material-check: |
| `SimulationMode.RESIMULATION`    | :material-close: | :material-check: |

## Which Simulator Should I Use?

Currently, the only simulation mode that both simulators support is `SimulationMode.RANDOM_TRAFFIC_GENERATION`. In this mode, SUMO often executes faster than OTS. Quality differences have not yet been assessed.

For all other simulation modes, you must obviously use OTS, because they are not supported by SUMO.
