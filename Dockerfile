FROM ubuntu:24.04 AS base
ARG TZ="Europe/Paris"
RUN ln -fs "/usr/share/zoneinfo/${TZ}" \
&& apt update \
&& DEBIAN_FRONTEND=noninteractive apt install -y tzdata \
&& dpkg-reconfigure --frontend noninteractive tzdata \
&& apt install -y python3 python3-gdal python3-pip
WORKDIR /home/ubuntu
RUN chown -R ubuntu:ubuntu /home/ubuntu

FROM base AS build_stage
WORKDIR /home/ubuntu/app
COPY . /home/ubuntu/app
RUN apt install -y python3-setuptools python3-build python3-venv \
&& chown -R ubuntu:ubuntu /home/ubuntu
USER ubuntu
RUN python3 -m build

FROM base AS install_stage
USER ubuntu
COPY --from=build_stage /home/ubuntu/app/dist/*.whl /tmp/app.whl
RUN python3 -m pip install --user /tmp/app.whl

CMD ["bash"]