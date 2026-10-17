FROM lthub/moodle:4.5.14
RUN apt-get update \
&& apt-get install -y --no-install-recommends libpq-dev \
&& docker-php-ext-install pdo_pgsql pgsql \
&& rm -rf /var/lib/apt/lists/*
