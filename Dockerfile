# Wind-Damage Photo Aggregator - Lambda Container
# Using specific Lambda base image

FROM public.ecr.aws/lambda/python:3.11

# Copy requirements and install dependencies
COPY src/requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt --target ${LAMBDA_TASK_ROOT}

# Copy source code
COPY src/ ${LAMBDA_TASK_ROOT}/

# Set environment variables
ENV PYTHONPATH=${LAMBDA_TASK_ROOT}
ENV PYTHONUNBUFFERED=1

# Set the CMD to your handler
CMD ["app.lambda_handler"]