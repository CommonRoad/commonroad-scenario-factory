from pathlib import Path

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.visualization.mp_renderer import MPRenderer
from matplotlib import pyplot as plt

path = Path(__file__).parent.joinpath("/home/florian/git/sumocr-scenario-generation/files/commonroad/DEU_LfV.xml")
scenario, _ = CommonRoadFileReader(path).open()

plt.figure(figsize=(25, 10))
rnd = MPRenderer()
rnd.draw_params.lanelet_network.draw_ids = True
scenario.draw(rnd)
rnd.render()
plt.show()


print("hey")
