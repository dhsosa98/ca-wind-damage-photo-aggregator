# Wind-Damage Photo Aggregator

## Overview
AWS Lambda microservice that analyzes exterior damage photos and returns a claim-level wind damage summary.

## Architecture
- **Runtime**: Python 3.11 Lambda (Container)
- **Entry Point**: API Gateway HTTP API
- **AI Service**: Amazon Rekognition Custom Labels
- **Infrastructure**: Terraform single stack
- **Deployment**: Docker container via ECR

## Prerequisites
- AWS CLI configured
- Terraform installed
- Docker installed
- Python 3.11+

## Quick Start
```bash
# Deploy (builds Docker image and deploys infrastructure)
make deploy

# Test
curl -X POST https://your-api-gateway-url/aggregate \
  -H "Content-Type: application/json" \
  -d @test/sample_request.json

# Teardown
make destroy
```

## Manual Deployment Steps
```bash
# 1. Build and push Docker image
make build

# 2. Deploy infrastructure
cd iac && terraform init && terraform apply

# 3. Get API endpoint
make endpoint
```

## Project Structure
- `src/` - Lambda application code
- `iac/` - Terraform infrastructure
- `test/` - Sample requests and responses
- `Dockerfile` - Container configuration
- `docs/` - Additional documentation

## Docker Commands
```bash
# Build image locally
make docker-build

# Test locally
make docker-test

# Push to ECR
make docker-push

# Show ECR URL
make ecr-url
```

## Assumptions
- Image URLs are publicly accessible
- Damage detection is done using Google Gemini 2.5 Flash model using a custom prompt and a structured output schema
- Quality scoring combines blur (Laplacian variance), brightness, contrast, and image size:
    - Blur: Laplacian variance (higher = less blurry)
    - Brightness: average value in HSV space (optimal near 128)
    - Contrast: standard deviation of grayscale values
    - Size: penalizes images smaller than 200x200 or much larger than 8000x8000; optimal area is around 1MP (1024x1024)
    - Final quality score is a weighted sum: blur (40%), brightness (30%), contrast (20%), size (10%)
    - Acceptable quality: score ≥ 0.3; quality is described as "excellent", "good", "fair", "poor", or "unacceptable" based on score
- Deduplication uses perceptual hashing
- Max representative images per area is 3
- The notes field is concatenated from the notes field of the damage analysis results
- Container deployment for better dependency management


## Experience & Technical Decisions

### Architecture Evolution
- **Initial Approach**: Started with a simple Lambda function using basic image processing
- **Current Architecture**: Evolved to a containerized microservice with comprehensive AI-powered analysis pipeline
- **Key Decision**: Chose AWS Lambda with container deployment for better dependency management and consistent runtime environment

### AI/ML Technology Choices
- **Damage Detection**: Migrated from basic computer vision using Rekognition Custom Labels to Google Gemini 2.5 Flash for superior damage classification
- **Reasoning**: Gemini provides more nuanced understanding of damage types and locations compared to traditional CV approaches
- **Structured Output**: Implemented Pydantic schemas for reliable, type-safe AI responses
- **Batch Processing**: Added async processing with semaphores to handle multiple images efficiently

### Quality Assessment Strategy
- **Multi-dimensional Scoring**: Combined blur detection (Laplacian variance), brightness analysis, contrast measurement, and size optimization
- **Weighted Algorithm**: 40% blur, 30% brightness, 20% contrast, 10% size - based on real-world testing
- **Acceptance Criteria**: Score ≥ 0.3 for processing, with descriptive quality labels

### Deduplication Approach
- **Perceptual Hashing**: Implemented to identify visually similar images
- **Representative Selection**: Limited to 3 images per damage area to maintain diversity while reducing redundancy
- **Performance**: Significantly reduces processing time and storage costs

### Infrastructure Decisions
- **Terraform IaC**: Single stack deployment for reproducibility and version control
- **Container Deployment**: Better dependency isolation and runtime consistency
- **Error Handling**: Comprehensive logging with correlation IDs for debugging

### Performance Optimizations
- **Async Processing**: Parallel image analysis with controlled concurrency
- **Batch Operations**: Efficient handling of multiple images per request
- **Memory Management**: Optimized image processing to handle large files
- **Timeout Configuration**: 15-minute Lambda timeout for complex analysis tasks

### Outstanding Issues

- **API Gateway Availability**: The API Gateway currently returns a 503 Service Unavailable or times out.
    - The endpoint works correctly when invoked locally or directly via Lambda test events, but not through the API Gateway.
    - Potential solutions include increasing the API Gateway and Lambda timeouts, and consulting AWS Support for further troubleshooting.

## Development
```bash
# Run tests
make test

# Load testing
make load-test

# Clean up
make clean
``` 