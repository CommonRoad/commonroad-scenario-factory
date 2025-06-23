# Getting Started

## Installation

```bash
$ pip install commonroad-scenario-factory
```

### Additional Requirements

Most dependencies are already installed through poetry, but some have to be installed manually on your system:

* [osmium](https://osmcode.org/osmium-tool/): Required for globetrotter
* [Java Runtime Environment](https://www.java.com/en/): Required for running simulations with OpenTrafficSim (OTS)

### Development

Before you start with the installation of the scenario factory, make sure that you have at least [python 3.10](https://www.python.org/downloads/) and [poetry](https://www.python.org/downloads/) installed on your system.

To get started, clone the repo and install all dependencies:

```sh
$ git clone git@gitlab.lrz.de:cps/commonroad/scenario-factory.git
$ cd scenario-factory
$ poetry install --with tests --with docs --with dev
```


## Use the Scenario Factory

After you have set up the Scenario Factory, you can try to [generate some scenarios](./generate_scenarios).
