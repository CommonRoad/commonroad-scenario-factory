from commonroad.visualization.mp_renderer import MPRenderer
from scenario_factory.pipeline import PipelineStepType, PipelineStepExecutionMode, PipelineContext
from pathlib import Path
from commonroad.visualization.draw_params import MPDrawParams
from scenario_factory.pipeline import PipelineStep

#Render Klasse
def pipeline_render_commonroad_scenario(output_path: Path, fps: int = 5, time_steps: int = 25) -> PipelineStep:
    """
    Pipeline-Schritt zur Visualisierung des Szenarios als Video-Datei.
    Args:
        output_path: Der Pfad, in dem die Visualisierung gespeichert werden soll.
        fps: Frames per second für das GIF.
        time_steps: Die Anzahl der Zeitschritte für die Animation.
    """

    # Render das Szenario als Video und speichere es im Ausgabeordner
    def render_step(context: PipelineContext, scenario_container):
        scenario = scenario_container.scenario

        # Gibt alle Objekte im Szenario aus
        print("Scenario ID:", scenario_container.scenario.scenario_id)
        print("PlanningProblemSets:", scenario_container.planning_problem_set)
        print("EgoVehicleManeuvers (falls vorhanden):", getattr(scenario_container.scenario, "ego_vehicle_maneuvers", None))

        #DrawParams konfigurieren
        draw_params = MPDrawParams()
        draw_params.time_begin = 0
        draw_params.time_end = time_steps  # Dynamische Endzeit
        draw_params.fps = fps #Dynamische FPS
        draw_params.dynamic_obstacle.show_label = False
        draw_params.dynamic_obstacle.draw_icon = True
        draw_params.dynamic_obstacle.draw_shape = True


        rnd = MPRenderer()
        output_file = output_path / f"{scenario.scenario_id}.gif"

        rnd.create_video([scenario], str(output_file), draw_params=draw_params)

    return PipelineStep(render_step, type=PipelineStepType.MAP, mode=PipelineStepExecutionMode.SEQUENTIAL)
