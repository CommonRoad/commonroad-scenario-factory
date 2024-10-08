# Ego Vehicle Selection

The ego vehicle selection process is used to determine which dynamic obstacles perform maneuvers that are interesting and should be used to create a new scenario. This process is split into two top-level steps:

* Ego Vehicle Selection based on criterions: Determine if an 'interesting' maneuver is detected based on a set of pre-defined criterions. The dynamic obstacles performing such a maneuver are canidates for new ego vehicles.
* Ego Vehicle Maneuver Filter: Filters the set of possible ego vehicles maneuvers to determine which of those maneuvers are suitable (e.g. to the maneuvers last long enough?) and interesting (e.g. are other vehicles around the ego vehicle?).

Criterions are applied as 'or' conditions. This means that each criterion will be matched independently of each other and one dynamic obstacle can be matched multiple times by different criterions (but one criterion can only match one dynamic obstacle once!)
Filters are applied as 'and' conditions. This means that only if a maneuver matches all filters, a scenario will be derived from it.

## Ego Vehicle Selection Criterions

An ego vehicle selection criterion is used to determine if a dynamic obstacle in a scenario performs an interesting maneuver.

### Pre-Defined criterions

The scenario factory includes some pre-defined criterions:

* `BrakingCriterion`
* `AccelerationCriterion`
* `TurningCriterion`
* `LaneChangeCriterion`
* `Mergingcriterion`

Each criterion can be individually configured e.g. with the deceleration threshold when the `BrakingCriterion` matches. To customize the criterions, you can override the default criterions list passed to the `ScenarioFactoryConfig`:

```python
...
factory_config = ScenarioFactoryConfig(
  criterions=[
    # Only the braking criterion is selected and braking is recognized when a dynamic obstacle decelerates with at least -1.0 continously over 5 time steps
    BrakingCriterion(braking_detection_threshold=-1.0, braking_detection_threshold_hold=5)
  ]
)
...
```


### Creating Your Own Ego Vehicle Selection Criterions

```python
def _obstacle_exceeds_speed_limit(scenario: Scenario, obstacle: DynamicObstacle) -> Optional[int]:
  # Stub function, that returns the time_step if an obstacle exceeds the speed limit and otherwise returns None
  ...

class MyCustomCriterion(EgoVehicleSelectionCriterion):
  def __init__(self, my_custom_start_time_offset: float = 0.5):
    # Your custom criterion must take a time offset as a parameter and pass it to its parent class.This offset will determine when the resulting scenario will start.
    super().__init__(my_custom_start_time_offset)

  def matches(self, scenario: Scenario, obstacle: DynamicObstacle) -> Tuple[bool, int]:
      time_step_at_which_speed_limit_is_exeeded = _obstacle_exceeds_speed_limit(scenario, obstacle)
      if time_step_at_which_speed_limit_is_exeeded is None:
        # Base case for no match must return -1 as time_step
        return False, -1

      # The obstacle exceeds the speed limit, so we return true (as the criterion matches) and the absolute time step at which the speed limit is exceeded
      return True, time_step_at_which_speed_limit_is_exeeded


```

> Note: The returned time step from the `matches` function must be absolute in relation to the scenario. This means it must not be relative to the initial state of the obstacle!

## Ego Vehicle Maneuver Filters


### Pre-Defined Filters

* `LongEnoughManeuver`: Is the trajectory after the start of the maneuver long enough to create a new scenario from it?
* `MinimumVelocityManeuverFilter`: Does the ego vehicle
* `InterestingLaneletNetworkFilter`:
* `EnoughSurroundingVehiclesFilter`: Are there enough other dynamic obstacles around the ego vehicle?

Similar to criterions, you can configure the default filters or change the filters that are applied:

```python
factory_config = ScenarioFactoryConfig(
  filters=[
    # Only the minimum velocity filter is applied
    MinimumVelocityManeuverFilter(
      min_ego_velocity=10 / 3.6
    )
  ]
)
```

### Custom Filters

Similar to criterions you can define custom filters:

```python
class BicycleFilter(EgoVehicleManeuverFilter):
    def matches(self, scenario: Scenario, scenario_time_steps: int, ego_vehicle_maneuver: EgoVehicleManeuver) -> bool:
      return ego_vehicle_maneuver.ego_vehicle.obstacle_type == ObstacleType.BICYCYLE

```
