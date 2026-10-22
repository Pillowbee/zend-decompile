# syntax=docker/dockerfile:1
FROM debian:bookworm

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    autoconf automake bison flex re2c build-essential libxml2-dev pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# PHP source is supplied through a temporary named context outside the checkout.
COPY --from=php_source /php-5.2.17.tar.bz2 /tmp/php-src.tar.bz2
RUN echo 'e81beb13ec242ab700e56f366e9da52fd6cf18961d155b23304ca870e53f116c  /tmp/php-src.tar.bz2' | sha256sum -c - \
    && mkdir -p /usr/src/php52 \
    && tar -xjf /tmp/php-src.tar.bz2 -C /usr/src/php52 --strip-components=1 \
    && rm /tmp/php-src.tar.bz2

WORKDIR /usr/src/php52
RUN CFLAGS='-O2 -fcommon' ./configure --disable-all --enable-cli --without-pear \
    --with-config-file-path=/usr/local/etc/php52 \
    && make -j2 \
    && install -Dm755 sapi/cli/php /usr/local/bin/php \
    && mkdir -p /usr/local/etc/php52

# The local archive is split into seven BuildKit secrets to fit the secret-size
# limit. Reassembly stays in this RUN step, so the archive is not an image layer.
RUN --mount=type=secret,id=optimizer_00,required=true \
    --mount=type=secret,id=optimizer_01,required=true \
    --mount=type=secret,id=optimizer_02,required=true \
    --mount=type=secret,id=optimizer_03,required=true \
    --mount=type=secret,id=optimizer_04,required=true \
    --mount=type=secret,id=optimizer_05,required=true \
    --mount=type=secret,id=optimizer_06,required=true \
    test "$(cat /run/secrets/optimizer_* | sha256sum | cut -d ' ' -f 1)" = \
      2dc42dec471cf6754f8f7dbb7444a040c92cc6c99b80c8aa924bdcd4d33decb8 \
    && cat /run/secrets/optimizer_* | tar -xOzf - \
       ZendOptimizer-3.3.9-linux-glibc23-x86_64/data/5_2_x_comp/ZendOptimizer.so \
       > /usr/local/lib/ZendOptimizer.so \
    && printf 'zend_extension=/usr/local/lib/ZendOptimizer.so\n' \
       > /usr/local/etc/php52/php.ini

WORKDIR /work
CMD ["php", "-v"]
