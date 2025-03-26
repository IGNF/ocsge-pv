FROM ubuntu:24.04 AS common
ARG TZ="Europe/Paris"
RUN ln -fs "/usr/share/zoneinfo/${TZ}" \
&& apt update \
&& apt -y upgrade \
&& DEBIAN_FRONTEND=noninteractive apt -y install tzdata \
&& dpkg-reconfigure --frontend noninteractive tzdata \
&& apt -y install python3 python3-gdal libgdal-dev \
&& apt -y autoremove --purge \
&& apt -y clean
COPY . /app
ENV OCSGE_PV_FIXTURE_DIR="/app/tests/fixtures"
ENV OCSGE_PV_RESOURCE_DIR="/app/src/ocsge_pv/resources"
WORKDIR /app
RUN chown -R ubuntu /app
ENV HOME="/tmp"
RUN ln -s /app/src/ocsge_pv/resources $HOME/ocsge-pv-resources

FROM common AS build_environment
RUN apt update \
&& apt -y install python3-venv python3-pip
USER ubuntu
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN python3 -m pip install setuptools wheel build "gdal==$(gdal-config --version)" \
&& python3 -m build

FROM common AS install_environment
RUN apt update \
&& apt -y install python3-venv python3-pip
USER ubuntu
COPY --from=build_environment /app/dist/*.whl /app/dist/
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN python3 -m pip install "gdal==$(gdal-config --version)" ./dist/*.whl

FROM common AS run_environment
USER ubuntu
ENV HOME="/home/ubuntu"
COPY --from=install_environment /app/venv /app/venv
COPY --from=common /app/src/ocsge_pv/resources $HOME/resources
ENV OCSGE_PV_RESOURCE_DIR="$HOME/resources"
ENV PATH="/app/venv/bin:$PATH"

CMD ["ocsge-pv-help"]