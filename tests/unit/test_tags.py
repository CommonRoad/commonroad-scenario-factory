from commonroad.scenario.scenario import Scenario

from scenario_factory.tags import find_applicable_tags_for_scenario


class TestAssignApplicableTags:
    def test_does_not_assign_tags_to_empty_scenario(self):
        scenario = Scenario(dt=0.1)
        tags = find_applicable_tags_for_scenario(scenario)
        assert len(tags) == 0
