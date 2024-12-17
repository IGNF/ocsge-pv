FROM ubuntu:24.04 AS base
ARG TZ="Europe/Paris"
RUN ln -fs "/usr/share/zoneinfo/${TZ}" \
&& apt update \
&& DEBIAN_FRONTEND=noninteractive apt install -y tzdata \
&& dpkg-reconfigure --frontend noninteractive tzdata \
&& apt install -y python3 python3-gdal python3-pip
RUN python3 -m pip install --upgrade pip
WORKDIR /home/ubuntu

FROM base AS build_stage
COPY . /home/ubuntu/app
RUN python3 -m pip install --upgrade setuptools build
WORKDIR /home/ubuntu/app
USER ubuntu
RUN python3 -m build

FROM base AS install_stage
COPY --from=build_stage /home/ubuntu/app/dist/*.whl /tmp/app.whl
USER ubuntu
RUN python3 -m pip install --user /tmp/app.whl

CMD ["bash"]