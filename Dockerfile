FROM debian:bookworm-slim

ARG GODOT_VERSION=4.6.3
ARG TARGETARCH
RUN test "$TARGETARCH" = "amd64" \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
       libx11-6 libxcursor1 libxinerama1 libxrandr2 libxi6 libgl1 \
       libasound2 libpulse0 libfontconfig1 libxkbcommon0 libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*
RUN set -eu; \
    base="https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}-stable"; \
    archive="Godot_v${GODOT_VERSION}-stable_linux.x86_64.zip"; \
    cd /tmp; \
    curl -fsSLO "$base/$archive"; \
    curl -fsSLO "$base/SHA512-SUMS.txt"; \
    grep " $archive\$" SHA512-SUMS.txt > selected.sha512; \
    sha512sum -c selected.sha512; \
    unzip "$archive"; \
    mv "Godot_v${GODOT_VERSION}-stable_linux.x86_64" /usr/local/bin/godot; \
    chmod +x /usr/local/bin/godot; \
    rm -f "$archive" SHA512-SUMS.txt selected.sha512

RUN useradd --create-home --uid 1000 player
WORKDIR /app
COPY --chown=player:player . .
RUN chown player:player /app
USER player
ENV XDG_DATA_HOME=/home/player/.local/share \
    XDG_CONFIG_HOME=/home/player/.config \
    XDG_CACHE_HOME=/home/player/.cache
CMD ["sh", "scripts/verify.sh"]
