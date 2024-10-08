from typing import List, Set

from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario
from commonroad_dc.collision.collision_detection.pycrcc_collision_dispatch import (
    create_collision_object,
)
from commonroad_dc.pycrcc import CollisionChecker


def has_scenario_collisions(scenario: Scenario) -> bool:
    return len(get_colliding_dynamic_obstacles_in_scenario(scenario)) > 0


def get_colliding_dynamic_obstacles_in_scenario(
    scenario: Scenario,
    get_all: bool = False,
) -> Set[int]:
    return get_colliding_dynamic_obstacles(scenario.dynamic_obstacles, get_all)


def get_colliding_dynamic_obstacles(
    obstacles: List[DynamicObstacle],
    get_all: bool = False,
) -> Set[int]:
    """
    Returns the IDs of all dynamic objects that are colliding in a scenario.

    :param get_all: if True, both obstacles of a pair of colliding obstacles is returned, otherwise only the first one
    """
    cc_objects_to_obstacle_id = {}
    cc_objects = []
    for obstacle in obstacles:
        cc_object = create_collision_object(obstacle)
        cc_objects_to_obstacle_id[cc_object] = obstacle.obstacle_id
        cc_objects.append(cc_object)

    # check self collisions
    resulting_colliding_ids = set()
    for i, current_cc_object in enumerate(cc_objects):
        cc = CollisionChecker()
        # Add the remaining collision objects to the collision checker that were not yet checked
        # Only the objects after the current_cc_object have to be added, because the objects before the current one, were already checked in the iteration before
        for other_cc_object in cc_objects[i + 1 :]:
            cc.add_collision_object(other_cc_object)

        if get_all is True:
            # Get the IDs of all dynamic obstacles that are colliding with the current object
            colliding_dynamic_obstacles = [
                cc_objects_to_obstacle_id[o]
                for o in cc.find_all_colliding_objects(current_cc_object)
            ]
            if len(colliding_dynamic_obstacles) > 0:
                # If there is at least one collision, the current object must also be added to the results
                resulting_colliding_ids.add(cc_objects_to_obstacle_id[current_cc_object])
                resulting_colliding_ids.update(colliding_dynamic_obstacles)
        else:
            if cc.collide(current_cc_object):
                # If the current object collides with any other object, only add the current one to the results
                resulting_colliding_ids.add(cc_objects_to_obstacle_id[current_cc_object])

    return resulting_colliding_ids
