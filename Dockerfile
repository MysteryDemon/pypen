FROM mysterydemon/pypen:master

WORKDIR /app
ARG S6_OVERLAY_VERSION=3.2.0.2
ARG S6_OVERLAY_ARCH=x86_64
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp/
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_OVERLAY_ARCH}.tar.xz /tmp/
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz \
    && tar -C / -Jxpf /tmp/s6-overlay-${S6_OVERLAY_ARCH}.tar.xz \
    && rm -f /tmp/s6-overlay-*.tar.xz
ENV PATH="/command:${PATH}"

COPY requirements.txt ./
RUN pip3 install --no-cache-dir uv
RUN uv pip install --system --no-cache -r requirements.txt
RUN mkdir -p /etc/s6/services /var/log/s6

COPY . .
EXPOSE 5000
CMD ["python3", "start.py"]
