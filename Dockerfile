FROM ubuntu:24.04@sha256:023f8a753c22258c9fe2d0005a7d28258038da7d620e9f93e9ad78aa266f9f11 AS common
ARG TZ="Europe/Paris"
ARG HOST_UID=1000
ARG HOST_GID=1000
USER root
RUN ln -fs "/usr/share/zoneinfo/${TZ}" \
&& apt update \
&& apt -y upgrade \
&& DEBIAN_FRONTEND=noninteractive apt -y install tzdata \
&& dpkg-reconfigure --frontend noninteractive tzdata \
&& apt -y install python3 python3-gdal libgdal-dev \
&& apt -y autoremove --purge \
&& apt -y clean
RUN groupadd -g $HOST_GID usergroup || echo "Group id already in use in the image: $HOST_GID"; \
useradd -m -u $HOST_UID -g usergroup -G usergroup user -d /home/user || echo "User id already in use in the image: $HOST_UID"
COPY . /app
COPY ./src/ocsge_pv/resources /opt/resources
RUN chown -R $HOST_UID:$HOST_GID /app /opt/resources
ENV OCSGE_PV_FIXTURE_DIR="/app/tests/fixtures"
ENV OCSGE_PV_RESOURCE_DIR="/opt/resources"
WORKDIR /app

FROM common AS build_environment
RUN apt update \
&& apt -y install python3-venv python3-pip
USER $HOST_UID:$HOST_GID
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN python3 -m pip install setuptools wheel build "gdal==$(gdal-config --version)" \
&& python3 -m build

FROM common AS install_environment
RUN apt update \
&& apt -y install python3-venv python3-pip
USER $HOST_UID:$HOST_GID
COPY --from=build_environment /app/dist/*.whl /app/dist/
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN python3 -m pip install "gdal==$(gdal-config --version)" ./dist/*.whl

FROM common AS run_environment
USER $HOST_UID:$HOST_GID
COPY --from=install_environment /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

CMD ["ocsge-pv-help"]
