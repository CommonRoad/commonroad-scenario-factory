# CommonRoad Scenario Factory

[![PyPI pyversions](https://img.shields.io/pypi/pyversions/commonroad-scenario-factory.svg)](https://pypi.python.org/pypi/commonroad-scenario-factory/)
[![PyPI version fury.io](https://badge.fury.io/py/commonroad-scenario-factory.svg)](https://pypi.python.org/pypi/commonroad-scenario-factory/)
[![PyPI download month](https://img.shields.io/pypi/dm/commonroad-scenario-factory.svg?label=PyPI%20downloads)](https://pypi.python.org/pypi/commonroad-scenario-factory/)
[![PyPI license](https://img.shields.io/pypi/l/commonroad-scenario-factory.svg)](https://pypi.python.org/pypi/commonroad-scenario-factory/)


The CommonRoad Scenario Factory is a toolbox that combines many different tools from the whole CommonRoad ecosystem to efficiently process CommonRoad scenarios.
Its current main use case is the generation of new CommonRoad scenarios with the traffic simulators OpenTrafficSim (OTS) and SUMO.

The full documentation can be found at [cps.pages.gitlab.lrz.de/commonroad/scenario-factory](https://cps.pages.gitlab.lrz.de/commonroad/scenario-factory/).

## Installation

```bash
$ pip install commonroad-scenario-factory
```

### Additional Requirements

Most dependencies are already installed through poetry, but some have to be installed manually on your system:

* [osmium](https://osmcode.org/osmium-tool/): Required for the globetrotter package (i.e. the extraction of map segments from OpenStreetMap (OSM)).
* [Java Runtime Environment](https://www.java.com/en/): Required for running simulations with OpenTrafficSim (OTS).

SUMO and OTS are distributed as python packages and included as dependencies. Therefore, they do not need to be installed separately.

## Development

Before you start with the installation of the scenario factory, make sure that you have at least [python 3.10](https://www.python.org/downloads/) and [poetry](https://www.python.org/downloads/) installed on your system alongside the additional requirements listed above.

To get started with development, clone the repo and install all dependencies:

```
$ git clone git@gitlab.lrz.de:cps/commonroad/scneario-factory.git
$ cd scenario-factory
$ poetry install --with tests --with docs --with dev
```

