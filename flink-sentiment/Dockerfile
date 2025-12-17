#image: asia-southeast1-docker.pkg.dev/dongtd2/flink/flink-sentiment

# Image base: Flink 1.19 + Java 17
FROM flink:1.19.1-scala_2.12-java17

# Install Python and dependencies
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-setuptools \
    python3-wheel \
 && ln -s /usr/bin/python3 /usr/bin/python \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /tmp/requirements.txt
RUN  pip3 install --no-cache-dir -r /tmp/requirements.txt
     #pip3 install --no-cache-dir apache-flink==1.19.1

# Debug Python and PyFlink installation
RUN python3 --version && \
    python --version && \
    pip3 show apache-flink && \
    pip3 show requests && \
    pip3 show urllib3

# Copy Kafka connector and Kafka clients jars
COPY flink-connector-kafka-3.3.0-1.19.jar /opt/flink/lib/
COPY kafka-clients-3.3.0.jar /opt/flink/lib/

# Copy job code to Flink's usrlib directory
WORKDIR /opt/flink/usrlib
COPY flink_job_sentiment.py flink_job_telegram.py flink_job_c2c_telegram.py utils.py ./

# Set PYTHONPATH for TaskManagers to find code
ENV PYTHONPATH="/opt/flink/usrlib:/usr/local/lib/python3.10/dist-packages"
ENV FLINK_PYTHON_EXECUTABLE="/usr/bin/python3"

# Switch back to flink user
USER flink

#RUN wget -P /opt/flink/lib https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-kafka/3.3.0-1.19/flink-connector-kafka-3.3.0-1.19.jar
#RUN wget -P /opt/flink/lib https://repo.maven.apache.org/maven2/org/apache/kafka/kafka-clients/3.3.0/kafka-clients-3.3.0.jar


# ADD hadoop-3.3.4/share/hadoop/common/*.jar $FLINK_HOME/lib/
# ADD hadoop-3.3.4/share/hadoop/hdfs/*.jar $FLINK_HOME/lib/

# Debug PyFlink installation
# RUN python3 --version && \
#     pip3 show apache-flink && \
    #python3 -c "from pyflink.datastream.watermark_strategy import WatermarkStrategy; print('WatermarkStrategy imported successfully')"
    #python3 -c "from pyflink.common.watermark_strategy import WatermarkStrategy; print('WatermarkStrategy imported successfully')"
