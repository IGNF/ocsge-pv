FROM ubuntu:24.04 AS common
ARG TZ="Europe/Paris"
RUN ln -fs "/usr/share/zoneinfo/${TZ}" \
&& apt update \
&& apt -y upgrade \
&& DEBIAN_FRONTEND=noninteractive apt -y install tzdata \
&& dpkg-reconfigure --frontend noninteractive tzdata \
&& apt -y install python3 python3-gdal \
&& sudo apt -y autoremove --purge \
&& apt -y clean
COPY . /app
WORKDIR /app

FROM common AS build_environment
RUN apt update \
&& apt -y install python3-venv python3-setuptools python3-wheel
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN source /opt/venv/bin/activate \
&& python3 -m build \
&& python3 -m pip install ./dist/*.whl

FROM common AS run_environment
COPY --from=build_environment /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
USER ubuntu
ENV PATH="/opt/venv/bin:$PATH"

CMD ["bash"]