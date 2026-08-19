FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

# ToeholdDesignBench — reproducible evaluation container
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pandas pyarrow numpy scipy scikit-learn openpyxl

WORKDIR /workspace/ToeholdDesignBench
COPY src ./src
COPY tests ./tests
COPY requirements.txt ./

# Data is mounted at runtime from /mnt/cunyuliu/ToeholdDesignBench (not copied into image).
# Run: docker run -v /mnt/cunyuliu/ToeholdDesignBench:/mnt/cunyuliu/ToeholdDesignBench \
#        toeholddesignbench python src/runner.py --method B1_thermo
ENTRYPOINT ["python", "src/runner.py"]