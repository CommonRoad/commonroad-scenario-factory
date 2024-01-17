# create docker image for CI/CD pipeline
FROM ubuntu:latest
LABEL authors="Florian Finkeldei <florian.finkeldei@tum.de>"

RUN apt-get update
RUN apt-get install software-properties-common osmium-tool -y
RUN add-apt-repository ppa:sumo/stable
RUN apt-get update
RUN apt-get install sumo sumo-tools sumo-doc -y

ENV SUM0_HOME /usr/share/sumo
