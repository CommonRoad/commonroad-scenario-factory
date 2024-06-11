from typing import Dict, Optional, Set, Tuple, Union

from commonroad.scenario.obstacle import Obstacle
from commonroad.scenario.scenario import Scenario

try:
    from commonroad_dc.collision.collision_detection.pycrcc_collision_dispatch import create_collision_object
    from commonroad_dc.pycrcc import CollisionChecker
except ImportError:
    from commonroad_dc.collision.collision_detection.pycrcc_collision_dispatch import create_collision_object
    from commonroad_dc.pycrcc import CollisionChecker

    raise ImportError(
        "CommonRoad collision checker"
        "https://gitlab.lrz.de/tum-cps/commonroad-collision-checker not installed properly. "
        "Build with cmake and add folder to python path"
    )


class DeleteScenario(RuntimeError):
    pass


def check_collision(
    obstacles: Dict[int, Obstacle],
    return_colliding_ids: bool = False,
    get_all: bool = False,
    max_collisions: Optional[int] = None,
) -> Union[bool, Tuple[bool, Set[int]]]:
    """
    Returns true if vehicles in scenario collide.
    """
    obstacle_list = []
    obs_ids = []
    for obs_id, obs in obstacles.items():
        obstacle_list.append(obs)
        obs_ids.append(obs_id)

    cc_objects = [create_collision_object(obs) for obs in obstacle_list]
    if get_all is True:
        obs_dict = {cc_objects[i]: obs.obstacle_id for i, obs in enumerate(obstacle_list)}
    else:
        obs_dict = None

    # check self collisions
    collision = False
    colliding_ids = set()
    for i, obs in enumerate(cc_objects):
        cc = CollisionChecker()
        [cc.add_collision_object(o) for o in cc_objects[i + 1 :]]
        if get_all is True:
            obs_ids = [obs_dict[o] for o in cc.find_all_colliding_objects(obs)]
        else:
            obs_ids = [obs_ids[i]] if cc.collide(obs) else None

        if len(obs_ids) > 0:
            collision = True
            if return_colliding_ids is True or max_collisions is not None:
                colliding_ids |= set(obs_ids)
                if max_collisions is not None and len(colliding_ids) > max_collisions:
                    raise DeleteScenario
            else:
                return True

    if return_colliding_ids:
        return collision, colliding_ids
    else:
        return False


def check_extreme_states(scenario: Scenario):
    for obs in scenario.dynamic_obstacles:
        for state in obs.prediction.trajectory.state_list:
            if abs(state.acceleration) > 11.0:
                return False
