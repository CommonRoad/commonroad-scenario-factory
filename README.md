# CommonRoad Scenario Factory
[![pipeline status](https://gitlab.lrz.de/cps/commonroad/sumocr-scenario-generation/badges/develop/pipeline.svg)](https://gitlab.lrz.de/cps/commonroad/sumocr-scenario-generation/-/commits/develop)
[![coverage report](https://gitlab.lrz.de/cps/commonroad/sumocr-scenario-generation/badges/develop/coverage.svg)](https://gitlab.lrz.de/cps/commonroad/sumocr-scenario-generation/-/commits/develop)

The CommonRoad Scenario Factory is a toolbox that combines many different tools from the whole CommonRoad ecosystem to efficiently process CommonRoad Scenarios.

## Installation

Before you start with the installation of the scenario factory, make sure that you have at least [python 3.10](https://www.python.org/downloads/) and [poetry](https://www.python.org/downloads/) installed on your system.

To get started, clone the repo and install all dependencies:

```
$ git clone git@gitlab.lrz.de:cps/commonroad/scneario-factory.git
$ cd scenario-factory
$ poetry install --with tests --with docs --with dev
```

### Additional Requirements

Most dependencies are already installed through poetry, but some have to be installed manually on your system:

* [osmium](https://osmcode.org/osmium-tool/): Required for globetrotter
* [Java Runtime Environment](https://www.java.com/en/): Required for running simulations with OpenTrafficSim (OTS)

## Documentation

The full documentation can be found at [cps.pages.gitlab.lrz.de/commonroad/scenario-factory](https://cps.pages.gitlab.lrz.de/commonroad/scenario-factory/).
