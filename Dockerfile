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
WORKDIR /app

# FROM common AS test_environment
# RUN apt update \
# && apt -y install python3-venv python3-pip
# RUN python3 -m venv /opt/venv
# ENV PATH="/opt/venv/bin:$PATH"
# RUN python3 -m pip install "gdal==$(gdal-config --version)" .[test] \
# && python3 -m pytest ./tests

FROM common AS build_environment
RUN apt update \
&& apt -y install python3-venv python3-pip
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN python3 -m pip install setuptools wheel build "gdal==$(gdal-config --version)" \
&& python3 -m build

FROM common AS install_environment
COPY --from=build_environment /app/dist/*.whl /app/dist/
RUN apt update \
&& apt -y install python3-venv python3-pip
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN python3 -m pip install "gdal==$(gdal-config --version)" ./dist/*.whl

FROM common AS run_environment
COPY --from=install_environment /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
USER ubuntu
ENV PATH="/opt/venv/bin:$PATH"

CMD ["bash"]