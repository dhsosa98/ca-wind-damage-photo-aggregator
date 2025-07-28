#!/bin/bash

# Wind-Damage Photo Aggregator - Deployment Script
set -e

echo "Starting deployment..."

# Check prerequisites
echo "Checking prerequisites..."
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI not found. Please install it."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not found. Please install it."; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "❌ Terraform not found. Please install it."; exit 1; }
if [ -z "$GEMINI_API_KEY" ]; then
  echo "❌ GEMINI_API_KEY environment variable is not set. Please export it before deploying."
  exit 1
fi

# Check AWS credentials
echo "Checking AWS credentials..."
aws sts get-caller-identity >/dev/null 2>&1 || { echo "❌ AWS credentials not configured. Please run 'aws configure'."; exit 1; }

# Get AWS account and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
ECR_REPO="wind-damage-aggregator"
IMAGE_TAG="latest"

echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"

# Build Docker image
echo "Building Docker image..."
DOCKER_BUILDKIT=0 docker build -t $ECR_REPO:$IMAGE_TAG .

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Check if ECR repository exists, if not, create it with Terraform
ECR_EXISTS=$(aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" 2>/dev/null || echo "notfound")
if [[ "$ECR_EXISTS" == "notfound" ]]; then
  echo "ECR repository '$ECR_REPO' does not exist. Creating with Terraform..."
  terraform -chdir=iac init
  terraform -chdir=iac apply -auto-approve -target=aws_ecr_repository.lambda -var="gemini_api_key=$GEMINI_API_KEY"
else
  echo "ECR repository '$ECR_REPO' already exists."
fi

# Tag and push image (after ECR repository is created by Terraform)
echo "Pushing Docker image to ECR..."
docker tag $ECR_REPO:$IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG

echo "Deploying infrastructure with Terraform..."
cd iac
terraform init
terraform apply -auto-approve -var="gemini_api_key=$GEMINI_API_KEY"
cd ..

# Get API endpoint
echo "Getting API endpoint..."
API_ENDPOINT=$(terraform -chdir=iac output -raw api_endpoint)

echo "Deployment complete!"
echo "API Endpoint: $API_ENDPOINT"
echo ""
echo "Test with:"
echo "curl -X POST $API_ENDPOINT \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d @test/sample_request.json" 